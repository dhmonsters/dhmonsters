# planet_solver_noauth 방식의 실시간 CCTV 표시와 마우스 이동을 제공한다.
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from math import hypot
from typing import Any

import numpy as np

from core.puzzle.defaults import fixed_detect_roi, fixed_popup_header_roi, fixed_popup_preview_roi
from core.puzzle.evidence import EvidenceJudges
from core.puzzle.game_window import find_game_hwnd, get_game_client_rect_screen
from core.puzzle.identity import IdentityTracker
from core.puzzle.live_temporal_selector import LiveTemporalDecision, LiveTemporalSelector
from core.puzzle.models import Candidate, CandidateEvidence, FramePacket, IdentityDecision, RoiSpec
from core.puzzle.roi import crop_by_roi


CursorSetter = Callable[[int, int], None]
CursorDetector = Callable[[Any], tuple[float, float] | None]
BackgroundClicker = Callable[[int, int], None]
ClientOriginGetter = Callable[[], tuple[int, int]]

IDENTITY_TEMPORAL_DIVERGENCE_LIMIT = 28.0
IDENTITY_TEMPORAL_MIN_CONFIDENCE = 0.65
IDENTITY_TEMPORAL_HARD_DIVERGENCE_LIMIT = 120.0
IDENTITY_TEMPORAL_HOLD_MIN_CONFIDENCE = 0.25
IDENTITY_TEMPORAL_ALIVE_STATES = frozenset({
    "TRACK_CONFIDENT",
    "REACQUIRE",
    "OCCLUSION_SUSPECTED",
    "IDENTITY_HOLD",
})


@dataclass(frozen=True)
class MouseMoveResult:
    moved: bool
    abs_point: tuple[int, int] | None
    client_point: tuple[int, int] | None
    det_point: tuple[float, float] | None
    offset: tuple[float, float]
    reason: str


@dataclass(frozen=True)
class PlanetLiveResult:
    preview_frame: Any | None = None
    trace_events: list[tuple[str, dict[str, object]]] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    evidence: dict[str, CandidateEvidence] = field(default_factory=dict)
    decision: IdentityDecision | Any | None = None
    temporal_decision: LiveTemporalDecision | None = None
    mouse_move: MouseMoveResult | None = None


class PlanetMouseController:
    def __init__(
        self,
        *,
        cursor_setter: CursorSetter | None = None,
        cursor_detector: CursorDetector | None = None,
        background_clicker: BackgroundClicker | None = None,
        client_origin_getter: ClientOriginGetter | None = None,
        offset_limit: float = 200.0,
        offset_alpha: float = 0.5,
    ) -> None:
        bridge = _NoAuthMouseBridge()
        self.background_clicker = background_clicker
        self.client_origin_getter = client_origin_getter or bridge.client_origin
        self.cursor_setter = cursor_setter or _default_cursor_setter
        self.cursor_detector = cursor_detector or detect_pink_cursor
        self.offset_limit = float(offset_limit)
        self.offset_alpha = float(offset_alpha)
        self.offset_x = 0.0
        self.offset_y = 0.0

    def move_to_det_point(
        self,
        *,
        detect_roi: RoiSpec,
        point: tuple[float, float] | None,
        det_frame: Any | None,
        enabled: bool,
        learn_offset: bool = True,
    ) -> MouseMoveResult:
        if point is None:
            return MouseMoveResult(False, None, None, None, (0.0, 0.0), "no_target")
        if not enabled:
            return MouseMoveResult(False, None, None, point, (0.0, 0.0), "disabled")

        cx = max(0.0, min(float(detect_roi.w - 1), float(point[0])))
        cy = max(0.0, min(float(detect_roi.h - 1), float(point[1])))
        if learn_offset:
            self._learn_cursor_offset(cx, cy, det_frame)
        move_cx = max(0.0, min(float(detect_roi.w - 1), cx + self.offset_x))
        move_cy = max(0.0, min(float(detect_roi.h - 1), cy + self.offset_y))
        client_x = detect_roi.x + int(move_cx)
        client_y = detect_roi.y + int(move_cy)
        origin_x, origin_y = self._client_origin()
        abs_x = origin_x + client_x
        abs_y = origin_y + client_y
        if self.background_clicker is not None:
            try:
                self.background_clicker(client_x, client_y)
            except Exception as exc:
                return MouseMoveResult(
                    False,
                    (abs_x, abs_y),
                    (client_x, client_y),
                    (cx, cy),
                    (self.offset_x, self.offset_y),
                    f"click_failed:{exc.__class__.__name__}",
                )
            return MouseMoveResult(True, (abs_x, abs_y), (client_x, client_y), (cx, cy), (self.offset_x, self.offset_y), "bg_click")
        try:
            self.cursor_setter(abs_x, abs_y)
        except Exception as exc:
            return MouseMoveResult(
                False,
                (abs_x, abs_y),
                (client_x, client_y),
                (cx, cy),
                (self.offset_x, self.offset_y),
                f"fg_move_failed:{exc.__class__.__name__}",
            )
        return MouseMoveResult(True, (abs_x, abs_y), (client_x, client_y), (cx, cy), (self.offset_x, self.offset_y), "fg_move")

    def _client_origin(self) -> tuple[int, int]:
        try:
            origin_x, origin_y = self.client_origin_getter()
            return int(origin_x), int(origin_y)
        except Exception:
            return (0, 0)

    def _learn_cursor_offset(self, cx: float, cy: float, det_frame: Any | None) -> None:
        if det_frame is None:
            return
        cursor = self.cursor_detector(det_frame)
        if cursor is None:
            return
        self.offset_x += (cx - float(cursor[0])) * self.offset_alpha
        self.offset_y += (cy - float(cursor[1])) * self.offset_alpha
        self.offset_x = max(-self.offset_limit, min(self.offset_limit, self.offset_x))
        self.offset_y = max(-self.offset_limit, min(self.offset_limit, self.offset_y))


