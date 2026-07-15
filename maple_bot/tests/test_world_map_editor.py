# 전역 지도 편집기의 노드와 이미지 트리거 설정 저장을 검증하는 테스트
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QImage
from PyQt6.QtWidgets import QApplication, QMessageBox, QPushButton

from core_ui.world_map_editor import WorldMapEditor


class FakeConfig:
    def __init__(self):
        self.data = {
            "world_map": {},
            "navigation": {"nodes": [], "edges": [], "routes": []},
            "attack": {},
        }
        self.saved = 0
        self.loaded = 0

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
        self.saved += 1

    def load(self):
        self.loaded += 1


def test_editor_saves_action_node():
    app = QApplication.instance() or QApplication([])
    config = FakeConfig()
    editor = WorldMapEditor(config)

    editor.add_action_node(100, 80, "사냥", "up", 0.2, 1, 0.0, 1.0)

    nodes = config.get("navigation", "nodes")
    assert nodes[0]["kind"] == "action"
    assert nodes[0]["action"]["key"] == "up"
    assert config.saved == 1


def test_editor_saves_image_trigger_settings():
    app = QApplication.instance() or QApplication([])
    config = FakeConfig()
    editor = WorldMapEditor(config)

    editor.save_image_trigger(
        True, "templates/target.png", 0.88, 0.2, 3.0,
        "space", 0.1, 2, 0.3, 0.5,
    )

    trigger = config.get("attack", "image_trigger")
    assert trigger["template_path"] == "templates/target.png"
    assert trigger["action"]["repeat"] == 2
    assert config.saved == 1


def test_editor_collects_two_pairs_and_applies_calibration():
    app = QApplication.instance() or QApplication([])
    config = FakeConfig()
    editor = WorldMapEditor(config)

    editor._on_world_point(100, 50)
    editor._on_local_point(10, 5)
    editor._on_world_point(500, 250)
    editor._on_local_point(210, 105)
    calibration = editor.apply_calibration()

    assert calibration.scale == 2.0
    assert config.get("world_map", "calibration")["offset"] == [80.0, 40.0]
    assert config.saved == 1
    assert config.loaded == 1


def test_editor_ui_calibration_failure_shows_warning_without_raising(monkeypatch):
    app = QApplication.instance() or QApplication([])
    config = FakeConfig()
    editor = WorldMapEditor(config)
    warnings = []

    def fake_warning(parent, title, message):
        warnings.append((parent, title, message))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)

    editor._apply_calibration_from_ui()

    assert warnings
    assert warnings[0][0] is editor
    assert config.saved == 0


def test_editor_ui_preserves_all_image_action_timings():
    app = QApplication.instance() or QApplication([])
    config = FakeConfig()
    editor = WorldMapEditor(config)
    editor._template_path.setText("target.png")
    editor._hold_sec.setValue(0.7)
    editor._repeat_interval.setValue(0.4)
    editor._wait_after.setValue(1.2)

    editor._save_trigger_from_ui()

    action = config.get("attack", "image_trigger")["action"]
    assert action["hold_sec"] == 0.7
    assert action["repeat_interval_sec"] == 0.4
    assert action["wait_after_sec"] == 1.2


def test_editor_sets_world_map_image_from_user_file(tmp_path):
    app = QApplication.instance() or QApplication([])
    config = FakeConfig()
    image_path = tmp_path / "world-map.png"
    QImage(640, 360, QImage.Format.Format_RGB32).save(str(image_path))
    editor = WorldMapEditor(config)

    editor.set_world_map_image(str(image_path))

    world = config.get("world_map")
    assert world["enabled"] is True
    assert world["image_path"] == str(image_path)
    assert world["image_width"] == 640
    assert world["image_height"] == 360
    assert editor.findChild(QPushButton, "worldMapImageButton") is not None


def test_editor_canvas_tools_create_waypoint_and_action_node():
    app = QApplication.instance() or QApplication([])
    config = FakeConfig()
    editor = WorldMapEditor(config)

    editor.set_edit_tool("waypoint")
    editor._on_world_point(100, 80)
    editor.set_edit_tool("action")
    editor._action_key.setText("up")
    editor._on_world_point(180, 80)

    nodes = config.get("navigation", "nodes")
    assert [node["kind"] for node in nodes] == ["waypoint", "action"]
    assert nodes[1]["action"]["key"] == "up"


def test_editor_connect_tool_creates_edge_between_clicked_nodes():
    app = QApplication.instance() or QApplication([])
    config = FakeConfig()
    config.data["navigation"]["nodes"] = [
        {"id": "node-001", "kind": "waypoint", "x": 10.0, "y": 20.0},
        {"id": "node-002", "kind": "waypoint", "x": 90.0, "y": 20.0},
    ]
    editor = WorldMapEditor(config)

    editor.set_edit_tool("connect")
    editor._on_world_point(10, 20)
    editor._on_world_point(90, 20)

    edges = config.get("navigation", "edges")
    assert edges == [{
        "id": "edge-001",
        "from_id": "node-001",
        "to_id": "node-002",
        "traversal": "walk",
    }]
