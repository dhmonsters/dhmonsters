# 전역 지도 편집기의 노드와 이미지 트리거 설정 저장을 검증하는 테스트
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

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
