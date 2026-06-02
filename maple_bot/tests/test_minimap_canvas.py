# MinimapCanvas — 실시간 캡처·캐릭터 투영·추적상태·에러표시 offscreen 스모크
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication
from core_ui.minimap_canvas import MinimapCanvas


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeConfig:
    def __init__(self, data=None): self._d = data or {}
    def get(self, *keys, default=None):
        node = self._d
        for k in keys:
            if not isinstance(node, dict) or k not in node:
                return default
            node = node[k]
        return node


def _region_cfg():
    return FakeConfig({"minimap": {"region_x": 0, "region_y": 0,
                                   "width": 200, "height": 120}})


def test_tick_detects_char_and_paints(app):
    cfg = _region_cfg()
    shot = np.zeros((120, 200, 3), dtype=np.uint8)
    cv = MinimapCanvas(cfg, screen_capture=lambda r: shot,
                       char_finder=lambda *a, **k: (50, 60), interval_ms=99999)
    cv.resize(300, 200)
    cv._tick()
    assert cv._last_char == (50, 60)
    cv.grab()                       # paintEvent 예외 없이 도는지


def test_region_unset_shows_hint_no_crash(app):
    cfg = FakeConfig({"minimap": {"width": 0}})
    cv = MinimapCanvas(cfg, screen_capture=lambda r: None,
                       char_finder=lambda *a, **k: (1, 1), interval_ms=99999)
    cv._tick()
    assert cv._last_char is None
    cv.grab()


def test_char_not_found_keeps_last(app):
    cfg = _region_cfg()
    shot = np.zeros((120, 200, 3), dtype=np.uint8)
    seq = [(10, 20), None]
    cv = MinimapCanvas(cfg, screen_capture=lambda r: shot,
                       char_finder=lambda *a, **k: seq.pop(0), interval_ms=99999)
    cv._tick()                      # (10,20)
    cv._tick()                      # None → 직전 유지
    assert cv._last_char == (10, 20)


def test_track_state_transitions_and_stale_renders(app):
    cfg = _region_cfg()
    shot = np.zeros((120, 200, 3), dtype=np.uint8)
    t = {"now": 100.0}
    cv = MinimapCanvas(cfg, screen_capture=lambda r: shot,
                       char_finder=lambda *a, **k: (50, 60), interval_ms=99999,
                       clock=lambda: t["now"])
    cv.resize(300, 200)
    cv._tick()                      # 검출 @100.0
    assert cv.track_state() == "tracking"
    t["now"] = 102.0
    assert cv.track_state() == "lost"
    t["now"] = 105.0
    assert cv.track_state() == "stale"
    cv.grab()                       # stale에서도 예외 없이 렌더


def test_track_state_stale_before_any_detection(app):
    cfg = _region_cfg()
    cv = MinimapCanvas(cfg, screen_capture=lambda r: None,
                       char_finder=lambda *a, **k: None, interval_ms=99999)
    assert cv.track_state() == "stale"   # 한 번도 검출 전이면 stale


def test_fit_sets_zoom_to_show_whole_minimap(app):
    cfg = _region_cfg()
    shot = np.zeros((120, 200, 3), dtype=np.uint8)
    cv = MinimapCanvas(cfg, screen_capture=lambda r: shot,
                       char_finder=lambda *a, **k: (50, 60), interval_ms=99999)
    cv.resize(400, 240)
    cv._tick()                      # _mm_size=(200,120)
    cv.fit()
    # min(400/200, 240/120) = min(2.0, 2.0) = 2.0
    assert abs(cv._zoom - 2.0) < 1e-6


def test_zoom_clamped(app):
    cfg = _region_cfg()
    cv = MinimapCanvas(cfg, screen_capture=lambda r: None,
                       char_finder=lambda *a, **k: None, interval_ms=99999)
    cv.set_zoom(99)
    assert cv._zoom == 8.0          # 상한
    cv.set_zoom(0.01)
    assert cv._zoom == 0.5          # 하한


def test_minimap_size_from_region_without_tick(app):
    cfg = _region_cfg()
    cv = MinimapCanvas(cfg, screen_capture=lambda r: None,
                       char_finder=lambda *a, **k: None, interval_ms=99999)
    assert cv.minimap_size() == (200, 120)   # 타이머 안 돌아도 _region 기반
