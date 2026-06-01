# 미니맵 클릭 픽커 — 표시 클릭좌표 → 미니맵 상대좌표 환산 검증
from core_ui.shot_selector import display_to_point


def test_no_scale_identity():
    assert display_to_point(40, 30, scale=1.0) == (40, 30)


def test_scaled_display():
    # 50% 축소표시면 클릭좌표 ×2 가 원본 미니맵 좌표
    assert display_to_point(40, 30, scale=0.5) == (80, 60)


def test_rounding():
    x, y = display_to_point(33, 21, scale=0.5)
    assert x == 66 and y == 42
