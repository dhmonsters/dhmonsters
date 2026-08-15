# CharScanner — 미니맵에서 캐릭터 위치를 HSV+면적필터로 감지 (C vision.py 방식 채택)
from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
import sys
import threading
import time

from core.config_manager import get_user_templates_dir
from core.internal_trace import trace_event
from core.sensing.event import Event
from core.sensing.scanner import Scanner
from core.sensing.coordinate_history import CoordinateHistory, CoordinateSample


MIN_MARKER_TEMPLATE_SIDE = 8


def hsv_range_from_rgb(r: int, g: int, b: int,
                       h_tol: int = 10, s_min: int = 100, v_min: int = 200):
    """캐릭터색 RGB → HSV (하한, 상한). H는 색상 ±h_tol, S/V는 높은 하한으로 밝고 진한
    점만 골라낸다(미니맵 배경의 칙칙한 색 제외 — 검증된 기본값과 동일). 설정 char_r/g/b 반영용."""
    h = int(cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV)[0, 0, 0])
    return ((max(0, h - h_tol), s_min, v_min), (min(179, h + h_tol), 255, 255))


def auto_hsv_range_from_rgb(r: int, g: int, b: int,
                            h_tol: int = 10, sv_margin: int = 40):
    """대표 RGB 한 값에서 색상·채도·밝기 허용 범위를 자동 계산한다."""
    h, s, v = (
        int(value)
        for value in cv2.cvtColor(
            np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2HSV
        )[0, 0]
    )
    return (
        (max(0, h - h_tol), max(0, s - sv_margin), max(0, v - sv_margin)),
        (min(179, h + h_tol), 255, 255),
    )


def find_char_in_hsv(
    bgr_img: np.ndarray,
    hsv_lower: tuple[int, int, int],
    hsv_upper: tuple[int, int, int],
    min_area: float,
    max_area: float,
    previous_position: tuple[int, int] | None = None,
    diagnostic_out: dict[str, object] | None = None,
) -> tuple[int, int] | None:
    """BGR 이미지에서 헌터 방식으로 캐릭터 노란점을 찾아 미니맵 좌표를 반환한다."""
    if diagnostic_out is not None:
        diagnostic_out.clear()
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

    def _record_candidate(contour) -> None:
        if diagnostic_out is not None:
            diagnostic_out["candidate_bbox"] = tuple(int(value) for value in cv2.boundingRect(contour))

    if previous_position is not None:
        near_candidates = [item for item in candidates if item[4] <= 80.0]
        if near_candidates:
            best_contour, (cx, cy), _area, _circularity, _distance = min(
                near_candidates,
                key=lambda item: (item[4], -item[2], -item[3]),
            )
            _record_candidate(best_contour)
            return cx, cy

    best_contour, (cx, cy), _area, _circularity, _distance = max(
        candidates,
        key=lambda item: (item[2], item[3]),
    )
    moments = cv2.moments(best_contour)
    if moments["m00"] == 0:
        return None

    _record_candidate(best_contour)
    return cx, cy