class _NoAuthMouseBridge:
    def __init__(self) -> None:
        self._hwnd: int | None = None

    def click(self, client_x: int, client_y: int) -> None:
        from planet_live_solver import bg_click

        bg_click(self._require_hwnd(), int(client_x), int(client_y))

    def client_origin(self) -> tuple[int, int]:
        x, y, _w, _h = get_game_client_rect_screen(self._require_hwnd())
        return int(x), int(y)

    def _require_hwnd(self) -> int:
        if self._hwnd is None:
            hwnd = find_game_hwnd()
            if hwnd is None:
                raise RuntimeError("maple_hwnd_not_found")
            self._hwnd = int(hwnd)
        return self._hwnd


@dataclass(frozen=True)
class _VisibleLockState:
    locked: bool
    point: tuple[float, float] | None
    stable_frames: int
    reason: str


class _VisibleWhiteLock:
    def __init__(self, *, stable_frames: int = 2, max_jump_px: float = 45.0) -> None:
        self.required_stable_frames = max(1, int(stable_frames))
        self.max_jump_px = float(max_jump_px)
        self._last_point: tuple[float, float] | None = None
        self._stable_frames = 0

    def update(self, point: tuple[float, float] | None) -> _VisibleLockState:
        if point is None:
            self._last_point = None
            self._stable_frames = 0
            return _VisibleLockState(False, None, 0, "no_white_anchor")

        current = (float(point[0]), float(point[1]))
        if self._last_point is None:
            self._stable_frames = 1
            reason = "white_anchor_seen"
        elif hypot(current[0] - self._last_point[0], current[1] - self._last_point[1]) <= self.max_jump_px:
            self._stable_frames += 1
            reason = "white_anchor_stable"
        else:
            self._stable_frames = 1
            reason = "white_anchor_jump_reset"
        self._last_point = current

        locked = self._stable_frames >= self.required_stable_frames
        return _VisibleLockState(locked, current if locked else None, self._stable_frames, reason)


@dataclass(frozen=True)
class _MotionCoastPrediction:
    point: tuple[float, float]
    size: tuple[float, float]
    age: int
    velocity: tuple[float, float]


