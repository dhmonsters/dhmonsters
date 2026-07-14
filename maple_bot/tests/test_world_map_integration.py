# 전역 지도 편집 페이지와 런타임 신호 연결을 검증하는 통합 테스트
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from core_ui.pages import build_pages
from core_ui.world_map_editor import WorldMapEditor
from run_integrated import bind_world_editor


class FakeConfig:
    def __init__(self):
        self.data = {
            "world_map": {"enabled": True},
            "navigation": {"nodes": [], "edges": [], "routes": []},
            "floor_hunt": {"route": []},
        }

    def get(self, *keys, default=None):
        node = self.data
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def set(self, *args, value=None):
        if value is None:
            *keys, value = args
        else:
            keys = list(args)
        node = self.data
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value

    def save(self):
        pass


class FakeEditor(QObject):
    destination_requested = pyqtSignal(str)
    route_start_requested = pyqtSignal(str)

    def set_runtime_state_provider(self, **providers):
        self.providers = providers


class FakeShell:
    def __init__(self, editor):
        self.editor = editor

    def findChild(self, *_args):
        return self.editor


class FakeRuntime:
    def __init__(self):
        self.destinations = []
        self.routes = []

    def navigate_world_to(self, node_id):
        self.destinations.append(node_id)
        return True

    def start_world_route(self, route_id):
        self.routes.append(route_id)
        return True

    def world_position(self):
        return None

    def world_tracking_state(self):
        return "unavailable"

    def world_viewport(self):
        return None


def test_navigation_page_contains_world_editor_when_enabled():
    app = QApplication.instance() or QApplication([])
    pages = build_pages(FakeConfig())

    editor = pages[1].findChild(WorldMapEditor, "worldMapEditor")

    assert editor is not None


def test_editor_requests_are_forwarded_to_runtime():
    app = QApplication.instance() or QApplication([])
    editor = FakeEditor()
    runtime = FakeRuntime()

    bind_world_editor(FakeShell(editor), runtime)
    editor.destination_requested.emit("node-002")
    editor.route_start_requested.emit("route-001")

    assert runtime.destinations == ["node-002"]
    assert runtime.routes == ["route-001"]
    assert editor.providers["tracking_state_fn"]() == "unavailable"


def test_runtime_image_trigger_uses_captured_hunt_area_only():
    import numpy as np
    from types import SimpleNamespace
    from core.runtime import BotRuntime

    calls = []
    runtime = object.__new__(BotRuntime)
    runtime._cfg = SimpleNamespace(
        image_trigger_spec=object(),
        hunt_area_region={"left": 10, "top": 20, "width": 30, "height": 15},
    )
    runtime._image_trigger = SimpleNamespace(
        check=lambda frame, region, spec: calls.append((frame.shape, region, spec))
    )
    runtime._resolve_region = lambda region: region
    runtime._capture = lambda region: np.zeros((15, 30, 3), dtype=np.uint8)
    runtime.log = lambda *args: None

    runtime._check_image_trigger()

    assert calls == [((15, 30, 3), (0, 0, 30, 15), runtime._cfg.image_trigger_spec)]


def test_runtime_image_trigger_isolates_region_resolution_error():
    from types import SimpleNamespace
    from core.runtime import BotRuntime

    logs = []
    runtime = object.__new__(BotRuntime)
    runtime._cfg = SimpleNamespace(image_trigger_spec=object(), hunt_area_region={})
    runtime._image_trigger = object()
    runtime._resolve_region = lambda region: (_ for _ in ()).throw(ValueError("bad region"))
    runtime.log = lambda *args: logs.append(args)

    assert runtime._check_image_trigger() is None
    assert "bad region" in logs[0][0]


def test_world_editor_survives_capture_initialization_failure(monkeypatch):
    from core.screen_reader import ScreenReader

    app = QApplication.instance() or QApplication([])
    monkeypatch.setattr(
        ScreenReader,
        "__init__",
        lambda self: (_ for _ in ()).throw(RuntimeError("capture unavailable")),
    )

    pages = build_pages(FakeConfig())

    assert pages[1].findChild(WorldMapEditor, "worldMapEditor") is not None