def _resource_path(*parts: str) -> Path:
    """EXE와 소스 실행 모두에서 템플릿 파일 위치를 찾는다."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base.joinpath(*parts)


def _load_marker_templates() -> list[tuple[str, np.ndarray]]:
    """미니맵 캐릭터 마커 템플릿을 로드한다."""
    templates: list[tuple[str, np.ndarray]] = []
    user_dir = Path(get_user_templates_dir()) / "player"
    name = "y_p.png"
    candidates = (user_dir / name, _resource_path("templates", "player", name))
    checked = set()
    for path in candidates:
        identity = str(path.resolve(strict=False)).lower()
        if identity in checked:
            continue
        checked.add(identity)
        if not path.is_file():
            continue
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is not None and img.size > 0:
            templates.append((name, img))
            break
    return templates


def _partition_marker_assets(
    templates: list[tuple[str, np.ndarray]],
) -> tuple[list[tuple[str, np.ndarray]], tuple[tuple[int, int, int], tuple[int, int, int]] | None]:
    """큰 이미지는 형태 템플릿으로, 작은 이미지는 HSV 색상 샘플로 분리한다."""
    shape_templates = []
    sample_range = None
    for name, image in templates:
        height, width = image.shape[:2]
        if height >= MIN_MARKER_TEMPLATE_SIDE and width >= MIN_MARKER_TEMPLATE_SIDE:
            shape_templates.append((name, image))
            continue
        if sample_range is None:
            pixels = image.reshape(-1, 3)
            b, g, r = (int(value) for value in np.median(pixels, axis=0))
            sample_range = auto_hsv_range_from_rgb(r, g, b, h_tol=10, sv_margin=40)
    return shape_templates, sample_range


def find_char_by_template(
    bgr_img: np.ndarray,
    templates: list[tuple[str, np.ndarray]],
    threshold: float = 0.72,
    excluded_regions: tuple[tuple[int, int, int, int], ...] = (),
    timing_out: dict[str, object] | None = None,
    previous_position: tuple[int, int] | None = None,
    search_radius: int | None = None,
) -> tuple[int, int] | None:
    """이전 위치 주변을 우선해 고정 캐릭터 마커 중심 좌표를 반환한다."""
    if timing_out is not None:
        timing_out.clear()
        timing_out.update(template_match_sec=0.0, candidate_filter_sec=0.0)
    templates = [
        (name, template)
        for name, template in templates
        if template.shape[0] >= MIN_MARKER_TEMPLATE_SIDE
        and template.shape[1] >= MIN_MARKER_TEMPLATE_SIDE
    ]
    if bgr_img is None or not templates:
        return None
    template_match_sec = 0.0
    candidate_filter_sec = 0.0
    img_h, img_w = bgr_img.shape[:2]

    def search(search_image, offset_x: int, offset_y: int):
        nonlocal template_match_sec, candidate_filter_sec
        best: tuple[float, int, int, tuple[int, int, int, int]] | None = None
        search_h, search_w = search_image.shape[:2]
        for _name, template in templates:
            th, tw = template.shape[:2]
            if th <= 0 or tw <= 0:
                continue
            for scale in (0.8, 0.9, 1.0, 1.1, 1.2, 1.35):
                sw = max(1, int(round(tw * scale)))
                sh = max(1, int(round(th * scale)))
                if sw > search_w or sh > search_h:
                    continue
                match_started = time.perf_counter()
                scaled = cv2.resize(template, (sw, sh), interpolation=cv2.INTER_AREA)
                result = cv2.matchTemplate(search_image, scaled, cv2.TM_CCOEFF_NORMED)
                template_match_sec += time.perf_counter() - match_started
                candidate_started = time.perf_counter()
                while result.size:
                    _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(result)
                    if max_val < threshold:
                        break
                    cx = int(offset_x + max_loc[0] + sw / 2)
                    cy = int(offset_y + max_loc[1] + sh / 2)
                    if any(x1 <= cx <= x2 and y1 <= cy <= y2
                           for x1, y1, x2, y2 in excluded_regions):
                        result[max_loc[1], max_loc[0]] = -1.0
                        continue
                    if best is None or max_val > best[0]:
                        best = (
                            float(max_val),
                            cx,
                            cy,
                            (offset_x + max_loc[0], offset_y + max_loc[1], sw, sh),
                        )
                    break
                candidate_filter_sec += time.perf_counter() - candidate_started
        return best

    best = None
    search_mode = "global"
    if previous_position is not None:
        radius = (
            max(12, int(round(min(img_w, img_h) * 0.20)))
            if search_radius is None
            else max(1, int(search_radius))
        )
        px, py = int(previous_position[0]), int(previous_position[1])
        left = max(0, px - radius)
        top = max(0, py - radius)
        right = min(img_w, px + radius + 1)
        bottom = min(img_h, py + radius + 1)
        if right > left and bottom > top:
            best = search(bgr_img[top:bottom, left:right], left, top)
        if best is not None:
            search_mode = "local"
    if best is None:
        best = search(bgr_img, 0, 0)
    if timing_out is not None:
        timing_out.update(
            template_match_sec=template_match_sec,
            candidate_filter_sec=candidate_filter_sec,
            search_mode=search_mode,
        )
        if best is not None:
            timing_out["candidate_bbox"] = best[3]
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
                 marker_exclusions: tuple[tuple[int, int, int, int], ...] = (),
                 position_offset: tuple[int, int] = (0, 0)):
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
        self._preview_frame: np.ndarray | None = None
        self._history = CoordinateHistory(maxlen=10)
        self._position_store = position_store
        self._marker_templates, self._marker_sample_hsv = _partition_marker_assets(
            _load_marker_templates()
        )
        self._marker_exclusions = marker_exclusions
        self._position_offset = (int(position_offset[0]), int(position_offset[1]))
        self._pending_jump_position: tuple[int, int] | None = None
        self._pending_jump_count = 0

    def position(self) -> tuple[int, int] | None:
        """이벤트 큐 처리와 무관하게 읽을 수 있는 최신 캐릭터 좌표."""
        with self._position_lock:
            return self._last_position

    def capture_region(self) -> dict | None:
        """현재 스캔에 사용하는 화면 캡처 영역을 반환한다."""
        region = self._region() if callable(self._region) else self._region
        return dict(region) if region else None

    def position_ratio(self) -> tuple[float, float] | None:
        """최신 위치를 현재 미니맵 내부 0~1 비율로 반환한다."""
        with self._position_lock:
            position = self._last_position
        if position is None:
            return None
        region = self.capture_region()
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

    def set_position_offset(self, x: int, y: int) -> None:
        """감지한 미니맵 좌표에 적용할 사용자 보정값을 갱신한다."""
        self._position_offset = (int(x), int(y))

    def reload_marker_templates(self) -> None:
        """디스크에 저장된 캐릭터 마커 템플릿을 다시 로드한다."""
        templates, sample_hsv = _partition_marker_assets(_load_marker_templates())
        with self._scan_lock:
            self._marker_templates = templates
            self._marker_sample_hsv = sample_hsv

    def sample(self) -> tuple[tuple[int, int] | None, float | None]:
        with self._position_lock:
            return self._last_position, self._last_position_at

    def preview_snapshot(self) -> tuple[np.ndarray | None, tuple[int, int] | None, float | None]:
        """동일 스캔에서 얻은 미니맵 이미지와 보정 좌표를 함께 반환한다."""
        with self._position_lock:
            frame = None if self._preview_frame is None else self._preview_frame.copy()
            return frame, self._last_position, self._last_position_at

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
        region = self.capture_region()
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
        template_timing: dict[str, object] = {}
        previous_adjusted = self.position()
        previous_raw = (
            (
                previous_adjusted[0] - self._position_offset[0],
                previous_adjusted[1] - self._position_offset[1],
            )
            if previous_adjusted is not None
            else None
        )
        pos = find_char_by_template(
            img,
            self._marker_templates,
            excluded_regions=self._marker_exclusions,
            timing_out=template_timing,
            previous_position=previous_raw,
        )
        detection_source = "template" if pos is not None else None
        hsv_candidate_sec = 0.0
        hsv_diagnostics: dict[str, object] = {}
        if pos is None and self._marker_sample_hsv is not None:
            hsv_started = time.perf_counter()
            sample_lo, sample_hi = self._marker_sample_hsv
            pos = find_char_in_hsv(
                img, sample_lo, sample_hi, self._min_area, self._max_area,
                previous_position=previous_raw,
                diagnostic_out=hsv_diagnostics,
            )
            hsv_candidate_sec = time.perf_counter() - hsv_started
            if pos is not None:
                detection_source = "sample_color"
        if pos is None and not self._marker_templates and self._marker_sample_hsv is None:
            hsv_started = time.perf_counter()
            pos = find_char_in_hsv(
                img, self._lo, self._hi, self._min_area, self._max_area,
                previous_position=previous_raw,
                diagnostic_out=hsv_diagnostics,
            )
            hsv_candidate_sec = time.perf_counter() - hsv_started
            if pos is not None:
                detection_source = "color"
        if pos is None:
            self._pending_jump_position = None
            self._pending_jump_count = 0
            self._diag(f"⚠ 노란점 미검출 (캡처 {tuple(img.shape)}, HSV {tuple(self._lo)}~{tuple(self._hi)})")
            return None
        image_height, image_width = img.shape[:2]
        raw_pos = pos
        pos = (
            int(raw_pos[0]) + self._position_offset[0],
            int(raw_pos[1]) + self._position_offset[1],
        )
        candidate_bbox = (
            template_timing.get("candidate_bbox")
            if detection_source == "template"
            else hsv_diagnostics.get("candidate_bbox")
        )
        candidate_text = (
            "none"
            if candidate_bbox is None
            else f"({','.join(str(int(value)) for value in candidate_bbox)})"
        )
        observed_at = time.monotonic()
        scan_duration = observed_at - scan_started
        with self._position_lock:
            previous_position = self._last_position
        if previous_position is not None:
            jump_distance = (
                (float(pos[0]) - float(previous_position[0])) ** 2
                + (float(pos[1]) - float(previous_position[1])) ** 2
            ) ** 0.5
            jump_threshold = max(30.0, min(image_width, image_height) * 0.35)
            needs_confirmation = (
                template_timing.get("search_mode") == "global"
                or jump_distance > jump_threshold
            )
            if needs_confirmation:
                pending = self._pending_jump_position
                confirm_radius = max(8.0, min(image_width, image_height) * 0.08)
                pending_matches = pending is not None and (
                    (float(pos[0]) - float(pending[0])) ** 2
                    + (float(pos[1]) - float(pending[1])) ** 2
                ) ** 0.5 <= confirm_radius
                if pending_matches:
                    self._pending_jump_count += 1
                else:
                    self._pending_jump_position = pos
                    self._pending_jump_count = 1
                if self._pending_jump_count < 3:
                    trace_event(
                        "character",
                        "position_rejected",
                        reason="unconfirmed_global_candidate",
                        previous_x=previous_position[0],
                        previous_y=previous_position[1],
                        candidate_x=pos[0],
                        candidate_y=pos[1],
                        jump_distance=jump_distance,
                        threshold=jump_threshold,
                        confirmations=self._pending_jump_count,
                    )
                    return None
                trace_event(
                    "character",
                    "position_selected",
                    reason="confirmed_global_candidate",
                    x=pos[0],
                    y=pos[1],
                    jump_distance=jump_distance,
                )
        self._pending_jump_position = None
        self._pending_jump_count = 0
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
            template_match_sec=float(template_timing.get("template_match_sec", 0.0)),
            candidate_filter_sec=(
                float(template_timing.get("candidate_filter_sec", 0.0)) + hsv_candidate_sec
            ),
            total_scan_sec=scan_duration,
        )
        with self._position_lock:
            self._last_position = pos
            self._last_position_at = observed_at
            self._preview_frame = img.copy()
        sample = self._history.append(pos, observed_at, scan_duration)
        if self._position_store is not None:
            self._position_store.publish(pos[0], pos[1], observed_at)
        now = time.monotonic()
        if now - self._last_position_log_ts >= 1.0:
            self._last_position_log_ts = now
            self._diag(
                f"✓ 캐릭터 감지 source={detection_source} raw=({raw_pos[0]},{raw_pos[1]}) "
                f"candidate={candidate_text} "
                f"x={pos[0]} y={pos[1]} "
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

