# 미니맵↔캔버스 좌표 변환 + 범위 환산 + 추적 상태 순수 함수 검증
from core_ui.minimap_geom import (
    minimap_to_canvas, screen_px_to_minimap_px, char_track_state,
)


def test_minimap_to_canvas_zoom_and_pan():
    assert minimap_to_canvas(10, 20, 1.0) == (10, 20)
    assert minimap_to_canvas(10, 20, 2.0) == (20, 40)
    assert minimap_to_canvas(10, 20, 2.0, pan=(5, -3)) == (25, 37)


def test_screen_px_to_minimap_px_proportional():
    # factor = camera_w_ratio*minimap_w/screen_w = 0.5*200/1000 = 0.1
    assert screen_px_to_minimap_px(35, 200, 1000, 0.5) == 3.5
    assert screen_px_to_minimap_px(70, 200, 1000, 0.5) == 7.0   # 2배 입력→2배 출력


def test_screen_px_to_minimap_px_guards_zero_screen():
    assert screen_px_to_minimap_px(35, 200, 0, 0.5) == 0.0


def test_char_track_state_thresholds():
    # 미검출 경과시간(초) → 추적 상태
    assert char_track_state(0.0) == "tracking"
    assert char_track_state(0.9) == "tracking"
    assert char_track_state(1.0) == "lost"      # 경계: lost_after 이상
    assert char_track_state(2.5) == "lost"
    assert char_track_state(3.0) == "stale"     # 경계: stale_after 이상
    assert char_track_state(10.0) == "stale"


def test_char_track_state_custom_thresholds():
    assert char_track_state(0.4, lost_after=0.5, stale_after=2.0) == "tracking"
    assert char_track_state(1.0, lost_after=0.5, stale_after=2.0) == "lost"
    assert char_track_state(2.0, lost_after=0.5, stale_after=2.0) == "stale"