class _MotionCoast:
    def __init__(self, *, max_age_frames: int = 18, max_velocity_px: float = 35.0) -> None:
        self.max_age_frames = int(max_age_frames)
        self.max_velocity_px = float(max_velocity_px)
        self._history: list[tuple[int, tuple[float, float], tuple[float, float]]] = []

    def update(
        self,
        *,
        frame_index: int,
        visible_point: tuple[float, float] | None,
        visible_size: tuple[float, float] | None,
        frame_shape: Sequence[int] | None,
    ) -> _MotionCoastPrediction | None:
        if visible_point is not None:
            self._history.append((
                int(frame_index),
                (float(visible_point[0]), float(visible_point[1])),
                _clean_size(visible_size),
            ))
            self._history = self._history[-5:]
            return None
        return self._predict(int(frame_index), frame_shape=frame_shape)

    def _predict(
        self,
        frame_index: int,
        *,
        frame_shape: Sequence[int] | None,
    ) -> _MotionCoastPrediction | None:
        if len(self._history) < 2:
            return None
        last_frame, last_point, last_size = self._history[-1]
        age = frame_index - last_frame
        if age <= 0 or age > self.max_age_frames:
            return None

        velocities = []
        for before, after in zip(self._history, self._history[1:]):
            dt = max(1, after[0] - before[0])
            velocities.append((
                (after[1][0] - before[1][0]) / dt,
                (after[1][1] - before[1][1]) / dt,
            ))
        if not velocities:
            return None
        vx = sum(item[0] for item in velocities) / len(velocities)
        vy = sum(item[1] for item in velocities) / len(velocities)
        speed = hypot(vx, vy)
        if speed > self.max_velocity_px:
            scale = self.max_velocity_px / speed
            vx *= scale
            vy *= scale

        point = (last_point[0] + vx * age, last_point[1] + vy * age)
        point = _clamp_point_to_shape(point, frame_shape=frame_shape)
        return _MotionCoastPrediction(point=point, size=last_size, age=age, velocity=(vx, vy))


