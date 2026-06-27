# planet_solver_noauth 방식의 실시간 CCTV 표시와 마우스 이동을 제공한다.
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.puzzle.defaults import fixed_detect_roi, fixed_popup_preview_roi
from core.puzzle.evidence import EvidenceJudges
from core.puzzle.identity import IdentityTracker
from core.puzzle.models import Candidate, CandidateEvidence, FramePacket, IdentityDecision, RoiSpec
from core.puzzle.roi import crop_by_roi


CursorSetter = Callable[[int, int], None]
CursorDetector = Callable[[Any], tuple[float, float] | None]


@dataclass(frozen=True)
class MouseMoveResult:
    moved: bool
    abs_point: tuple[int, int] | None
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
    mouse_move: MouseMoveResult | None = None


class PlanetMouseController:
    def __init__(
        self,
        *,
        cursor_setter: CursorSetter | None = None,
        cursor_detector: CursorDetector | None = None,
        offset_limit: float = 200.0,
        offset_alpha: float = 0.5,
    ) -> None:
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
    ) -> MouseMoveResult:
        if point is None:
            return MouseMoveResult(False, None, None, (self.offset_x, self.offset_y), "no_target")
        if not enabled:
            return MouseMoveResult(False, None, point, (self.offset_x, self.offset_y), "disabled")

        cx = max(0.0, min(float(detect_roi.w - 1), float(point[0])))
        cy = max(0.0, min(float(detect_roi.h - 1), float(point[1])))
        if det_frame is not None:
            cursor = self.cursor_detector(det_frame)
            if cursor is not None:
                self.offset_x += (cx - float(cursor[0])) * self.offset_alpha
                self.offset_y += (cy - float(cursor[1])) * self.offset_alpha
                self.offset_x = _clamp(self.offset_x, -self.offset_limit, self.offset_limit)
                self.offset_y = _clamp(self.offset_y, -self.offset_limit, self.offset_limit)

        abs_x = detect_roi.x + int(cx + self.offset_x)
        abs_y = detect_roi.y + int(cy + self.offset_y)
        self.cursor_setter(abs_x, abs_y)
        return MouseMoveResult(True, (abs_x, abs_y), (cx, cy), (self.offset_x, self.offset_y), "moved")


class PlanetLiveSolver:
    def __init__(
        self,
        *,
        detector: Any | None = None,
        mouse: PlanetMouseController | None = None,
        evidence_judges: EvidenceJudges | None = None,
        identity_tracker: IdentityTracker | None = None,
    ) -> None:
        self.detector = detector
        self.mouse = mouse or PlanetMouseController()
        self.evidence_judges = evidence_judges or EvidenceJudges()
        self.identity_tracker = identity_tracker or IdentityTracker()
        self._noauth_detector: Any | None = None
        self._noauth_detector_loaded = False

    def analyze(self, packet: FramePacket, *, solver_running: bool) -> PlanetLiveResult:
        detect_payload = packet.roi_snapshot.get("detect", {})
        board_payload = packet.roi_snapshot.get("board", {})
        detect_roi = _roi_from_payload(detect_payload, fallback_name="detect")
        board_roi = _roi_from_payload(board_payload, fallback_name="board")
        det_frame = crop_by_roi(packet.source_frame, detect_roi)
        raw_rows = self._detect_rows(det_frame)
        candidates = _candidates_from_det_rows(
            raw_rows,
            frame_index=packet.frame_index,
            detect_roi=detect_roi,
            board_roi=board_roi,
        )
        evidence = self.evidence_judges.score(candidates, packet)
        decision = self.identity_tracker.update(
            frame_index=packet.frame_index,
            candidates=candidates,
            evidence=evidence,
        )
        det_point = _board_point_to_det_point(decision.point, detect_roi=detect_roi, board_roi=board_roi)
        mouse_move = self.mouse.move_to_det_point(
            detect_roi=detect_roi,
            point=det_point,
            det_frame=det_frame,
            enabled=solver_running,
        )
        det_candidates = _det_rows_from_candidates(candidates, detect_roi=detect_roi, board_roi=board_roi)
        preview = render_planet_cctv_preview(
            packet.source_frame,
            candidates=det_candidates,
            track_pos=det_point,
            engine=_decision_engine_name(decision),
        )
        return PlanetLiveResult(
            preview_frame=preview,
            trace_events=_trace_events(candidates, evidence, decision, mouse_move),
            candidates=candidates,
            evidence=evidence,
            decision=decision,
            mouse_move=mouse_move,
        )

    def _detect_rows(self, det_frame: Any) -> Sequence[Any]:
        detector = self.detector or self._load_noauth_detector()
        if detector is None or not getattr(detector, "enabled", True):
            return []
        try:
            return list(detector.detect_all(det_frame))
        except Exception:
            return []

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
    detect_roi = fixed_detect_roi(frame_w=frame_w, frame_h=frame_h)
    popup = crop_by_roi(frame, popup_roi)
    vis = popup.copy()
    cv2 = _cv2()
    header_h = int(round(frame_h * 0.061))
    cv2.rectangle(vis, (0, 0), (popup_roi.w - 1, max(0, header_h - 1)), (0, 230, 255), 2)
    score_text = "HDR score --" if popup_score is None else f"HDR score={popup_score:.2f} / thr=0.50"
    cv2.putText(vis, score_text, (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 230, 255), 1, cv2.LINE_AA)

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
                source="raw",
                class_name=parsed["class_name"],
            )
        )
    return candidates


def _parse_row(row: Any) -> dict[str, float | str]:
    if isinstance(row, dict):
        return {
            "cx": float(row["cx"]),
            "cy": float(row["cy"]),
            "score": float(row["score"]),
            "w": float(row["w"]),
            "h": float(row["h"]),
            "class_name": str(row.get("class_name", "")),
        }
    return {
        "cx": float(row[0]),
        "cy": float(row[1]),
        "score": float(row[2]),
        "w": float(row[3]) if len(row) > 3 else 20.0,
        "h": float(row[4]) if len(row) > 4 else 20.0,
        "class_name": str(row[5]) if len(row) > 5 else "",
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


def _board_point_to_det_point(
    point: tuple[float, float] | None,
    *,
    detect_roi: RoiSpec,
    board_roi: RoiSpec,
) -> tuple[float, float] | None:
    if point is None:
        return None
    return (float(point[0]) - (detect_roi.x - board_roi.x), float(point[1]) - (detect_roi.y - board_roi.y))


def _trace_events(
    candidates: Sequence[Candidate],
    evidence: dict[str, CandidateEvidence],
    decision: IdentityDecision,
    mouse_move: MouseMoveResult,
) -> list[tuple[str, dict[str, object]]]:
    return [
        (
            "CANDIDATES",
            {
                "count": len(candidates),
                "candidates": [_candidate_payload(candidate) for candidate in candidates],
                "debug": {"source": "planet_live"},
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
        (
            "MOUSE_MOVE",
            {
                "moved": mouse_move.moved,
                "abs_point": mouse_move.abs_point,
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


def _decision_engine_name(decision: IdentityDecision) -> str:
    if decision.candidate_id:
        return "ID"
    return "WAIT"


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
