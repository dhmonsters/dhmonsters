# BlockEditor — 좌표 동선 블록(route) 리스트 편집 + config 저장/로드 검증
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from PyQt6.QtWidgets import QApplication
from core_ui.block_editor import BlockEditor


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeConfig:
    def __init__(self, data=None): self._d = data or {}; self.saved = 0
    def get(self, *keys, default=None):
        node = self._d
        for k in keys:
            if not isinstance(node, dict) or k not in node: return default
            node = node[k]
        return node
    def set(self, *args):
        *keys, val = args; node = self._d
        for k in keys[:-1]: node = node.setdefault(k, {})
        node[keys[-1]] = val
    def save(self): self.saved += 1


def test_loads_existing_route(app):
    cfg = FakeConfig({"floor_hunt": {"route": [
        {"type": "move", "target_x": 50, "move_type": "walk"},
        {"type": "attack", "skill_key": "a"},
    ]}})
    ed = BlockEditor(cfg, ("floor_hunt", "route"))
    assert ed.row_count() == 2


def test_add_move_block_saves(app):
    cfg = FakeConfig()
    ed = BlockEditor(cfg, ("floor_hunt", "route"))
    ed.add_block("move")
    assert ed.row_count() == 1
    route = cfg.get("floor_hunt", "route")
    assert route[0]["type"] == "move"
    assert cfg.saved >= 1


def test_add_attack_block(app):
    cfg = FakeConfig()
    ed = BlockEditor(cfg, ("floor_hunt", "route"))
    ed.add_block("attack")
    assert cfg.get("floor_hunt", "route")[0]["type"] == "attack"


def test_remove_block(app):
    cfg = FakeConfig({"floor_hunt": {"route": [
        {"type": "move", "target_x": 10}, {"type": "attack", "skill_key": "a"}]}})
    ed = BlockEditor(cfg, ("floor_hunt", "route"))
    ed.remove_row(0)
    assert ed.row_count() == 1
    assert cfg.get("floor_hunt", "route")[0]["type"] == "attack"


def test_edit_target_x_persists(app):
    cfg = FakeConfig()
    ed = BlockEditor(cfg, ("floor_hunt", "route"))
    ed.add_block("move")
    ed.set_field(0, "target_x", 120)
    assert cfg.get("floor_hunt", "route")[0]["target_x"] == 120
