# CharScanner — 미니맵에서 캐릭터 위치를 HSV+면적필터로 감지 (C vision.py 방식 채택)
from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
import sys
import threading
import time

from core.internal_trace import trace_event
from core.sensing.event import Event
from core.sensing.scanner import Scanner
from core.sensing.coordinate_history import CoordinateHistory, CoordinateSample


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
    previous_position: tuple[int, int] | None = None,
) -> tuple[int, int] | None:
    """BGR 이미지에서 헌터 방식으로 캐릭터 노란점을 찾아 미니맵 좌표를 반환한다."""
    img_hsv = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(img_hsv, np.array(hsv_lower), np.array(hsv_upper))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    valid_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not (min_area <= area <= max_area):
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w <= 0 or h <= 0:
            continue
        aspect = max(w / h, h / w)
        if aspect > 1.9:
            continue
        perimeter = cv2.arcLength(contour, True)
        circularity = 0.0 if perimeter <= 0 else (4.0 * np.pi * area / (perimeter * perimeter))
        if circularity < 0.35:
            continue
        valid_contours.append((contour, area, circularity))

    if not valid_contours:
        return None

    def _center(contour):
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            return None
        return (
            int(moments["m10"] / moments["m00"] + 0.5),
            int(moments["m01"] / moments["m00"] + 0.5),
        )

    candidates = []
    for contour, area, circularity in valid_contours:
        center = _center(contour)
        if center is None:
            continue
        if previous_position is None:
            distance_score = 0.0
        else:
            distance_score = float(np.hypot(center[0] - previous_position[0], center[1] - previous_position[1]))
        candidates.append((contour, center, area, circularity, distance_score))

    if not candidates:
        return None

    if previous_position is not None:
        near_candidates = [item for item in candidates if item[4] <= 80.0]
        if near_candidates:
            best_contour, (cx, cy), _area, _circularity, _distance = min(
                near_candidates,
                key=lambda item: (item[4], -item[2], -item[3]),
            )
            return cx, cy

    best_contour, (cx, cy), _area, _circularity, _distance = max(
        candidates,
        key=lambda item: (item[2], item[3]),
    )
    moments = cv2.moments(best_contour)
    if moments["m00"] == 0:
        return None

    return cx, cy


