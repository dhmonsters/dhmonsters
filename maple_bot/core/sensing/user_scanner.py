# UserScanner — 미니맵 빨강 픽셀(타 유저)을 HSV로 감지 → user_detected (C UserScanner 방식)
from __future__ import annotations

import cv2
import numpy as np

from core.sensing.event import Event
from core.sensing.scanner import Scanner

# 빨강 HSV 두 구간(0근처 + 180근처) — 색상환 양끝
_RED1_LO = np.array([0, 120, 120]);   _RED1_HI = np.array([10, 255, 255])
_RED2_LO = np.array([170, 120, 120]); _RED2_HI = np.array([180, 255, 255])


def count_red_pixels(bgr_img: np.ndarray) -> int:
    """이미지의 빨강 픽셀 수 (타 유저 닉네임/도트)."""
    hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
    m1 = cv2.inRange(hsv, _RED1_LO, _RED1_HI)
    m2 = cv2.inRange(hsv, _RED2_LO, _RED2_HI)
    return int(cv2.countNonZero(cv2.bitwise_or(m1, m2)))


class UserScanner(Scanner):
    """미니맵에서 빨강(타 유저)을 감지. min_red 초과 출현 순간 user_detected 1회 발행."""
    interval = 0.5

    def __init__(self, screen_capture, min_red: int = 15, region: dict | None = None):
        super().__init__()
        self._capture = screen_capture
        self._min_red = min_red
        self._region = region
        self._present = False

    def scan_once(self) -> Event | None:
        img = self._capture(self._region) if self._region else self._capture()
        if img is None:
            return None
        red = count_red_pixels(img)
        detected = red >= self._min_red
        if detected and not self._present:
            self._present = True
            return Event(type="user_detected", data={"red": red})
        if not detected and self._present:
            self._present = False
        return None
