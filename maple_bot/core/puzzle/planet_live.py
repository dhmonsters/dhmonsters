# planet_solver_noauth 방식의 실시간 CCTV 표시와 마우스 이동을 제공한다.
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from math import hypot
from typing import Any

import numpy as np

from core.puzzle.defaults import fixed_detect_roi, fixed_popup_header_roi, fixed_popup_preview_roi
from core.puzzle.evidence import EvidenceJudges, LiveEvidenceJudges
from core.puzzle.game_window import find_game_hwnd, get_game_client_rect_screen
from core.puzzle.hypothesis_challenge import HypothesisChallengeGuard
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
IDENTITY_TEMPORAL_FADED_REACQUIRE_MIN_CONFIDENCE = 0.55
IDENTITY_TEMPORAL_OCCLUSION_MIN_CONFIDENCE = 0.35
IDENTITY_LOCAL_REACQUIRE_LIMIT = 45.0
KINEMATIC_TEXTURE_ADVANTAGE_LIMIT = 0.01
KINEMATIC_SHAPE_TEXTURE_LIMIT = 0.938
KINEMATIC_CONFIDENT_TEXTURE_ADVANTAGE_LIMIT = -0.04
KINEMATIC_HOLD_SAME_CANDIDATE_MIN_SHIFT = 20.0
KINEMATIC_BEAM_APPEARANCE_ADVANTAGE_LIMIT = 0.011
KINEMATIC_BEAM_SAME_CANDIDATE_MAX_SHIFT = 100.0
KINEMATIC_BEAM_BOTTOM_EDGE_MARGIN = 1.0
KINEMATIC_WIDE_BEAM_TEXTURE_ADVANTAGE_LIMIT = -0.06
KINEMATIC_WIDE_BEAM_MIN_SHIFT = 50.0
KINEMATIC_WIDE_BEAM_MOTION_ADVANTAGE_LIMIT = 0.0
KINEMATIC_WIDE_BEAM_YOLO_ADVANTAGE_LIMIT = -0.10
KINEMATIC_WIDE_BEAM_MERGE_ADVANTAGE_LIMIT = -0.10
KINEMATIC_LOCAL_RIGID_MIN_RESIDUAL = 0.20
KINEMATIC_LOCAL_RIGID_MIN_ADVANTAGE = 0.121
KINEMATIC_LOCAL_RIGID_MIN_SHIFT = 30.0
KINEMATIC_EXPLORER_HYPOTHESIS_LIMIT = 12
IDENTITY_TEMPORAL_HARD_OVERRIDE_STATES = frozenset({
    "TRACK_CONFIDENT",
    "OCCLUSION_SUSPECTED",
    "IDENTITY_HOLD",
})
CCTV_OBSERVATION_TOP_LEFT = (0.04, 0.08)
CCTV_OBSERVATION_TOP_RIGHT = (0.82, 0.10)
CCTV_OBSERVATION_BOTTOM_RIGHT = (0.76, 0.66)
CCTV_OBSERVATION_BOTTOM_LEFT = (0.04, 0.62)
CCTV_OBSERVATION_LEFT_SIDE_TOP = (0.01, 0.11)
CCTV_OBSERVATION_LEFT_SIDE_BOTTOM = (0.01, 0.595)
CCTV_OBSERVATION_RIGHT_SIDE_TOP = (0.885, 0.125)
CCTV_OBSERVATION_RIGHT_SIDE_BOTTOM = (0.832, 0.705)
CCTV_OBSERVATION_SIDE_STRIP_RATIO = 0.07
CCTV_OBSERVATION_SCANLINE_ALPHA = 0.84
CCTV_OBSERVATION_LEFT_SIDE_SHADE = 0.50
CCTV_OBSERVATION_RIGHT_SIDE_SHADE = 0.50
CCTV_OBSERVATION_CONTRAST_CLIP_LIMIT = 1.18


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
        self.evidence_judges = evidence_judges or LiveEvidenceJudges()
        self.identity_tracker = identity_tracker or IdentityTracker()
        self.temporal_selector = temporal_selector or LiveTemporalSelector()
        self.mouse_enabled = bool(mouse_enabled)
        self._noauth_detector: Any | None = None
        self._noauth_detector_loaded = False
        self._last_detect_debug: dict[str, object] = {}
        self._visible_white_lock = _VisibleWhiteLock()
        self._motion_coast = _MotionCoast()
        self._hypothesis_challenge_guard = HypothesisChallengeGuard(
            confirm_frames=3,
            max_step_px=60.0,
        )
        self._target_history: list[tuple[float, float]] = []

    def reset(self) -> None:
        for component in (self.evidence_judges, self.identity_tracker, self.temporal_selector):
            reset = getattr(component, "reset", None)
            if callable(reset):
                reset()
        self._last_detect_debug = {}
        self._visible_white_lock = _VisibleWhiteLock(
            stable_frames=self._visible_white_lock.required_stable_frames,
            max_jump_px=self._visible_white_lock.max_jump_px,
        )
        self._motion_coast = _MotionCoast(
            max_age_frames=self._motion_coast.max_age_frames,
            max_velocity_px=self._motion_coast.max_velocity_px,
        )
        self._hypothesis_challenge_guard.reset()
        self._target_history = []

    def analyze(self, packet: FramePacket, *, solver_running: bool) -> PlanetLiveResult:
        detect_payload = packet.roi_snapshot.get("detect", {})
        board_payload = packet.roi_snapshot.get("board", {})
        detect_roi = _roi_from_payload(detect_payload, fallback_name="detect")
        board_roi = _roi_from_payload(board_payload, fallback_name="board")
        det_frame = crop_by_roi(packet.source_frame, detect_roi)
        raw_rows = list(self._detect_rows(det_frame))
        detected_white_anchor_rows = _detect_white_anchor_rows(det_frame)
        white_anchor_rows = _refine_white_anchor_rows(detected_white_anchor_rows, raw_rows)
        white_anchor_refined = bool(
            detected_white_anchor_rows
            and white_anchor_rows
            and (
                float(detected_white_anchor_rows[0]["cx"]) != float(white_anchor_rows[0]["cx"])
                or float(detected_white_anchor_rows[0]["cy"]) != float(white_anchor_rows[0]["cy"])
            )
        )
        candidate_rows = [*white_anchor_rows, *raw_rows]
        self._last_detect_debug = {
            **self._last_detect_debug,
            "white_anchor_count": len(white_anchor_rows),
            "white_anchor_refined": white_anchor_refined,
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
        trusted_white_anchor = visible_lock.point if visible_lock.locked else None
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
            "white_anchor_trusted": trusted_white_anchor is not None,
        }
        evidence = self.evidence_judges.score(candidates, packet)
        decision = self.identity_tracker.update(
            frame_index=packet.frame_index,
            candidates=candidates,
            evidence=evidence,
            white_anchor=trusted_white_anchor,
        )
        temporal_decision = self.temporal_selector.update(
            frame_index=packet.frame_index,
            candidates=_candidate_rows_from_candidates(candidates),
            primary_point=decision.point,
            white_anchor=trusted_white_anchor,
            wide_white_anchor=white_anchor,
            frame_shape=_frame_shape(packet.board_frame),
        )
        if visible_lock.locked and visible_lock.point is not None:
            target_point = visible_lock.point
            kinematic_texture_gate = {
                "available": False,
                "selected": False,
                "reason": "visible_lock",
            }
            kinematic_beam_gate = {
                "available": False,
                "selected": False,
                "reason": "visible_lock",
            }
            kinematic_wide_beam_gate = {
                "available": False,
                "selected": False,
                "reason": "visible_lock",
            }
            kinematic_local_rigid_gate = {
                "available": False,
                "selected": False,
                "reason": "visible_lock",
            }
            kinematic_explorer_gate = {
                "available": False,
                "selected": False,
                "reason": "visible_lock",
            }
            self._hypothesis_challenge_guard.reset()
        else:
            base_target_point = _choose_live_target_point(
                decision=decision,
                temporal_decision=temporal_decision,
                visible_lock=visible_lock,
            )
            target_point, kinematic_texture_gate = _choose_kinematic_texture_target(
                base_point=base_target_point,
                shape_point=temporal_decision.debug.get("kinematic_shape_point"),
                candidates=candidates,
                evidence=evidence,
                identity_state=decision.state,
            )
            target_point, kinematic_beam_gate = _choose_kinematic_beam_target(
                base_point=target_point,
                beam_point=temporal_decision.debug.get("kinematic_beam_point"),
                candidates=candidates,
                evidence=evidence,
                identity_state=decision.state,
                frame_shape=_frame_shape(packet.board_frame),
            )
            pre_wide_target_point = target_point
            target_point, kinematic_wide_beam_gate = _choose_kinematic_wide_beam_target(
                base_point=target_point,
                hypothesis_points=temporal_decision.debug.get("kinematic_wide_beam_points"),
                candidates=candidates,
                evidence=evidence,
                identity_state=decision.state,
                frame_shape=_frame_shape(packet.board_frame),
            )
            target_point, kinematic_local_rigid_gate = _choose_kinematic_local_rigid_target(
                base_point=target_point,
                hypothesis_points=temporal_decision.debug.get("kinematic_wide_beam_points"),
                candidates=candidates,
                evidence=evidence,
                identity_state=decision.state,
            )
            incumbent_selection = _target_selection_payload(
                decision=decision,
                temporal_decision=temporal_decision,
                visible_lock=visible_lock,
                target_point=target_point,
                kinematic_texture_gate=kinematic_texture_gate,
                kinematic_beam_gate=kinematic_beam_gate,
                kinematic_wide_beam_gate=kinematic_wide_beam_gate,
                kinematic_local_rigid_gate=kinematic_local_rigid_gate,
            )
            target_point, kinematic_explorer_gate = _choose_kinematic_explorer_target(
                incumbent_point=target_point,
                incumbent_source=str(incumbent_selection.get("source", "")),
                pre_wide_point=pre_wide_target_point,
                hypothesis_points=temporal_decision.debug.get("kinematic_explorer_beam_points"),
                candidates=candidates,
                evidence=evidence,
                identity_state=decision.state,
                frame_shape=_frame_shape(packet.board_frame),
                challenge_guard=self._hypothesis_challenge_guard,
            )
        target_selection = _target_selection_payload(
            decision=decision,
            temporal_decision=temporal_decision,
            visible_lock=visible_lock,
            target_point=target_point,
            kinematic_texture_gate=kinematic_texture_gate,
            kinematic_beam_gate=kinematic_beam_gate,
            kinematic_wide_beam_gate=kinematic_wide_beam_gate,
            kinematic_local_rigid_gate=kinematic_local_rigid_gate,
            kinematic_explorer_gate=kinematic_explorer_gate,
        )
        det_point = _board_point_to_det_point(target_point, detect_roi=detect_roi, board_roi=board_roi)
        if det_point is not None:
            self._target_history.append((float(det_point[0]), float(det_point[1])))
            self._target_history = self._target_history[-48:]
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
            target_history=self._target_history,
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
    target_history: Sequence[tuple[float, float]] | None = None,
    engine: str = "WAIT",
) -> Any:
    frame_h, frame_w = frame.shape[:2]
    popup_roi = fixed_popup_preview_roi(frame_w=frame_w, frame_h=frame_h)
    header_roi = _optional_header_roi(frame_w=frame_w, frame_h=frame_h)
    detect_roi = fixed_detect_roi(frame_w=frame_w, frame_h=frame_h)
    popup = crop_by_roi(frame, popup_roi)
    cv2 = _cv2()
    vis, observation_matrix = _skew_grayscale_observation(popup, cv2=cv2)
    header_text_x = 4
    header_text_y = 14
    if header_roi is not None:
        header_lx = header_roi.x - popup_roi.x
        header_ly = header_roi.y - popup_roi.y
        header_rx = header_lx + header_roi.w - 1
        header_ry = header_ly + header_roi.h - 1
        _draw_transformed_rect(
            vis,
            observation_matrix,
            header_lx,
            header_ly,
            header_rx,
            header_ry,
            (0, 230, 255),
            2,
            cv2=cv2,
        )
        header_text_x = header_lx + 4
        header_text_y = header_ly + 14
    score_text = "HDR score --" if popup_score is None else f"HDR score={popup_score:.2f} / thr=0.50"
    score_pos = _transform_preview_point(observation_matrix, header_text_x, header_text_y)
    cv2.putText(
        vis,
        score_text,
        score_pos,
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
    _draw_transformed_rect(
        vis,
        observation_matrix,
        det_lx,
        det_ly,
        det_rx,
        det_ry,
        (0, 140, 255),
        2,
        cv2=cv2,
    )
    cv2.putText(
        vis,
        "DET",
        _transform_preview_point(observation_matrix, det_lx + 4, det_ly + 14),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.4,
        (0, 140, 255),
        1,
        cv2.LINE_AA,
    )

    candidate_rows = [row for row in candidates or [] if len(row) >= 5]
    candidate_roles = _preview_candidate_roles(candidate_rows, track_pos)
    for candidate_index, row in enumerate(candidate_rows, start=1):
        if len(row) < 5:
            continue
        cx, cy, score, width, height = [float(value) for value in row[:5]]
        x1 = det_lx + int(cx - width / 2.0)
        y1 = det_ly + int(cy - height / 2.0)
        x2 = det_lx + int(cx + width / 2.0)
        y2 = det_ly + int(cy + height / 2.0)
        role = candidate_roles[candidate_index - 1]
        color, thickness = _preview_candidate_style(role)
        _draw_transformed_rect(
            vis,
            observation_matrix,
            x1,
            y1,
            x2,
            y2,
            color,
            thickness,
            cv2=cv2,
        )
        cv2.putText(
            vis,
            f"{score:.2f}",
            _transform_preview_point(observation_matrix, x1, max(0, y1 - 3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.38,
            color,
            1,
            cv2.LINE_AA,
        )
        cv2.putText(
            vis,
            f"#{candidate_index} {role}",
            _transform_preview_point(observation_matrix, x1 + 2, y1 + 12),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )

    history_points = [
        _transform_preview_point(observation_matrix, det_lx + float(point[0]), det_ly + float(point[1]))
        for point in target_history or []
        if point is not None
    ]
    if len(history_points) >= 2:
        pts = np.array(history_points, dtype=np.int32)
        cv2.polylines(vis, [pts], False, (0, 255, 80), 2)

    if track_pos is not None:
        marker_x, marker_y = _transform_preview_point(
            observation_matrix,
            det_lx + int(track_pos[0]),
            det_ly + int(track_pos[1]),
        )
        cv2.circle(vis, (marker_x, marker_y), 24, (0, 255, 80), 3, cv2.LINE_AA)
        cv2.circle(vis, (marker_x, marker_y), 4, (0, 255, 80), -1, cv2.LINE_AA)
        cv2.drawMarker(vis, (marker_x, marker_y), (0, 255, 80), cv2.MARKER_CROSS, 34, 3)
        cv2.putText(
            vis,
            engine,
            _transform_preview_point(observation_matrix, det_lx + 4, max(det_ly + 18, det_ry - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 220, 0),
            1,
            cv2.LINE_AA,
        )

    return vis


def _preview_candidate_roles(
    candidates: Sequence[Sequence[float]],
    track_pos: tuple[float, float] | None,
) -> list[str]:
    if not candidates:
        return []
    if track_pos is None:
        return ["CHECK" for _row in candidates]
    rows = [[float(value) for value in row[:5]] for row in candidates]
    selected_index = _preview_selected_candidate_index(rows, track_pos)
    roles: list[str] = []
    for index, row in enumerate(rows):
        if index == selected_index:
            roles.append("PICK")
            continue
        cx, cy, _score, width, height = row
        distance = hypot(float(track_pos[0]) - cx, float(track_pos[1]) - cy)
        check_radius = max(32.0, max(width, height) * 0.85)
        roles.append("CHECK" if distance <= check_radius else "DROP")
    return roles


def _preview_selected_candidate_index(
    rows: Sequence[Sequence[float]],
    track_pos: tuple[float, float],
) -> int | None:
    containing = [
        (hypot(float(track_pos[0]) - row[0], float(track_pos[1]) - row[1]), index)
        for index, row in enumerate(rows)
        if _contains_point((row[0], row[1], row[3], row[4]), track_pos)
    ]
    if containing:
        return min(containing)[1]
    nearest = [
        (hypot(float(track_pos[0]) - row[0], float(track_pos[1]) - row[1]), index)
        for index, row in enumerate(rows)
    ]
    return min(nearest)[1] if nearest else None


def _preview_candidate_style(role: str) -> tuple[tuple[int, int, int], int]:
    if role == "PICK":
        return (0, 255, 80), 2
    if role == "CHECK":
        return (0, 220, 255), 1
    return (0, 70, 255), 1


def _skew_grayscale_observation(frame: Any, *, cv2: Any) -> tuple[Any, Any]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = _enhance_observation_gray(gray, cv2=cv2)
    gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    height, width = gray_bgr.shape[:2]
    matrix = _cctv_observation_matrix(width, height)
    canvas = np.zeros_like(gray_bgr)
    side_strip = max(12, int(round(width * CCTV_OBSERVATION_SIDE_STRIP_RATIO)))
    src_left = np.array(
        [
            [0.0, 0.0],
            [float(side_strip), 0.0],
            [float(side_strip), float(height - 1)],
            [0.0, float(height - 1)],
        ],
        dtype=np.float32,
    )
    src_right = np.array(
        [
            [float(width - side_strip - 1), 0.0],
            [float(width - 1), 0.0],
            [float(width - 1), float(height - 1)],
            [float(width - side_strip - 1), float(height - 1)],
        ],
        dtype=np.float32,
    )
    main_dst = _cctv_observation_dst_points(width, height)
    left_dst = np.array(
        [
            _ratio_point(width, height, CCTV_OBSERVATION_LEFT_SIDE_TOP),
            main_dst[0],
            main_dst[3],
            _ratio_point(width, height, CCTV_OBSERVATION_LEFT_SIDE_BOTTOM),
        ],
        dtype=np.float32,
    )
    right_dst = np.array(
        [
            main_dst[1],
            _ratio_point(width, height, CCTV_OBSERVATION_RIGHT_SIDE_TOP),
            _ratio_point(width, height, CCTV_OBSERVATION_RIGHT_SIDE_BOTTOM),
            main_dst[2],
        ],
        dtype=np.float32,
    )
    _warp_observation_face(canvas, gray_bgr, src_left, left_dst, shade=CCTV_OBSERVATION_LEFT_SIDE_SHADE, cv2=cv2)
    _warp_observation_face(canvas, gray_bgr, src_right, right_dst, shade=CCTV_OBSERVATION_RIGHT_SIDE_SHADE, cv2=cv2)
    src_main = np.array(
        [
            [0.0, 0.0],
            [float(width - 1), 0.0],
            [float(width - 1), float(height - 1)],
            [0.0, float(height - 1)],
        ],
        dtype=np.float32,
    )
    _warp_observation_face(canvas, gray_bgr, src_main, main_dst, shade=1.0, cv2=cv2)
    _apply_observation_scanlines(canvas)
    return canvas, matrix


def _cctv_observation_matrix(width: int, height: int) -> Any:
    cv2 = _cv2()
    src = np.array(
        [
            [0.0, 0.0],
            [float(width - 1), 0.0],
            [float(width - 1), float(height - 1)],
            [0.0, float(height - 1)],
        ],
        dtype=np.float32,
    )
    return cv2.getPerspectiveTransform(src, _cctv_observation_dst_points(width, height))


def _cctv_observation_dst_points(width: int, height: int) -> Any:
    dst = np.array(
        [
            _ratio_point(width, height, CCTV_OBSERVATION_TOP_LEFT),
            _ratio_point(width, height, CCTV_OBSERVATION_TOP_RIGHT),
            _ratio_point(width, height, CCTV_OBSERVATION_BOTTOM_RIGHT),
            _ratio_point(width, height, CCTV_OBSERVATION_BOTTOM_LEFT),
        ],
        dtype=np.float32,
    )
    return dst


def _ratio_point(width: int, height: int, ratio: tuple[float, float]) -> tuple[float, float]:
    return (float(width - 1) * ratio[0], float(height - 1) * ratio[1])


def _cctv_observation_transform_point(width: int, height: int, x: float, y: float) -> tuple[int, int]:
    return _transform_preview_point(_cctv_observation_matrix(width, height), x, y)


def _transform_preview_point(matrix: Any, x: float, y: float) -> tuple[int, int]:
    tx = float(matrix[0, 0]) * float(x) + float(matrix[0, 1]) * float(y) + float(matrix[0, 2])
    ty = float(matrix[1, 0]) * float(x) + float(matrix[1, 1]) * float(y) + float(matrix[1, 2])
    tw = float(matrix[2, 0]) * float(x) + float(matrix[2, 1]) * float(y) + float(matrix[2, 2])
    if abs(tw) > 1e-6:
        tx /= tw
        ty /= tw
    return (int(round(tx)), int(round(ty)))


def _draw_transformed_rect(
    frame: Any,
    matrix: Any,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    color: tuple[int, int, int],
    thickness: int,
    *,
    cv2: Any,
) -> None:
    pts = np.array(
        [
            _transform_preview_point(matrix, x1, y1),
            _transform_preview_point(matrix, x2, y1),
            _transform_preview_point(matrix, x2, y2),
            _transform_preview_point(matrix, x1, y2),
        ],
        dtype=np.int32,
    )
    cv2.polylines(frame, [pts], True, color, thickness)


def _warp_observation_face(
    canvas: Any,
    source: Any,
    src_points: Any,
    dst_points: Any,
    *,
    shade: float,
    cv2: Any,
) -> None:
    height, width = canvas.shape[:2]
    matrix = cv2.getPerspectiveTransform(src_points, dst_points)
    warped = cv2.warpPerspective(
        source,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0),
    )
    if shade != 1.0:
        warped = cv2.convertScaleAbs(warped, alpha=float(shade), beta=0)
    mask = np.zeros((height, width), dtype=np.uint8)
    cv2.fillConvexPoly(mask, np.round(dst_points).astype(np.int32), 255)
    canvas[mask > 0] = warped[mask > 0]


def _apply_observation_scanlines(frame: Any) -> None:
    if frame.size == 0:
        return
    frame[1::4] = (frame[1::4].astype(np.float32) * CCTV_OBSERVATION_SCANLINE_ALPHA).astype(frame.dtype)


def _enhance_observation_gray(gray: Any, *, cv2: Any) -> Any:
    if gray.size == 0:
        return gray
    clahe = cv2.createCLAHE(clipLimit=CCTV_OBSERVATION_CONTRAST_CLIP_LIMIT, tileGridSize=(8, 8))
    return clahe.apply(gray)


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


def _refine_white_anchor_rows(
    white_rows: Sequence[Any],
    raw_rows: Sequence[Any],
) -> list[dict[str, float | str]]:
    if len(white_rows) != 1 or not raw_rows:
        return [dict(row) for row in white_rows]

    white = _parse_row(white_rows[0])
    white_area = max(1.0, float(white["w"]) * float(white["h"]))
    matches: list[tuple[float, float, dict[str, float | str]]] = []
    for raw_row in raw_rows:
        raw = _parse_row(raw_row)
        if float(raw["score"]) < 0.2:
            continue
        width = float(raw["w"])
        height = float(raw["h"])
        if width > max(160.0, float(white["w"]) * 4.0):
            continue
        if height > max(160.0, float(white["h"]) * 4.0):
            continue
        raw_area = max(1.0, width * height)
        area_ratio = raw_area / white_area
        if area_ratio < 2.0 or area_ratio > 20.0:
            continue
        if not _contains_point(
            (float(raw["cx"]), float(raw["cy"]), width, height),
            (float(white["cx"]), float(white["cy"])),
        ):
            continue
        distance = hypot(
            float(raw["cx"]) - float(white["cx"]),
            float(raw["cy"]) - float(white["cy"]),
        )
        matches.append((distance, -float(raw["score"]), raw))

    if not matches:
        return [dict(row) for row in white_rows]
    _distance_to_fragment, _negative_score, best = min(matches, key=lambda item: (item[0], item[1]))
    refined = dict(white_rows[0])
    refined.update(
        {
            "cx": float(best["cx"]),
            "cy": float(best["cy"]),
            "score": max(float(white["score"]), float(best["score"])),
            "w": float(best["w"]),
            "h": float(best["h"]),
            "source": "white_anchor",
            "class_name": "white_anchor",
        }
    )
    return [refined]


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


def _choose_kinematic_texture_target(
    *,
    base_point: Sequence[float] | None,
    shape_point: object,
    candidates: Sequence[Candidate],
    evidence: dict[str, CandidateEvidence],
    identity_state: str = "",
    texture_advantage_limit: float = KINEMATIC_TEXTURE_ADVANTAGE_LIMIT,
    shape_texture_limit: float = KINEMATIC_SHAPE_TEXTURE_LIMIT,
    confident_texture_advantage_limit: float = KINEMATIC_CONFIDENT_TEXTURE_ADVANTAGE_LIMIT,
    hold_same_candidate_min_shift: float = KINEMATIC_HOLD_SAME_CANDIDATE_MIN_SHIFT,
) -> tuple[tuple[float, float] | None, dict[str, object]]:
    base = _coerce_point(base_point)
    shape = _coerce_point(shape_point)
    if base is None or shape is None or not candidates:
        return base, {
            "available": False,
            "selected": False,
            "reason": "missing_path_or_candidates",
        }
    base_candidate = min(candidates, key=lambda candidate: _point_distance(candidate.center, base))
    shape_candidate = min(candidates, key=lambda candidate: _point_distance(candidate.center, shape))
    base_evidence = evidence.get(base_candidate.candidate_id)
    shape_evidence = evidence.get(shape_candidate.candidate_id)
    if base_evidence is None or shape_evidence is None:
        return base, {
            "available": False,
            "selected": False,
            "reason": "missing_texture_evidence",
        }
    shape_texture = float(shape_evidence.texture_bg_score)
    texture_advantage = shape_texture - float(base_evidence.texture_bg_score)
    shape_shift = _point_distance(base, shape)
    if shape_texture > float(shape_texture_limit):
        selected = False
        reason = "shape_too_background_like"
    elif texture_advantage > float(texture_advantage_limit):
        selected = False
        reason = "shape_more_background_like"
    elif identity_state == "TRACK_CONFIDENT" and texture_advantage > float(confident_texture_advantage_limit):
        selected = False
        reason = "confident_texture_gain_too_weak"
    elif (
        identity_state == "IDENTITY_HOLD"
        and base_candidate.candidate_id == shape_candidate.candidate_id
        and shape_shift < float(hold_same_candidate_min_shift)
    ):
        selected = False
        reason = "hold_same_candidate_shift_too_small"
    else:
        selected = True
        reason = "accepted"
    return (shape if selected else base), {
        "available": True,
        "selected": selected,
        "reason": reason,
        "base_point": base,
        "shape_point": shape,
        "selected_point": shape if selected else base,
        "base_candidate_id": base_candidate.candidate_id,
        "shape_candidate_id": shape_candidate.candidate_id,
        "base_texture_bg_score": float(base_evidence.texture_bg_score),
        "shape_texture_bg_score": float(shape_evidence.texture_bg_score),
        "texture_advantage": texture_advantage,
        "texture_advantage_limit": float(texture_advantage_limit),
        "shape_texture_limit": float(shape_texture_limit),
        "identity_state": identity_state,
        "confident_texture_advantage_limit": float(confident_texture_advantage_limit),
        "shape_shift": shape_shift,
        "hold_same_candidate_min_shift": float(hold_same_candidate_min_shift),
    }


def _choose_kinematic_beam_target(
    *,
    base_point: Sequence[float] | None,
    beam_point: object,
    candidates: Sequence[Candidate],
    evidence: dict[str, CandidateEvidence],
    identity_state: str = "",
    appearance_advantage_limit: float = KINEMATIC_BEAM_APPEARANCE_ADVANTAGE_LIMIT,
    same_candidate_max_shift: float = KINEMATIC_BEAM_SAME_CANDIDATE_MAX_SHIFT,
    bottom_edge_margin: float = KINEMATIC_BEAM_BOTTOM_EDGE_MARGIN,
    frame_shape: tuple[int, int] | None = None,
) -> tuple[tuple[float, float] | None, dict[str, object]]:
    base = _coerce_point(base_point)
    beam = _coerce_point(beam_point)
    if base is None or beam is None or not candidates:
        return base, {
            "available": False,
            "selected": False,
            "reason": "missing_path_or_candidates",
        }
    base_candidate = min(candidates, key=lambda candidate: _point_distance(candidate.center, base))
    beam_candidate = min(candidates, key=lambda candidate: _point_distance(candidate.center, beam))
    base_evidence = evidence.get(base_candidate.candidate_id)
    beam_evidence = evidence.get(beam_candidate.candidate_id)
    if base_evidence is None or beam_evidence is None:
        return base, {
            "available": False,
            "selected": False,
            "reason": "missing_appearance_evidence",
        }
    appearance_advantage = float(beam_evidence.color_residual) - float(base_evidence.color_residual)
    beam_shift = _point_distance(base, beam)
    same_candidate = base_candidate.candidate_id == beam_candidate.candidate_id
    bottom_margin = None
    if frame_shape is not None:
        bottom_margin = float(frame_shape[0]) - float(beam_candidate.bbox[3])
    if identity_state == "INIT_VISIBLE":
        selected = False
        reason = "visible_identity_locked"
    elif same_candidate and beam_shift < float(same_candidate_max_shift):
        selected = False
        reason = "same_candidate_shift_too_small"
    elif bottom_margin is not None and bottom_margin <= float(bottom_edge_margin):
        selected = False
        reason = "beam_candidate_bottom_clipped"
    elif appearance_advantage > float(appearance_advantage_limit):
        selected = False
        reason = "beam_appearance_worse"
    else:
        selected = True
        reason = "appearance_parity"
    return (beam if selected else base), {
        "available": True,
        "selected": selected,
        "reason": reason,
        "base_point": base,
        "beam_point": beam,
        "selected_point": beam if selected else base,
        "base_candidate_id": base_candidate.candidate_id,
        "beam_candidate_id": beam_candidate.candidate_id,
        "base_color_residual": float(base_evidence.color_residual),
        "beam_color_residual": float(beam_evidence.color_residual),
        "appearance_advantage": appearance_advantage,
        "appearance_advantage_limit": float(appearance_advantage_limit),
        "identity_state": identity_state,
        "same_candidate": same_candidate,
        "beam_shift": beam_shift,
        "same_candidate_max_shift": float(same_candidate_max_shift),
        "bottom_margin": bottom_margin,
        "bottom_edge_margin": float(bottom_edge_margin),
    }


def _choose_kinematic_wide_beam_target(
    *,
    base_point: Sequence[float] | None,
    hypothesis_points: object,
    candidates: Sequence[Candidate],
    evidence: dict[str, CandidateEvidence],
    identity_state: str = "",
    texture_advantage_limit: float = KINEMATIC_WIDE_BEAM_TEXTURE_ADVANTAGE_LIMIT,
    min_shift: float = KINEMATIC_WIDE_BEAM_MIN_SHIFT,
    frame_shape: tuple[int, int] | None = None,
) -> tuple[tuple[float, float] | None, dict[str, object]]:
    base = _coerce_point(base_point)
    if not isinstance(hypothesis_points, Sequence) or isinstance(hypothesis_points, (str, bytes)):
        points: list[tuple[float, float]] = []
    else:
        points = [point for value in hypothesis_points if (point := _coerce_point(value)) is not None]
    if base is None or not points or not candidates:
        return base, {
            "available": False,
            "selected": False,
            "reason": "missing_path_or_hypotheses",
        }

    base_candidate = min(candidates, key=lambda candidate: _point_distance(candidate.center, base))
    base_evidence = evidence.get(base_candidate.candidate_id)
    if base_evidence is None:
        return base, {
            "available": False,
            "selected": False,
            "reason": "missing_base_evidence",
        }

    hypotheses: list[tuple[tuple[float, float], Candidate, CandidateEvidence]] = []
    seen_candidate_ids: set[str] = set()
    for point in points:
        candidate = min(candidates, key=lambda item: _point_distance(item.center, point))
        if candidate.candidate_id in seen_candidate_ids:
            continue
        candidate_evidence = evidence.get(candidate.candidate_id)
        if candidate_evidence is None:
            continue
        seen_candidate_ids.add(candidate.candidate_id)
        hypotheses.append((point, candidate, candidate_evidence))
    if not hypotheses:
        return base, {
            "available": False,
            "selected": False,
            "reason": "missing_hypothesis_evidence",
        }

    wide_point, wide_candidate, wide_evidence = min(
        hypotheses,
        key=lambda row: float(row[2].texture_bg_score),
    )
    guarded_point, beam_guard = _choose_kinematic_beam_target(
        base_point=base,
        beam_point=wide_point,
        candidates=candidates,
        evidence=evidence,
        identity_state=identity_state,
        frame_shape=frame_shape,
    )
    wide_shift = _point_distance(base, wide_point)
    texture_advantage = (
        float(wide_evidence.texture_bg_score) - float(base_evidence.texture_bg_score)
    )
    motion_advantage = (
        float(wide_evidence.motion_divergence) - float(base_evidence.motion_divergence)
    )
    yolo_advantage = float(wide_candidate.score) - float(base_candidate.score)
    merge_advantage = (
        float(wide_evidence.merge_likelihood) - float(base_evidence.merge_likelihood)
    )
    texture_guard = (
        wide_shift >= float(min_shift)
        and texture_advantage <= float(texture_advantage_limit)
    )
    observation_consensus = (
        motion_advantage >= KINEMATIC_WIDE_BEAM_MOTION_ADVANTAGE_LIMIT
        and yolo_advantage >= KINEMATIC_WIDE_BEAM_YOLO_ADVANTAGE_LIMIT
        and merge_advantage >= KINEMATIC_WIDE_BEAM_MERGE_ADVANTAGE_LIMIT
    )
    if not bool(beam_guard.get("selected")):
        selected = False
        reason = str(beam_guard.get("reason") or "beam_guard_rejected")
    elif texture_guard:
        selected = True
        reason = "wide_texture_guard"
    elif observation_consensus:
        selected = True
        reason = "wide_observation_consensus"
    elif wide_shift < float(min_shift):
        selected = False
        reason = "paths_not_separated"
    else:
        selected = False
        reason = "texture_gain_too_weak"
    return (guarded_point if selected else base), {
        "available": True,
        "selected": selected,
        "reason": reason,
        "base_point": base,
        "wide_point": wide_point,
        "selected_point": guarded_point if selected else base,
        "base_candidate_id": base_candidate.candidate_id,
        "wide_candidate_id": wide_candidate.candidate_id,
        "base_texture_bg_score": float(base_evidence.texture_bg_score),
        "wide_texture_bg_score": float(wide_evidence.texture_bg_score),
        "texture_advantage": texture_advantage,
        "texture_advantage_limit": float(texture_advantage_limit),
        "motion_advantage": motion_advantage,
        "motion_advantage_limit": KINEMATIC_WIDE_BEAM_MOTION_ADVANTAGE_LIMIT,
        "yolo_advantage": yolo_advantage,
        "yolo_advantage_limit": KINEMATIC_WIDE_BEAM_YOLO_ADVANTAGE_LIMIT,
        "merge_advantage": merge_advantage,
        "merge_advantage_limit": KINEMATIC_WIDE_BEAM_MERGE_ADVANTAGE_LIMIT,
        "observation_consensus": observation_consensus,
        "wide_shift": wide_shift,
        "min_shift": float(min_shift),
        "hypothesis_count": len(hypotheses),
        "beam_guard": dict(beam_guard),
    }


def _choose_kinematic_local_rigid_target(
    *,
    base_point: Sequence[float] | None,
    hypothesis_points: object,
    candidates: Sequence[Candidate],
    evidence: dict[str, CandidateEvidence],
    identity_state: str = "",
    min_residual: float = KINEMATIC_LOCAL_RIGID_MIN_RESIDUAL,
    min_advantage: float = KINEMATIC_LOCAL_RIGID_MIN_ADVANTAGE,
    min_shift: float = KINEMATIC_LOCAL_RIGID_MIN_SHIFT,
) -> tuple[tuple[float, float] | None, dict[str, object]]:
    base = _coerce_point(base_point)
    if not isinstance(hypothesis_points, Sequence) or isinstance(hypothesis_points, (str, bytes)):
        points: list[tuple[float, float]] = []
    else:
        points = [point for value in hypothesis_points if (point := _coerce_point(value)) is not None]
    if base is None or not points or not candidates:
        return base, {
            "available": False,
            "selected": False,
            "reason": "missing_path_or_hypotheses",
        }
    if identity_state == "INIT_VISIBLE":
        return base, {
            "available": False,
            "selected": False,
            "reason": "visible_identity_locked",
        }

    base_candidate = min(candidates, key=lambda candidate: _point_distance(candidate.center, base))
    base_evidence = evidence.get(base_candidate.candidate_id)
    if base_evidence is None:
        return base, {
            "available": False,
            "selected": False,
            "reason": "missing_base_evidence",
        }

    hypotheses: list[tuple[tuple[float, float], Candidate, CandidateEvidence]] = []
    seen_candidate_ids: set[str] = set()
    for point in points:
        candidate = min(candidates, key=lambda item: _point_distance(item.center, point))
        if candidate.candidate_id in seen_candidate_ids:
            continue
        candidate_evidence = evidence.get(candidate.candidate_id)
        if candidate_evidence is None:
            continue
        seen_candidate_ids.add(candidate.candidate_id)
        hypotheses.append((point, candidate, candidate_evidence))
    if not hypotheses:
        return base, {
            "available": False,
            "selected": False,
            "reason": "missing_hypothesis_evidence",
        }

    selected_point, selected_candidate, selected_evidence = max(
        hypotheses,
        key=lambda row: float(row[2].local_rigid_residual),
    )
    base_residual = float(base_evidence.local_rigid_residual)
    selected_residual = float(selected_evidence.local_rigid_residual)
    residual_advantage = selected_residual - base_residual
    shift = _point_distance(base, selected_point)
    if base_residual <= 0.0:
        selected = False
        reason = "base_residual_unavailable"
    elif selected_candidate.candidate_id == base_candidate.candidate_id:
        selected = False
        reason = "same_candidate"
    elif selected_residual < float(min_residual):
        selected = False
        reason = "residual_too_weak"
    elif residual_advantage < float(min_advantage):
        selected = False
        reason = "advantage_too_weak"
    elif shift < float(min_shift):
        selected = False
        reason = "paths_not_separated"
    else:
        selected = True
        reason = "local_rigid_advantage"
    return (selected_point if selected else base), {
        "available": True,
        "selected": selected,
        "reason": reason,
        "base_point": base,
        "selected_point": selected_point if selected else base,
        "hypothesis_point": selected_point,
        "base_candidate_id": base_candidate.candidate_id,
        "selected_candidate_id": selected_candidate.candidate_id,
        "base_residual": base_residual,
        "selected_residual": selected_residual,
        "residual_advantage": residual_advantage,
        "min_residual": float(min_residual),
        "min_advantage": float(min_advantage),
        "shift": shift,
        "min_shift": float(min_shift),
        "hypothesis_count": len(hypotheses),
    }


def _choose_kinematic_explorer_target(
    *,
    incumbent_point: Sequence[float] | None,
    incumbent_source: str,
    pre_wide_point: Sequence[float] | None,
    hypothesis_points: object,
    candidates: Sequence[Candidate],
    evidence: dict[str, CandidateEvidence],
    identity_state: str,
    frame_shape: tuple[int, int] | None,
    challenge_guard: HypothesisChallengeGuard,
    hypothesis_limit: int = KINEMATIC_EXPLORER_HYPOTHESIS_LIMIT,
) -> tuple[tuple[float, float] | None, dict[str, object]]:
    incumbent = _coerce_point(incumbent_point)
    if not isinstance(hypothesis_points, Sequence) or isinstance(hypothesis_points, (str, bytes)):
        points: tuple[object, ...] = ()
    else:
        points = tuple(hypothesis_points)[:max(1, int(hypothesis_limit))]
    if incumbent is None or not points:
        challenge_guard.reset()
        return incumbent, {
            "available": False,
            "selected": False,
            "reason": "missing_incumbent_or_hypotheses",
        }

    challenger, wide_gate = _choose_kinematic_wide_beam_target(
        base_point=pre_wide_point,
        hypothesis_points=points,
        candidates=candidates,
        evidence=evidence,
        identity_state=identity_state,
        frame_shape=frame_shape,
    )
    challenger, local_rigid_gate = _choose_kinematic_local_rigid_target(
        base_point=challenger,
        hypothesis_points=points,
        candidates=candidates,
        evidence=evidence,
        identity_state=identity_state,
    )
    selected, guard_debug = challenge_guard.update(
        incumbent_point=incumbent,
        challenger_point=challenger,
        protect_incumbent=incumbent_source == "kinematic_local_rigid",
    )
    return selected, {
        "available": True,
        "selected": bool(guard_debug.get("selected")),
        "reason": str(guard_debug.get("reason", "")),
        "incumbent_point": incumbent,
        "incumbent_source": incumbent_source,
        "challenger_point": challenger,
        "selected_point": selected,
        "hypothesis_count": len(points),
        "wide_gate": dict(wide_gate),
        "local_rigid_gate": dict(local_rigid_gate),
        "challenge_guard": dict(guard_debug),
    }


def _coerce_point(value: object) -> tuple[float, float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _should_prefer_identity_target(decision: IdentityDecision, temporal_decision: LiveTemporalDecision) -> bool:
    if decision.point is None or temporal_decision.point is None:
        return False
    distance = hypot(decision.point[0] - temporal_decision.point[0], decision.point[1] - temporal_decision.point[1])
    if distance > IDENTITY_TEMPORAL_HARD_DIVERGENCE_LIMIT and _is_temporal_overlap_recovery(temporal_decision):
        if decision.state == "REACQUIRE":
            distance_to_last = decision.debug.get("distance_to_last")
            color_weight = decision.debug.get("color_weight")
            if (
                isinstance(distance_to_last, (int, float))
                and float(distance_to_last) <= IDENTITY_LOCAL_REACQUIRE_LIMIT
                and decision.confidence >= IDENTITY_TEMPORAL_MIN_CONFIDENCE
            ):
                return True
            if (
                isinstance(color_weight, (int, float))
                and float(color_weight) <= 0.0
                and decision.confidence >= IDENTITY_TEMPORAL_FADED_REACQUIRE_MIN_CONFIDENCE
            ):
                return True
            return False
    if (
        decision.state in IDENTITY_TEMPORAL_HARD_OVERRIDE_STATES
        and decision.confidence >= IDENTITY_TEMPORAL_HOLD_MIN_CONFIDENCE
        and distance > IDENTITY_TEMPORAL_HARD_DIVERGENCE_LIMIT
    ):
        return True
    if (
        decision.state == "OCCLUSION_SUSPECTED"
        and decision.confidence >= IDENTITY_TEMPORAL_OCCLUSION_MIN_CONFIDENCE
        and distance > IDENTITY_TEMPORAL_DIVERGENCE_LIMIT
    ):
        return True
    if decision.state != "TRACK_CONFIDENT":
        return False
    if decision.confidence < IDENTITY_TEMPORAL_MIN_CONFIDENCE:
        return False
    return distance > IDENTITY_TEMPORAL_DIVERGENCE_LIMIT


def _is_temporal_overlap_recovery(temporal_decision: LiveTemporalDecision) -> bool:
    if temporal_decision.point is None:
        return False
    if temporal_decision.reason != "selected_family":
        return False
    family = str(temporal_decision.family or "")
    return (
        family.startswith("raw_candidate_cont")
        or "box_rel" in family
        or "occlusion" in family
        or family.startswith("guarded_decal_identity_consensus")
    )


def _target_selection_payload(
    *,
    decision: IdentityDecision,
    temporal_decision: LiveTemporalDecision,
    visible_lock: Any,
    target_point: tuple[float, float] | None,
    kinematic_texture_gate: dict[str, object] | None = None,
    kinematic_beam_gate: dict[str, object] | None = None,
    kinematic_wide_beam_gate: dict[str, object] | None = None,
    kinematic_local_rigid_gate: dict[str, object] | None = None,
    kinematic_explorer_gate: dict[str, object] | None = None,
) -> dict[str, object]:
    distance = _point_distance(decision.point, temporal_decision.point)
    if visible_lock.locked and visible_lock.point is not None:
        source = "visible_lock"
        reason = str(getattr(visible_lock, "reason", "") or "visible_lock")
    elif temporal_decision.point is None:
        source = "identity"
        reason = "temporal_missing"
    elif kinematic_explorer_gate and bool(kinematic_explorer_gate.get("selected")):
        source = "kinematic_explorer"
        reason = str(kinematic_explorer_gate.get("reason") or "challenger_confirmed")
    elif kinematic_local_rigid_gate and bool(kinematic_local_rigid_gate.get("selected")):
        source = "kinematic_local_rigid"
        reason = "local_rigid_advantage"
    elif kinematic_wide_beam_gate and bool(kinematic_wide_beam_gate.get("selected")):
        source = "kinematic_wide_beam"
        reason = "wide_texture_guard"
    elif kinematic_beam_gate and bool(kinematic_beam_gate.get("selected")):
        source = "kinematic_beam"
        reason = "appearance_parity_guard"
    elif kinematic_texture_gate and bool(kinematic_texture_gate.get("selected")):
        source = "kinematic_shape"
        reason = "dual_texture_guard"
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
        "kinematic_texture_gate": dict(kinematic_texture_gate or {}),
        "kinematic_beam_gate": dict(kinematic_beam_gate or {}),
        "kinematic_wide_beam_gate": dict(kinematic_wide_beam_gate or {}),
        "kinematic_local_rigid_gate": dict(kinematic_local_rigid_gate or {}),
        "kinematic_explorer_gate": dict(kinematic_explorer_gate or {}),
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
        "local_rigid_residual": evidence.local_rigid_residual,
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