class PlanetLiveSolver:
    def __init__(
        self,
        *,
        detector: Any | None = None,
        mouse: PlanetMouseController | None = None,
        evidence_judges: EvidenceJudges | None = None,
        identity_tracker: IdentityTracker | None = None,
        temporal_selector: Any | None = None,
        mouse_enabled: bool = True,
    ) -> None:
        self.detector = detector
        self.mouse = mouse or PlanetMouseController()
        self.evidence_judges = evidence_judges or EvidenceJudges()
        self.identity_tracker = identity_tracker or IdentityTracker()
        self.temporal_selector = temporal_selector or LiveTemporalSelector()
        self.mouse_enabled = bool(mouse_enabled)
        self._noauth_detector: Any | None = None
        self._noauth_detector_loaded = False
        self._last_detect_debug: dict[str, object] = {}
        self._visible_white_lock = _VisibleWhiteLock()
        self._motion_coast = _MotionCoast()

    def analyze(self, packet: FramePacket, *, solver_running: bool) -> PlanetLiveResult:
        detect_payload = packet.roi_snapshot.get("detect", {})
        board_payload = packet.roi_snapshot.get("board", {})
        detect_roi = _roi_from_payload(detect_payload, fallback_name="detect")
        board_roi = _roi_from_payload(board_payload, fallback_name="board")
        det_frame = crop_by_roi(packet.source_frame, detect_roi)
        raw_rows = list(self._detect_rows(det_frame))
        white_anchor_rows = _detect_white_anchor_rows(det_frame)
        candidate_rows = [*white_anchor_rows, *raw_rows]
        self._last_detect_debug = {
            **self._last_detect_debug,
            "white_anchor_count": len(white_anchor_rows),
            "candidate_count": len(candidate_rows),
        }
        candidates = _candidates_from_det_rows(
            candidate_rows,
            frame_index=packet.frame_index,
            detect_roi=detect_roi,
            board_roi=board_roi,
        )
        white_anchor = candidates[0].center if white_anchor_rows and candidates else None
        white_anchor_size = _candidate_size(candidates[0]) if white_anchor_rows and candidates else None
        if white_anchor is not None:
            motion_prediction = self._motion_coast.update(
                frame_index=packet.frame_index,
                visible_point=white_anchor,
                visible_size=white_anchor_size,
                frame_shape=_frame_shape(packet.board_frame),
            )
        elif not candidates:
            motion_prediction = self._motion_coast.update(
                frame_index=packet.frame_index,
                visible_point=None,
                visible_size=None,
                frame_shape=_frame_shape(packet.board_frame),
            )
        else:
            motion_prediction = None
        motion_coast_inserted = False
        if not candidates and motion_prediction is not None:
            candidates.append(_motion_coast_candidate(motion_prediction, frame_index=packet.frame_index))
            motion_coast_inserted = True
        visible_lock = self._visible_white_lock.update(white_anchor)
        self._last_detect_debug = {
            **self._last_detect_debug,
            "candidate_count": len(candidates),
            "motion_coast_count": 1 if motion_coast_inserted else 0,
            "motion_coast_age": motion_prediction.age if motion_prediction is not None else 0,
            "motion_coast_point": motion_prediction.point if motion_prediction is not None else None,
            "motion_coast_velocity": motion_prediction.velocity if motion_prediction is not None else None,
            "visible_lock": visible_lock.locked,
            "visible_lock_stable": visible_lock.stable_frames,
            "visible_lock_reason": visible_lock.reason,
            "visible_lock_point": visible_lock.point,
        }
        evidence = self.evidence_judges.score(candidates, packet)
        decision = self.identity_tracker.update(
            frame_index=packet.frame_index,
            candidates=candidates,
            evidence=evidence,
            white_anchor=white_anchor,
        )
        temporal_decision = self.temporal_selector.update(
            frame_index=packet.frame_index,
            candidates=_candidate_rows_from_candidates(candidates),
            primary_point=decision.point,
            white_anchor=white_anchor,
            frame_shape=_frame_shape(packet.board_frame),
        )
        if visible_lock.locked and visible_lock.point is not None:
            target_point = visible_lock.point
        else:
            target_point = _choose_live_target_point(
                decision=decision,
                temporal_decision=temporal_decision,
                visible_lock=visible_lock,
            )
        target_selection = _target_selection_payload(
            decision=decision,
            temporal_decision=temporal_decision,
            visible_lock=visible_lock,
            target_point=target_point,
        )
        det_point = _board_point_to_det_point(target_point, detect_roi=detect_roi, board_roi=board_roi)
        mouse_move = self.mouse.move_to_det_point(
            detect_roi=detect_roi,
            point=det_point,
            det_frame=det_frame,
            enabled=solver_running and self.mouse_enabled,
            learn_offset=visible_lock.locked and white_anchor is not None,
        )
        det_candidates = _det_rows_from_candidates(candidates, detect_roi=detect_roi, board_roi=board_roi)
        preview = render_planet_cctv_preview(
            packet.source_frame,
            candidates=det_candidates,
            track_pos=det_point,
            engine=_decision_engine_name(decision, temporal_decision),
        )
        return PlanetLiveResult(
            preview_frame=preview,
            trace_events=_trace_events(
                candidates,
                evidence,
                decision,
                temporal_decision,
                mouse_move,
                detect_debug=self._last_detect_debug,
                target_selection=target_selection,
            ),
            candidates=candidates,
            evidence=evidence,
            decision=decision,
            temporal_decision=temporal_decision,
            mouse_move=mouse_move,
        )

    def _detect_rows(self, det_frame: Any) -> Sequence[Any]:
        detector = self.detector or self._load_noauth_detector()
        if detector is None:
            self._last_detect_debug = {
                "source": "planet_live",
                "detector": "none",
                "detector_enabled": False,
                "detector_error": "detector_not_loaded",
                "raw_count": 0,
            }
            return []
        detector_enabled = bool(getattr(detector, "enabled", True))
        if not detector_enabled:
            self._last_detect_debug = _detector_debug(detector, enabled=False, raw_count=0)
            return []
        try:
            rows = list(detector.detect_all(det_frame))
        except Exception as exc:
            self._last_detect_debug = _detector_debug(
                detector,
                enabled=detector_enabled,
                raw_count=0,
                error=f"{exc.__class__.__name__}: {exc}",
            )
            return []
        self._last_detect_debug = _detector_debug(detector, enabled=detector_enabled, raw_count=len(rows))
        return rows

    def _load_noauth_detector(self) -> Any | None:
        if self._noauth_detector_loaded:
            return self._noauth_detector
        self._noauth_detector_loaded = True
        try:
            from core.puzzle.planet_noauth import PlanetNoAuthDetector

            self._noauth_detector = PlanetNoAuthDetector()
        except Exception:
            self._noauth_detector = None
        return self._noauth_detector