def _resource_path(*parts: str) -> Path:
    """EXE와 소스 실행 모두에서 템플릿 파일 위치를 찾는다."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base.joinpath(*parts)


def _load_marker_templates() -> list[tuple[str, np.ndarray]]:
    """미니맵 캐릭터 마커 템플릿을 로드한다."""
    templates: list[tuple[str, np.ndarray]] = []
    for name in ("y_p.png", "r_p.png"):
        path = _resource_path("templates", "player", name)
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is not None and img.size > 0:
            templates.append((name, img))
    return templates


def find_char_by_template(
    bgr_img: np.ndarray,
    templates: list[tuple[str, np.ndarray]],
    threshold: float = 0.72,
    excluded_regions: tuple[tuple[int, int, int, int], ...] = (),
    timing_out: dict[str, float] | None = None,
) -> tuple[int, int] | None:
    """미니맵 안에서 고정 캐릭터 마커 템플릿을 찾아 중심 좌표를 반환한다."""
    if timing_out is not None:
        timing_out.clear()
        timing_out.update(template_match_sec=0.0, candidate_filter_sec=0.0)
    if bgr_img is None or not templates:
        return None
    best: tuple[float, int, int] | None = None
    template_match_sec = 0.0
    candidate_filter_sec = 0.0
    img_h, img_w = bgr_img.shape[:2]
    for _name, template in templates:
        th, tw = template.shape[:2]
        if th <= 0 or tw <= 0:
            continue
        for scale in (0.8, 0.9, 1.0, 1.1, 1.2, 1.35):
            sw = max(1, int(round(tw * scale)))
            sh = max(1, int(round(th * scale)))
            if sw > img_w or sh > img_h:
                continue
            match_started = time.perf_counter()
            scaled = cv2.resize(template, (sw, sh), interpolation=cv2.INTER_AREA)
            result = cv2.matchTemplate(bgr_img, scaled, cv2.TM_CCOEFF_NORMED)
            template_match_sec += time.perf_counter() - match_started
            candidate_started = time.perf_counter()
            while result.size:
                _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
                if max_val < threshold:
                    break
                cx = int(max_loc[0] + sw / 2)
                cy = int(max_loc[1] + sh / 2)
                if any(x1 <= cx <= x2 and y1 <= cy <= y2
                       for x1, y1, x2, y2 in excluded_regions):
                    result[max_loc[1], max_loc[0]] = -1.0
                    continue
                if best is None or max_val > best[0]:
                    best = (float(max_val), cx, cy)
                break
            candidate_filter_sec += time.perf_counter() - candidate_started
    if timing_out is not None:
        timing_out.update(
            template_match_sec=template_match_sec,
            candidate_filter_sec=candidate_filter_sec,
        )
    if best is None or best[0] < threshold:
        return None
    return best[1], best[2]

class CharScanner(Scanner):
    """미니맵 영역을 주기 캡처해 캐릭터 위치를 감지, char_pos 이벤트 발행.

    위치가 바뀐 경우에만 push(큐 스팸 방지)는 Orchestrator 정책에 맡기고,
    여기서는 매 감지마다 발행한다(공유 위치상태 갱신용).
    """
    interval = 0.03

    def __init__(self, screen_capture, region,
                 hsv_lower=(20, 100, 200), hsv_upper=(40, 255, 255),
                 min_area: float = 3, max_area: float = 100,
                 log_fn=None, position_store=None,
                 marker_exclusions: tuple[tuple[int, int, int, int], ...] = ()):
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
        self._last_position_log_ts = 0.0
        self._position_lock = threading.Lock()
        self._scan_lock = threading.Lock()
        self._last_position: tuple[int, int] | None = None
        self._last_position_at: float | None = None
        self._history = CoordinateHistory(maxlen=10)
        self._position_store = position_store
        self._marker_templates = _load_marker_templates()
        self._marker_exclusions = marker_exclusions

    def position(self) -> tuple[int, int] | None:
        """이벤트 큐 처리와 무관하게 읽을 수 있는 최신 캐릭터 좌표."""
        with self._position_lock:
            return self._last_position

    def position_ratio(self) -> tuple[float, float] | None:
        """최신 위치를 현재 미니맵 내부 0~1 비율로 반환한다."""
        with self._position_lock:
            position = self._last_position
        if position is None:
            return None
        region = self._region() if callable(self._region) else self._region
        if not region:
            return None
        width = max(1, int(region.get("width", 0)))
        height = max(1, int(region.get("height", 0)))
        return position[0] / width, position[1] / height

    def set_hsv(self, lower, upper) -> None:
        """맵별 HSV 오버라이드 (C set_hsv_override)."""
        self._lo, self._hi = lower, upper

    def set_filters(self, lower, upper, min_area: float | None = None, max_area: float | None = None) -> None:
        """HSV와 점 크기 필터를 함께 갱신한다."""
        self._lo, self._hi = lower, upper
        if min_area is not None:
            self._min_area = float(min_area)
        if max_area is not None:
            self._max_area = float(max_area)

    def reload_marker_templates(self) -> None:
        """디스크에 저장된 캐릭터 마커 템플릿을 다시 로드한다."""
        templates = _load_marker_templates()
        with self._scan_lock:
            self._marker_templates = templates

    def sample(self) -> tuple[tuple[int, int] | None, float | None]:
        with self._position_lock:
            return self._last_position, self._last_position_at

    def latest_sample(self) -> CoordinateSample | None:
        return self._history.latest()

    def history(self) -> tuple[CoordinateSample, ...]:
        return self._history.snapshot()

    def position_age(self, now: float | None = None) -> float | None:
        with self._position_lock:
            seen_at = self._last_position_at
        if seen_at is None:
            return None
        return max(0.0, (time.monotonic() if now is None else now) - seen_at)

    def _diag(self, msg: str) -> None:
        """진단 로그 — 같은 메시지는 1.5초에 한 번만(폭주 방지)."""
        import time as _t
        now = _t.monotonic()
        if msg == self._last_log and now - self._last_log_ts < 1.5:
            return
        self._last_log, self._last_log_ts = msg, now
        self._log(msg)

    def scan_once(self) -> Event | None:
        with self._scan_lock:
            return self._scan_once_locked()

    def _loop(self) -> None:
        """한 스캔의 처리시간을 포함해 시작 간격이 약 30ms가 되도록 실행한다."""
        while not self._stop.is_set():
            cycle_started = time.monotonic()
            try:
                ev = self.scan_once()
                if ev is not None and self._queue is not None:
                    self._queue.put(ev)
            except Exception:
                pass
            elapsed = time.monotonic() - cycle_started
            self._stop.wait(max(0.0, self.interval - elapsed))

    def refresh_position(self):
        """사다리 출발점 확인용으로 캡처를 즉시 한 번 실행하고 최신 좌표를 반환한다."""
        self.scan_once()
        return self.sample()

    def detect_position_once(self):
        """버튼 확인용으로 즉시 1회 캡처하고, 이번 감지에 성공한 좌표만 반환한다."""
        ev = self.scan_once()
        if ev is None:
            return None, None
        data = getattr(ev, "data", {}) or {}
        try:
            return (int(data["x"]), int(data["y"])), data.get("observed_at")
        except Exception:
            return None, None

    def _scan_once_locked(self) -> Event | None:
        scan_started = time.monotonic()
        region = self._region() if callable(self._region) else self._region
        capture_started = time.perf_counter()
        try:
            img = self._capture(region)
        except Exception as e:
            self._diag(f"⚠ 미니맵 캡처 예외(스캐너 스레드): {e!r}")
            return None
        if img is None:
            self._diag("⚠ 미니맵 캡처 결과 None")
            return None
        capture_sec = time.perf_counter() - capture_started
        template_timing: dict[str, float] = {}
        pos = find_char_by_template(
            img,
            self._marker_templates,
            excluded_regions=self._marker_exclusions,
            timing_out=template_timing,
        )
        hsv_candidate_sec = 0.0
        if pos is None and not self._marker_templates:
            hsv_started = time.perf_counter()
            pos = find_char_in_hsv(
                img, self._lo, self._hi, self._min_area, self._max_area,
                previous_position=self.position(),
            )
            hsv_candidate_sec = time.perf_counter() - hsv_started
        if pos is None:
            self._diag(f"⚠ 노란점 미검출 (캡처 {tuple(img.shape)}, HSV {tuple(self._lo)}~{tuple(self._hi)})")
            return None
        observed_at = time.monotonic()
        scan_duration = observed_at - scan_started
        image_height, image_width = img.shape[:2]
        with self._position_lock:
            previous_position = self._last_position
        if previous_position is not None:
            jump_distance = (
                (float(pos[0]) - float(previous_position[0])) ** 2
                + (float(pos[1]) - float(previous_position[1])) ** 2
            ) ** 0.5
            jump_threshold = max(30.0, min(image_width, image_height) * 0.35)
            if jump_distance > jump_threshold:
                pending = getattr(self, "_pending_jump_position", None)
                confirm_radius = max(8.0, min(image_width, image_height) * 0.08)
                pending_matches = pending is not None and (
                    (float(pos[0]) - float(pending[0])) ** 2
                    + (float(pos[1]) - float(pending[1])) ** 2
                ) ** 0.5 <= confirm_radius
                if not pending_matches:
                    self._pending_jump_position = pos
                    trace_event(
                        "character",
                        "position_rejected",
                        reason="transient_jump",
                        previous_x=previous_position[0],
                        previous_y=previous_position[1],
                        candidate_x=pos[0],
                        candidate_y=pos[1],
                        jump_distance=jump_distance,
                        threshold=jump_threshold,
                    )
                    return None
                trace_event(
                    "character",
                    "position_selected",
                    reason="confirmed_jump",
                    x=pos[0],
                    y=pos[1],
                    jump_distance=jump_distance,
                )
        self._pending_jump_position = None
        x_ratio = pos[0] / max(1, image_width)
        y_ratio = pos[1] / max(1, image_height)
        trace_event(
            "character",
            "position_selected",
            x=pos[0],
            y=pos[1],
            x_ratio=x_ratio,
            y_ratio=y_ratio,
            minimap_width=image_width,
            minimap_height=image_height,
            scan_duration_sec=scan_duration,
            capture_sec=capture_sec,
            template_match_sec=template_timing.get("template_match_sec", 0.0),
            candidate_filter_sec=(
                template_timing.get("candidate_filter_sec", 0.0) + hsv_candidate_sec
            ),
            total_scan_sec=scan_duration,
        )
        with self._position_lock:
            self._last_position = pos
            self._last_position_at = observed_at
        sample = self._history.append(pos, observed_at, scan_duration)
        if self._position_store is not None:
            self._position_store.publish(pos[0], pos[1], observed_at)
        now = time.monotonic()
        if now - self._last_position_log_ts >= 1.0:
            self._last_position_log_ts = now
            self._diag(
                f"✓ 캐릭터 감지 x={pos[0]} y={pos[1]} "
                f"ratio=({x_ratio:.4f},{y_ratio:.4f}) minimap={image_width}x{image_height}"
            )
        return Event(type="char_pos", data={
            "x": pos[0],
            "y": pos[1],
            "x_ratio": x_ratio,
            "y_ratio": y_ratio,
            "sequence": sample.sequence,
            "observed_at": sample.observed_at,
            "scan_duration_sec": sample.scan_duration_sec,
        })

