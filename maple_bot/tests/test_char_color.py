# 설정 캐릭터색(RGB)→HSV 범위 변환 검증(밝고 진한 점만 골라내는 빡빡한 하한)
import cv2
import numpy as np

from core.sensing.char_scanner import auto_hsv_range_from_rgb, hsv_range_from_rgb


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


def test_auto_hsv_range_uses_reference_s_and_v_minus_forty():
    lo, hi = auto_hsv_range_from_rgb(220, 210, 20)
    hsv = cv2.cvtColor(np.uint8([[[20, 210, 220]]]), cv2.COLOR_BGR2HSV)[0, 0]

    assert lo == (
        max(0, int(hsv[0]) - 10),
        max(0, int(hsv[1]) - 40),
        max(0, int(hsv[2]) - 40),
    )
    assert hi == (min(179, int(hsv[0]) + 10), 255, 255)