def render_planet_cctv_preview(
    frame: Any,
    *,
    popup_score: float | None = None,
    candidates: Sequence[Sequence[float]] | None = None,
    track_pos: tuple[float, float] | None = None,
    engine: str = "WAIT",
) -> Any:
    frame_h, frame_w = frame.shape[:2]
    popup_roi = fixed_popup_preview_roi(frame_w=frame_w, frame_h=frame_h)
    header_roi = _optional_header_roi(frame_w=frame_w, frame_h=frame_h)
    detect_roi = fixed_detect_roi(frame_w=frame_w, frame_h=frame_h)
    popup = crop_by_roi(frame, popup_roi)
    vis = popup.copy()
    cv2 = _cv2()
    header_text_x = 4
    header_text_y = 14
    if header_roi is not None:
        header_lx = header_roi.x - popup_roi.x
        header_ly = header_roi.y - popup_roi.y
        header_rx = header_lx + header_roi.w - 1
        header_ry = header_ly + header_roi.h - 1
        cv2.rectangle(vis, (header_lx, header_ly), (header_rx, header_ry), (0, 230, 255), 2)
        header_text_x = header_lx + 4
        header_text_y = header_ly + 14
    score_text = "HDR score --" if popup_score is None else f"HDR score={popup_score:.2f} / thr=0.50"
    cv2.putText(
        vis,
        score_text,
        (header_text_x, header_text_y),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (0, 230, 255),
        1,
        cv2.LINE_AA,
    )

    det_lx = detect_roi.x - popup_roi.x
    det_ly = detect_roi.y - popup_roi.y
    det_rx = det_lx + detect_roi.w
    det_ry = det_ly + detect_roi.h
    cv2.rectangle(vis, (det_lx, det_ly), (det_rx, det_ry), (0, 140, 255), 2)
    cv2.putText(vis, "DET", (det_lx + 4, det_ly + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 140, 255), 1, cv2.LINE_AA)

    for row in candidates or []:
        if len(row) < 5:
            continue
        cx, cy, score, width, height = [float(value) for value in row[:5]]
        x1 = det_lx + int(cx - width / 2.0)
        y1 = det_ly + int(cy - height / 2.0)
        x2 = det_lx + int(cx + width / 2.0)
        y2 = det_ly + int(cy + height / 2.0)
        selected = _contains_point((cx, cy, width, height), track_pos)
        color = (0, 255, 80) if selected else (0, 190, 0)
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2 if selected else 1)
        cv2.putText(vis, f"{score:.2f}", (x1, max(0, y1 - 3)), cv2.FONT_HERSHEY_SIMPLEX, 0.38, color, 1, cv2.LINE_AA)

    if track_pos is not None:
        marker_x = det_lx + int(track_pos[0])
        marker_y = det_ly + int(track_pos[1])
        cv2.drawMarker(vis, (marker_x, marker_y), (0, 255, 80), cv2.MARKER_CROSS, 22, 2)
        cv2.putText(vis, engine, (det_lx + 4, max(det_ly + 18, det_ry - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 220, 0), 1, cv2.LINE_AA)

    return vis


def _optional_header_roi(*, frame_w: int, frame_h: int) -> RoiSpec | None:
    try:
        return fixed_popup_header_roi(frame_w=frame_w, frame_h=frame_h)
    except ValueError:
        return None


def detect_pink_cursor(frame_bgr: Any) -> tuple[float, float] | None:
    try:
        cv2 = _cv2()
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([140, 80, 80]), np.array([175, 255, 255]))
        contours, _hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < 15:
            return None
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            return None
        return (float(moments["m10"] / moments["m00"]), float(moments["m01"] / moments["m00"]))
    except Exception:
        return None


def _candidates_from_det_rows(
    rows: Sequence[Any],
    *,
    frame_index: int,
    detect_roi: RoiSpec,
    board_roi: RoiSpec,
) -> list[Candidate]:
    candidates: list[Candidate] = []
    dx = detect_roi.x - board_roi.x
    dy = detect_roi.y - board_roi.y
    for row_index, row in enumerate(rows):
        parsed = _parse_row(row)
        cx = parsed["cx"] + dx
        cy = parsed["cy"] + dy
        width = parsed["w"]
        height = parsed["h"]
        candidates.append(
            Candidate(
                candidate_id=f"f{frame_index}_planet_live_{row_index}",
                frame_index=frame_index,
                bbox=(cx - width / 2.0, cy - height / 2.0, cx + width / 2.0, cy + height / 2.0),
                center=(cx, cy),
                score=parsed["score"],
                source=str(parsed.get("source", "raw")),
                class_name=parsed["class_name"],
            )
        )
    return candidates


