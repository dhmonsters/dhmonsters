# 설정 캐릭터색(RGB)→HSV 범위 변환 검증(밝고 진한 점만 골라내는 빡빡한 하한)
from core.sensing.char_scanner import hsv_range_from_rgb


def test_yellow_rgb_to_hsv_matches_proven_range():
    lo, hi = hsv_range_from_rgb(225, 225, 0)   # 노랑 → H≈30
    # 검증된 기본 노란 범위((20,100,200)~(40,255,255))와 동일해야 한다
    assert lo == (20, 100, 200)
    assert hi == (40, 255, 255)


def test_dim_background_excluded():
    # 칙칙한 배경색(낮은 V)은 범위에서 제외돼야 밝은 점만 잡힌다
    lo, hi = hsv_range_from_rgb(225, 225, 0)
    h, s, v = 30, 120, 150   # 어두운 노란계열(배경)
    assert not (lo[2] <= v)   # v_min=200 > 150 → 제외


def test_hue_centers_on_color():
    lo, hi = hsv_range_from_rgb(255, 0, 0)   # 빨강 H≈0 → 하한 0 클램프
    assert lo[0] == 0
    assert hi[0] == 10
