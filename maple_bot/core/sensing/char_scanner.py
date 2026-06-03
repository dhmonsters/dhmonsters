# CharScanner — 미니맵에서 캐릭터 위치를 HSV+면적필터로 감지 (C vision.py 방식 채택)
from __future__ import annotations

import cv2
import numpy as np

from core.sensing.event import Event
from core.sensing.scanner import Scanner


def hsv_range_from_rgb(r: int, g: int, b: int,
                       h_tol: int = 12, s_min: int = 60, v_min: int = 60):
    """캐릭터색 RGB → 느슨한 HSV (하한, 상한). 미니맵 점이 다소 어둡/흐려도 잡히게
    S/V 하한을 낮춘다. H는 ±h_tol. (설정 char_r/g/b를 그대로 감지에 쓰기 위함)"""
    h = int(cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV)[0, 0, 0])
    return ((max(0, h - h_tol), s_min, v_min), (min(179, h + h_tol), 255, 255))


def find_char_in_hsv(
    bgr_img: np.ndarray,
    hsv_lower: tuple[int, int, int],
    hsv_upper: tuple[int, int, int],
    min_area: float,
    max_area: float,
) -> tuple[int, int] | None:
    """BGR 이미지에서 HSV 범위에 맞는 가장 큰 유효 덩어리의 무게중심(x, y) 반환.

    C vision._detect_in_region 방식: inRange → contour → 면적필터 → moments.
    A의 RGB 거리매칭보다 조명/배경에 강함(카테고리1 채택 근거).
    """
    hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lower), np.array(hsv_upper))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best = None
    best_area = 0.0
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue
        if area > best_area:
            best_area = area
            best = c
    if best is None:
        return None

    m = cv2.moments(best)
    if m["m00"] == 0:
        return None
    cx = int(m["m10"] / m["m00"])
    cy = int(m["m01"] / m["m00"])
    return cx, cy


class CharScanner(Scanner):
    """미니맵 영역을 주기 캡처해 캐릭터 위치를 감지, char_pos 이벤트 발행.

    위치가 바뀐 경우에만 push(큐 스팸 방지)는 Orchestrator 정책에 맡기고,
    여기서는 매 감지마다 발행한다(공유 위치상태 갱신용).
    """
    interval = 0.05

    def __init__(self, screen_capture, region,
                 hsv_lower=(20, 100, 200), hsv_upper=(40, 255, 255),
                 min_area: float = 6, max_area: float = 4000):
        super().__init__()
        self._capture = screen_capture   # callable(region) -> BGR ndarray
        self._region = region
        self._lo = hsv_lower
        self._hi = hsv_upper
        self._min_area = min_area
        self._max_area = max_area

    def set_hsv(self, lower, upper) -> None:
        """맵별 HSV 오버라이드 (C set_hsv_override)."""
        self._lo, self._hi = lower, upper

    def scan_once(self) -> Event | None:
        region = self._region() if callable(self._region) else self._region
        img = self._capture(region)
        if img is None:
            return None
        pos = find_char_in_hsv(img, self._lo, self._hi, self._min_area, self._max_area)
        if pos is None:
            return None
        return Event(type="char_pos", data={"x": pos[0], "y": pos[1]})