def _motion_coast_candidate(prediction: _MotionCoastPrediction, *, frame_index: int) -> Candidate:
    width, height = prediction.size
    cx, cy = prediction.point
    return Candidate(
        candidate_id=f"f{frame_index}_motion_coast_0",
        frame_index=frame_index,
        bbox=(cx - width / 2.0, cy - height / 2.0, cx + width / 2.0, cy + height / 2.0),
        center=(cx, cy),
        score=0.55,
        source="motion_coast",
        class_name="motion_coast",
    )


def _candidate_size(candidate: Candidate) -> tuple[float, float]:
    return (
        max(1.0, float(candidate.bbox[2] - candidate.bbox[0])),
        max(1.0, float(candidate.bbox[3] - candidate.bbox[1])),
    )


def _clean_size(size: tuple[float, float] | None) -> tuple[float, float]:
    if size is None:
        return (42.0, 42.0)
    return (max(8.0, float(size[0])), max(8.0, float(size[1])))


def _clamp_point_to_shape(
    point: tuple[float, float],
    *,
    frame_shape: Sequence[int] | None,
) -> tuple[float, float]:
    if frame_shape is None or len(frame_shape) < 2:
        return (float(point[0]), float(point[1]))
    height = max(1, int(frame_shape[0]))
    width = max(1, int(frame_shape[1]))
    return (
        max(0.0, min(float(width - 1), float(point[0]))),
        max(0.0, min(float(height - 1), float(point[1]))),
    )


def _detect_white_anchor_rows(det_frame: Any) -> list[dict[str, float | str]]:
    arr = np.asarray(det_frame)
    if arr.size == 0:
        return []
    try:
        cv2 = _cv2()
        if arr.ndim >= 3:
            hsv = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_BGR2HSV)
            mask = ((hsv[:, :, 2] >= 230) & (hsv[:, :, 1] <= 80)).astype(np.uint8)
        else:
            mask = (arr >= 230).astype(np.uint8)
        if int(mask.sum()) < 300:
            return []
        component_count, _labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    except Exception:
        return []

    best: tuple[float, dict[str, float | str]] | None = None
    for label in range(1, component_count):
        x, y, width, height, area = [float(value) for value in stats[label]]
        if area < 300.0 or width < 16.0 or height < 16.0:
            continue
        if width > 140.0 or height > 140.0:
            continue
        aspect = width / max(height, 1.0)
        if aspect < 0.35 or aspect > 2.8:
            continue
        fill_ratio = area / max(width * height, 1.0)
        if fill_ratio < 0.28:
            continue
        cx, cy = [float(value) for value in centroids[label]]
        score = min(0.99, 0.82 + area / 9000.0)
        row = {
            "cx": cx,
            "cy": cy,
            "score": score,
            "w": width,
            "h": height,
            "source": "white_anchor",
            "class_name": "white_anchor",
        }
        rank = area * fill_ratio
        if best is None or rank > best[0]:
            best = (rank, row)
    return [best[1]] if best is not None else []


def _parse_row(row: Any) -> dict[str, float | str]:
    if isinstance(row, dict):
        return {
            "cx": float(row["cx"]),
            "cy": float(row["cy"]),
            "score": float(row["score"]),
            "w": float(row["w"]),
            "h": float(row["h"]),
            "class_name": str(row.get("class_name", "")),
            "source": str(row.get("source", "raw")),
        }
    return {
        "cx": float(row[0]),
        "cy": float(row[1]),
        "score": float(row[2]),
        "w": float(row[3]) if len(row) > 3 else 20.0,
        "h": float(row[4]) if len(row) > 4 else 20.0,
        "class_name": str(row[5]) if len(row) > 5 else "",
        "source": "raw",
    }


def _det_rows_from_candidates(
    candidates: Sequence[Candidate],
    *,
    detect_roi: RoiSpec,
    board_roi: RoiSpec,
) -> list[tuple[float, float, float, float, float]]:
    dx = detect_roi.x - board_roi.x
    dy = detect_roi.y - board_roi.y
    rows: list[tuple[float, float, float, float, float]] = []
    for candidate in candidates:
        width = candidate.bbox[2] - candidate.bbox[0]
        height = candidate.bbox[3] - candidate.bbox[1]
        rows.append((candidate.center[0] - dx, candidate.center[1] - dy, candidate.score, width, height))
    return rows


