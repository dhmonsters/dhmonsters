# RouteCanvas — 클릭 배치·드래그 이동·동기화 offscreen 스모크
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication
from core_ui.minimap_canvas import RouteCanvas


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeConfig:
    def __init__(self, data=None): self._d = data or {}; self.saved = 0
    def get(self, *keys, default=None):
        node = self._d
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node
    def set(self, *args):
        *keys, val = args; node = self._d
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = val
    def save(self): self.saved += 1


def _cfg():
    return FakeConfig({"minimap": {"region_x": 0, "region_y": 0, "width": 200, "height": 120}})


def _canvas(cfg, on_changed=None):
    cv = RouteCanvas(cfg, screen_capture=lambda r: np.zeros((120, 200, 3), dtype=np.uint8),
                     char_finder=lambda *a, **k: None, interval_ms=99999,
                     on_route_changed=on_changed)
    cv.resize(400, 240)
    return cv


def test_empty_click_with_active_type_adds_block_and_resets(app):
    cfg = _cfg()
    fired = {"n": 0}
    cv = _canvas(cfg, on_changed=lambda: fired.__setitem__("n", fired["n"] + 1))
    cv.set_active_type("move")
    cv._place_or_select(70, 40)
    route = cfg.get("floor_hunt", "route")
    assert len(route) == 1 and route[0]["type"] == "move"
    assert route[0]["pos_x"] == 70 and route[0]["pos_y"] == 40
    assert cv._active_type is None          # 자동 리셋
    assert fired["n"] >= 1                   # on_route_changed 발화


def test_click_on_block_starts_drag(app):
    cfg = _cfg()
    cfg.set("floor_hunt", "route", [{"type": "attack", "pos_x": 100, "pos_y": 100}])
    cv = _canvas(cfg)
    cv._place_or_select(102, 101)            # 블록 근처 클릭
    assert cv._dragging == 0


def test_drag_translates_block(app):
    cfg = _cfg()
    cfg.set("floor_hunt", "route", [{"type": "attack", "pos_x": 100, "pos_y": 100}])
    cv = _canvas(cfg)
    cv._place_or_select(100, 100)            # 선택
    cv._drag_to(110, 108)                    # +10,+8
    cv._end_drag()
    route = cfg.get("floor_hunt", "route")
    assert (route[0]["pos_x"], route[0]["pos_y"]) == (110, 108)
    assert cv._dragging is None


def test_empty_click_without_active_type_does_nothing(app):
    cfg = _cfg()
    cv = _canvas(cfg)                        # _active_type None
    cv._place_or_select(50, 50)
    assert cfg.get("floor_hunt", "route", default=None) in (None, [])


def test_paint_does_not_crash_with_blocks(app):
    cfg = _cfg()
    cfg.set("floor_hunt", "route", [
        {"type": "attack", "pos_x": 30, "pos_y": 40},
        {"type": "attack", "pos_x": -1, "pos_y": -1},     # 미배치 — 안 그려짐
        {"type": "ladder", "ladder_x": 120, "y_top": 20, "y_bot": 90},
    ])
    cv = _canvas(cfg)
    cv._tick()                               # _shot 세팅
    cv.grab()                                # paintEvent 예외 없이
