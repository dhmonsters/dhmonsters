# UserScanner — 미니맵 빨강 픽셀(타 유저) 감지 → user_detected 이벤트 (C UserScanner 방식)
import numpy as np
import pytest
from core.sensing.user_scanner import UserScanner, count_red_pixels


def _img(red_pixels=0, w=200, h=120):
    """빨강(타유저) 픽셀을 red_pixels개 심은 미니맵. 나머지는 검정."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    if red_pixels:
        n = int(red_pixels ** 0.5) + 1
        # BGR 빨강 (0,0,255)
        img[0:n, 0:n] = (0, 0, 255)
    return img


def test_count_red_detects_red():
    img = _img(red_pixels=100)
    assert count_red_pixels(img) > 0


def test_count_red_zero_on_black():
    assert count_red_pixels(_img(0)) == 0


def test_user_detected_when_red_exceeds_min():
    scanner = UserScanner(lambda r=None: _img(100), min_red=10)
    ev = scanner.scan_once()
    assert ev is not None and ev.type == "user_detected"


def test_no_event_below_min():
    scanner = UserScanner(lambda r=None: _img(0), min_red=10)
    assert scanner.scan_once() is None


def test_detect_fires_once_until_gone():
    """타유저 떠있는 동안 1회만 발행(C appear 패턴)."""
    frames = [_img(100), _img(100)]
    i = {"n": 0}
    def cap(r=None):
        f = frames[min(i["n"], 1)]; i["n"] += 1; return f
    sc = UserScanner(cap, min_red=10)
    assert sc.scan_once() is not None    # 출현
    assert sc.scan_once() is None        # 계속 있음 → 중복 안 함