def _candidate_rows_from_candidates(candidates: Sequence[Candidate]) -> list[tuple[float, float, float, float, float]]:
    rows: list[tuple[float, float, float, float, float]] = []
    for candidate in candidates:
        width = candidate.bbox[2] - candidate.bbox[0]
        height = candidate.bbox[3] - candidate.bbox[1]
        rows.append((candidate.center[0], candidate.center[1], candidate.score, width, height))
    return rows


def _board_point_to_det_point(
    point: tuple[float, float] | None,
    *,
    detect_roi: RoiSpec,
    board_roi: RoiSpec,
) -> tuple[float, float] | None:
    if point is None:
        return None
    return (float(point[0]) - (detect_roi.x - board_roi.x), float(point[1]) - (detect_roi.y - board_roi.y))


def _choose_live_target_point(
    *,
    decision: IdentityDecision,
    temporal_decision: LiveTemporalDecision,
    visible_lock: Any,
) -> tuple[float, float] | None:
    if visible_lock.locked and visible_lock.point is not None:
        return visible_lock.point
    if temporal_decision.point is None:
        return decision.point
    if _should_prefer_identity_target(decision, temporal_decision):
        return decision.point
    return temporal_decision.point


def _should_prefer_identity_target(decision: IdentityDecision, temporal_decision: LiveTemporalDecision) -> bool:
    if decision.point is None or temporal_decision.point is None:
        return False
    distance = hypot(decision.point[0] - temporal_decision.point[0], decision.point[1] - temporal_decision.point[1])
    if (
        decision.state in IDENTITY_TEMPORAL_ALIVE_STATES
        and decision.confidence >= IDENTITY_TEMPORAL_HOLD_MIN_CONFIDENCE
        and distance > IDENTITY_TEMPORAL_HARD_DIVERGENCE_LIMIT
    ):
        return True
    if decision.state != "TRACK_CONFIDENT":
        return False
    if decision.confidence < IDENTITY_TEMPORAL_MIN_CONFIDENCE:
        return False
    return distance > IDENTITY_TEMPORAL_DIVERGENCE_LIMIT


def _target_selection_payload(
    *,
    decision: IdentityDecision,
    temporal_decision: LiveTemporalDecision,
    visible_lock: Any,
    target_point: tuple[float, float] | None,
) -> dict[str, object]:
    distance = _point_distance(decision.point, temporal_decision.point)
    if visible_lock.locked and visible_lock.point is not None:
        source = "visible_lock"
        reason = str(getattr(visible_lock, "reason", "") or "visible_lock")
    elif temporal_decision.point is None:
        source = "identity"
        reason = "temporal_missing"
    elif _should_prefer_identity_target(decision, temporal_decision):
        source = "identity"
        reason = "identity_temporal_divergence"
    else:
        source = "temporal"
        reason = str(temporal_decision.reason or "temporal")
    return {
        "point": target_point,
        "source": source,
        "reason": reason,
        "distance": distance,
        "identity_point": decision.point,
        "identity_confidence": decision.confidence,
        "temporal_point": temporal_decision.point,
        "temporal_family": temporal_decision.family,
    }


