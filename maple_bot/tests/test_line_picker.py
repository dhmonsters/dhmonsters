# 라인 드래그 픽커 — 시작→끝 두 점 동시 환산 검증
from core_ui.shot_selector import display_to_point


def test_two_points_scaled():
    # 50% 축소표시 → 두 점 모두 ×2
    s = display_to_point(20, 30, scale=0.5)
    e = display_to_point(80, 30, scale=0.5)
    assert s == (40, 60) and e == (160, 60)


def test_line_picker_importable():
    from core_ui.shot_selector import LinePointPicker
    assert LinePointPicker is not None
