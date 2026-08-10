# CharScanner의 HSV 위치 감지(순수 함수)를 합성 이미지로 검증 (C vision.py 방식)
import numpy as np
import pytest
from core.sensing.char_scanner import CharScanner, find_char_in_hsv
from core.sensing.coordinate_history import CoordinateHistory


def _img_with_yellow_block(w=200, h=120, cx=50, cy=40, size=10):
    """배경(검정) 위에 노란색 블록 하나를 그린 BGR 이미지."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    # 노란색 BGR = (0, 255, 255)
    img[cy - size // 2: cy + size // 2, cx - size // 2: cx + size // 2] = (0, 255, 255)
    return img


# C vision.py 기본 노란색 HSV 범위(20~40 H)
HSV_LO = (20, 100, 200)
HSV_HI = (40, 255, 255)


def test_finds_yellow_block_center():
    img = _img_with_yellow_block(cx=50, cy=40, size=10)
    pos = find_char_in_hsv(img, HSV_LO, HSV_HI, min_area=10, max_area=10000)
    assert pos is not None
    x, y = pos
    assert abs(x - 50) <= 2 and abs(y - 40) <= 2  # 무게중심 ≈ 블록 중심


def test_returns_none_when_no_yellow():
    img = np.zeros((120, 200, 3), dtype=np.uint8)  # 전부 검정
    pos = find_char_in_hsv(img, HSV_LO, HSV_HI, min_area=10, max_area=10000)
    assert pos is None


def test_area_filter_rejects_too_small():
    """min_area보다 작은 노이즈는 무시."""
    img = _img_with_yellow_block(size=2)  # 4px
    pos = find_char_in_hsv(img, HSV_LO, HSV_HI, min_area=50, max_area=10000)
    assert pos is None


def test_area_filter_rejects_too_big():
    """max_area보다 큰 덩어리는 무시(배경 오염 방지)."""
    img = _img_with_yellow_block(size=60)
    pos = find_char_in_hsv(img, HSV_LO, HSV_HI, min_area=10, max_area=100)
    assert pos is None


def test_char_scanner_uses_30ms_interval():
    assert CharScanner.interval == 0.03


def test_coordinate_history_keeps_latest_ten_samples():
    history = CoordinateHistory(maxlen=10)
    for index in range(12):
        history.append((index, 40), observed_at=float(index), scan_duration_sec=0.01)
    samples = history.snapshot()
    assert len(samples) == 10
    assert samples[0].position == (2, 40)
    assert history.latest().position == (11, 40)