def _point_distance(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float | None:
    if a is None or b is None:
        return None
    return hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _trace_events(
    candidates: Sequence[Candidate],
    evidence: dict[str, CandidateEvidence],
    decision: IdentityDecision,
    temporal_decision: LiveTemporalDecision,
    mouse_move: MouseMoveResult,
    *,
    detect_debug: dict[str, object] | None = None,
    target_selection: dict[str, object] | None = None,
) -> list[tuple[str, dict[str, object]]]:
    return [
        (
            "CANDIDATES",
            {
                "count": len(candidates),
                "candidates": [_candidate_payload(candidate) for candidate in candidates],
                "debug": {"source": "planet_live", **(detect_debug or {})},
            },
        ),
        (
            "EVIDENCE",
            {
                "count": len(evidence),
                "evidence": [_evidence_payload(item) for item in evidence.values()],
            },
        ),
        ("IDENTITY_STATE", _identity_payload(decision)),
        ("TEMPORAL_SELECTOR", _temporal_payload(temporal_decision)),
        ("TARGET_SELECTION", target_selection or {}),
        (
            "MOUSE_MOVE",
            {
                "moved": mouse_move.moved,
                "abs_point": mouse_move.abs_point,
                "client_point": mouse_move.client_point,
                "det_point": mouse_move.det_point,
                "offset": mouse_move.offset,
                "reason": mouse_move.reason,
            },
        ),
    ]


def _candidate_payload(candidate: Candidate) -> dict[str, object]:
    return {
        "candidate_id": candidate.candidate_id,
        "bbox": candidate.bbox,
        "center": candidate.center,
        "score": candidate.score,
        "source": candidate.source,
        "class_name": candidate.class_name,
    }


def _detector_debug(
    detector: Any,
    *,
    enabled: bool,
    raw_count: int,
    error: str | None = None,
) -> dict[str, object]:
    detector_error = error if error is not None else str(getattr(detector, "last_error", "") or "")
    debug: dict[str, object] = {
        "source": "planet_live",
        "detector": detector.__class__.__name__,
        "detector_enabled": bool(enabled),
        "detector_load_source": str(getattr(detector, "load_source", "") or ""),
        "detector_error": detector_error,
        "raw_count": int(raw_count),
    }
    m1_score_used = getattr(detector, "m1_score_used", None)
    if m1_score_used is not None:
        debug["m1_score_used"] = float(m1_score_used)
    m1_attempts = getattr(detector, "m1_attempts", None)
    if m1_attempts is not None:
        debug["m1_attempts"] = [float(score) for score in m1_attempts]
    if hasattr(detector, "max_rows"):
        debug["detector_max_rows"] = int(getattr(detector, "max_rows"))
    return debug


def _evidence_payload(evidence: CandidateEvidence) -> dict[str, object]:
    return {
        "candidate_id": evidence.candidate_id,
        "bg_score": evidence.bg_score,
        "motion_divergence": evidence.motion_divergence,
        "rigid_violation": evidence.rigid_violation,
        "phase_similarity": evidence.phase_similarity,
        "texture_bg_score": evidence.texture_bg_score,
        "color_residual": evidence.color_residual,
        "merge_likelihood": evidence.merge_likelihood,
        "notes": evidence.notes,
    }


def _identity_payload(decision: IdentityDecision) -> dict[str, object]:
    return {
        "state": decision.state,
        "point": decision.point,
        "candidate_id": decision.candidate_id,
        "confidence": decision.confidence,
        "reason": decision.reason,
        "hold_frames": decision.hold_frames,
        "debug": decision.debug,
    }


def _temporal_payload(decision: LiveTemporalDecision) -> dict[str, object]:
    return {
        "point": decision.point,
        "source": decision.source,
        "reason": decision.reason,
        "family": decision.family,
        "selector_record": decision.selector_record,
        "live_family_points": dict(decision.live_family_points),
        "debug": dict(decision.debug),
    }


def _roi_from_payload(payload: object, *, fallback_name: str) -> RoiSpec:
    if not isinstance(payload, dict):
        raise ValueError(f"missing {fallback_name} ROI payload")
    return RoiSpec(
        name=str(payload.get("name", fallback_name)),
        basis="window_client",
        x=int(payload["x"]),
        y=int(payload["y"]),
        w=int(payload["w"]),
        h=int(payload["h"]),
        x_ratio=_optional_float(payload.get("x_ratio")),
        y_ratio=_optional_float(payload.get("y_ratio")),
        w_ratio=_optional_float(payload.get("w_ratio")),
        h_ratio=_optional_float(payload.get("h_ratio")),
        dpi_scale=float(payload.get("dpi_scale", 1.0)),
        window_title=str(payload.get("window_title", "")),
    )


def _decision_engine_name(decision: IdentityDecision, temporal_decision: LiveTemporalDecision | None = None) -> str:
    if temporal_decision is not None and temporal_decision.point is not None:
        return "TEMP"
    if decision.candidate_id:
        return "ID"
    return "WAIT"


def _frame_shape(frame: Any) -> tuple[int, int] | None:
    if frame is None or not hasattr(frame, "shape"):
        return None
    return tuple(frame.shape[:2])


def _contains_point(row: tuple[float, float, float, float], point: tuple[float, float] | None) -> bool:
    if point is None:
        return False
    cx, cy, width, height = row
    return (cx - width / 2.0) <= point[0] <= (cx + width / 2.0) and (cy - height / 2.0) <= point[1] <= (cy + height / 2.0)


def _default_cursor_setter(abs_x: int, abs_y: int) -> None:
    try:
        import win32api

        win32api.SetCursorPos((abs_x, abs_y))
    except Exception:
        pass


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _cv2() -> Any:
    import cv2

    return cv2


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
