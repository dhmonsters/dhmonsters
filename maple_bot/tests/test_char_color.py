# 설정 캐릭터색(RGB)→느슨한 HSV 범위 변환 검증
from core.sensing.char_scanner import hsv_range_from_rgb


def test_yellow_rgb_to_loose_hsv():
    lo, hi = hsv_range_from_rgb(225, 225, 0)   # 노랑 → H≈30
    assert lo == (18, 60, 60)
    assert hi == (42, 255, 255)


def test_sv_floor_is_loose_so_dim_dot_passes():
    # 하한 S/V가 60이라, 약간 어두운/흐린 노란점(예 HSV V=180,S=200)도 범위에 든다
    lo, hi = hsv_range_from_rgb(225, 225, 0)
    h, s, v = 30, 200, 180
    assert lo[0] <= h <= hi[0] and lo[1] <= s and lo[2] <= v


def test_hue_clamped():
    lo, hi = hsv_range_from_rgb(255, 0, 0)   # 빨강 H≈0 → 하한 0 클램프
    assert lo[0] == 0
