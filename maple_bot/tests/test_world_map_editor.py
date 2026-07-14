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
