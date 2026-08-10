# CharScanner의 HSV 위치 감지(순수 함수)를 합성 이미지로 검증 (C vision.py 방식)
import numpy as np
import pytest
from core.sensing.char_scanner import CharScanner, find_char_in_hsv
from core.sensing.coordinate_history import CoordinateHistory
from core.runtime import RuntimeConfig


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


def test_default_filter_accepts_deployed_round_marker_size():
    """배포 화면의 반지름 7 노란 마커를 기본 점 크기 범위가 탈락시키지 않는다."""
    import cv2

    image = np.zeros((39, 43, 3), dtype=np.uint8)
    cv2.circle(image, (29, 12), 7, (0, 225, 225), -1)
    config = RuntimeConfig(minimap_region={"left": 0, "top": 0, "width": 172, "height": 103})

    position = find_char_in_hsv(
        image,
        HSV_LO,
        HSV_HI,
        min_area=config.char_area_min,
        max_area=config.char_area_max,
    )

    assert position == (29, 12)


def test_even_width_marker_centroid_rounds_to_nearest_pixel():
    """X 중심이 28.5인 마커를 항상 왼쪽 28로 버리지 않는다."""
    yy, xx = np.ogrid[:39, :43]
    marker = (((xx - 28.5) / 6.5) ** 2 + ((yy - 12.0) / 6.0) ** 2) <= 1.0
    image = np.zeros((39, 43, 3), dtype=np.uint8)
    image[marker] = (0, 225, 225)

    position = find_char_in_hsv(image, HSV_LO, HSV_HI, min_area=3, max_area=160)

    assert position == (29, 12)


def test_default_filter_still_rejects_larger_round_background_object():
    """캐릭터보다 큰 원형 배경 물체는 기본 최대 면적에서 제외한다."""
    import cv2

    image = np.zeros((39, 43, 3), dtype=np.uint8)
    cv2.circle(image, (29, 18), 10, (0, 225, 225), -1)
    config = RuntimeConfig(minimap_region={"left": 0, "top": 0, "width": 172, "height": 103})

    position = find_char_in_hsv(
        image,
        HSV_LO,
        HSV_HI,
        min_area=config.char_area_min,
        max_area=config.char_area_max,
    )

    assert position is None


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
