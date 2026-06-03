# CharScanner — 미니맵에서 캐릭터 위치를 HSV+면적필터로 감지 (C vision.py 방식 채택)
from __future__ import annotations

import cv2
import numpy as np

from core.sensing.event import Event
from core.sensing.scanner import Scanner


def hsv_range_from_rgb(r: int, g: int, b: int,
                       h_tol: int = 10, s_min: int = 100, v_min: int = 200):
    """캐릭터색 RGB → HSV (하한, 상한). H는 색상 ±h_tol, S/V는 높은 하한으로 밝고 진한
    점만 골라낸다(미니맵 배경의 칙칙한 색 제외 — 검증된 기본값과 동일). 설정 char_r/g/b 반영용."""
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
                 min_area: float = 6, max_area: float = 4000,
                 log_fn=None):
        super().__init__()
        self._capture = screen_capture   # callable(region) -> BGR ndarray
        self._region = region
        self._lo = hsv_lower
        self._hi = hsv_upper
        self._min_area = min_area
        self._max_area = max_area
        self._log = log_fn or (lambda m: None)   # 스캐너 스레드 진단용(예외/검출 결과)
        self._last_log = None
        self._last_log_ts = 0.0

    def set_hsv(self, lower, upper) -> None:
        """맵별 HSV 오버라이드 (C set_hsv_override)."""
        self._lo, self._hi = lower, upper

    def _diag(self, msg: str) -> None:
        """진단 로그 — 같은 메시지는 1.5초에 한 번만(폭주 방지)."""
        import time as _t
        now = _t.monotonic()
        if msg == self._last_log and now - self._last_log_ts < 1.5:
            return
        self._last_log, self._last_log_ts = msg, now
        self._log(msg)

    def scan_once(self) -> Event | None:
        region = self._region() if callable(self._region) else self._region
        try:
            img = self._capture(region)
        except Exception as e:
            self._diag(f"⚠ 미니맵 캡처 예외(스캐너 스레드): {e!r}")
            return None
        if img is None:
            self._diag("⚠ 미니맵 캡처 결과 None")
            return None
        pos = find_char_in_hsv(img, self._lo, self._hi, self._min_area, self._max_area)
        if pos is None:
            self._diag(f"⚠ 노란점 미검출 (캡처 {tuple(img.shape)}, HSV {tuple(self._lo)}~{tuple(self._hi)})")
            return None
        self._diag(f"✓ 캐릭터 감지 x={pos[0]} y={pos[1]}")
        return Event(type="char_pos", data={"x": pos[0], "y": pos[1]})
