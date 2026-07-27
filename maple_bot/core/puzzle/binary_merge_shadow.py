# 런타임 추적에서 이진 병합 사건과 자식 역할 증거를 구성합니다.
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence

from .binary_merge_background import BackgroundFlowProfile, build_background_flow_profile
from .binary_merge_identity import (
    BinaryMergeIdentityResolver,
    BinaryRoleEvidence,
    BinaryTransferDecision,
    BinaryTransferStatus,
)
from .merge_split_relative import MergeSplitEventDetector, MergeState
from .models import Candidate, CandidateEvidence


_DUPLICATE_IOU = 0.50
_PARENT_REGION_TOLERANCE = 0.25


@dataclass(frozen=True)
class BackgroundRelationSnapshot:
    anchor_candidate_id: str
    anchor_center: tuple[float, float]
    relative_vector_ratio: tuple[float, float]


@dataclass(frozen=True)
class BinaryPremergeSnapshot:
    frame_index: int
    target_candidate_id: str
    background_candidate_id: str
    target_center: tuple[float, float]
    background_center: tuple[float, float]
    target_bbox: tuple[float, float, float, float]
    background_bbox: tuple[float, float, float, float]
    target_velocity: tuple[float, float]
    background_velocity: tuple[float, float]
    neighbor_relations: tuple[BackgroundRelationSnapshot, ...]


@dataclass(frozen=True)
class BinarySplitObservation:
    frame_index: int
    children: tuple[Candidate, Candidate]
    context_candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class BinaryMergeEventWindow:
    event_id: int
    premerge: BinaryPremergeSnapshot
    merge_frame_indices: tuple[int, ...]
    split_frame_indices: tuple[int, ...]
    parent_bboxes: tuple[tuple[float, float, float, float], ...]
    split_observations: tuple[BinarySplitObservation, ...]
    reason: str


@dataclass(frozen=True)
class BinaryEventExtractionDiagnostic:
    frame_index: int
    reason: str
    candidate_count: int


@dataclass(frozen=True)
class BinaryEventExtractionResult:
    events: tuple[BinaryMergeEventWindow, ...]
    diagnostics: tuple[BinaryEventExtractionDiagnostic, ...]


class BinaryEventOutcome(str, Enum):
    CORRECT_TRANSFER = "correct_transfer"
    WRONG_SWITCH = "wrong_switch"
    SAFE_HOLD = "safe_hold"
    LATE_RECOVERY = "late_recovery"
    TARGET_NOT_IN_CANDIDATES = "target_not_in_candidates"
    EVENT_DETECTION_FAILURE = "event_detection_failure"
    DUPLICATE_DETECTION_UNRESOLVED = "duplicate_detection_unresolved"


@dataclass(frozen=True)
class BinaryEventReplay:
    event_id: int
    premerge_frame: int
    split_frame: int | None
    decision_frame: int | None
    split_observations_evaluated: int
    selected_target_candidate_id: str | None
    selected_background_candidate_id: str | None
    decision_reason: str
    hold: bool
    diagnostics: dict[str, object]


@dataclass(frozen=True)
class BinaryEventScore:
    event_id: int
    outcome: BinaryEventOutcome
    target_candidate_id: str | None
    selected_candidate_id: str | None
    recovery_delay_ratio: float | None
    reason: str


@dataclass(frozen=True)
class BinaryEventSummary:
    total_events: int
    correct_transfer: int
    wrong_switches: int
    safe_hold: int
    late_recovery: int
    target_not_in_candidates: int
    event_detection_failure: int
    duplicate_detection_unresolved: int
    resolved_events: int
    median_normalized_recovery_delay: float | None


@dataclass(frozen=True)
class BinaryGateDecision:
    gate_verdict: str
    failure_stage: str | None
    expand_allowed: bool


@dataclass
class _OpenEvent:
    event_id: int
    premerge: BinaryPremergeSnapshot
    merge_frame_indices: list[int]
    split_frame_indices: list[int]
    parent_bboxes: list[tuple[float, float, float, float]]
    split_observations: list[BinarySplitObservation]
    reason: str


def extract_binary_merge_events(
    rows: Sequence[dict[str, Any]],
    event_limit: int | None = None,
) -> BinaryEventExtractionResult:
    """Extract scoreable binary events from runtime trace rows only."""
    if event_limit is not None and event_limit < 1:
        raise ValueError("event_limit must be at least 1")
    frame_rows = _index_runtime_rows(rows)
    detector = MergeSplitEventDetector()
    events: list[BinaryMergeEventWindow] = []
    diagnostics: list[BinaryEventExtractionDiagnostic] = []
    open_event: _OpenEvent | None = None
    suppressed_event_id: int | None = None
    pending_premerge: _FrameRuntime | None = None
    prior: _FrameRuntime | None = None
    trusted_separate_frames: list[_FrameRuntime] = []
    stable_area = 0.0

    def result_limit_reached() -> bool:
        return event_limit is not None and len(events) + len(diagnostics) >= event_limit

    def result() -> BinaryEventExtractionResult:
        return BinaryEventExtractionResult(tuple(events), tuple(diagnostics))

    for frame in frame_rows:
        previous_detector_state = detector.state
        previous_event_id = detector.event_id
        selected_candidate = _selected_candidate(frame.candidates, frame.target_point)
        target_candidate = (
            selected_candidate
            if selected_candidate is not None
            and (
                stable_area <= 0.0
                or _bbox_area(selected_candidate.bbox) / max(1.0, stable_area) <= 1.25
            )
            else None
        )
        collision_candidate = _nearest_other_candidate(target_candidate, frame.candidates)
        event_candidates = tuple(frame.candidates)
        if target_candidate is not None:
            event_candidates = (
                (target_candidate, collision_candidate)
                if collision_candidate is not None
                else (target_candidate,)
            )
        predicted_point = frame.target_point or (selected_candidate.center if selected_candidate else (0.0, 0.0))
        state_event = detector.update(
            target_candidate=target_candidate,
            candidates=event_candidates,
            stable_area=stable_area,
            predicted_target_point=predicted_point,
        )
        if (
            previous_detector_state is MergeState.SPLITTING
            and state_event.state in (MergeState.PARTIAL_OVERLAP, MergeState.MERGED)
            and state_event.event_id == previous_event_id
        ):
            event_id = detector.open_confirmed_merge_event()
        else:
            event_id = state_event.event_id
        in_merge = state_event.state in (MergeState.PARTIAL_OVERLAP, MergeState.MERGED)

        if detector.pending_merge_state is not None and pending_premerge is None:
            pending_premerge = prior

        if open_event is not None and event_id != open_event.event_id:
            _finalize_open_event(open_event, events, diagnostics, frame.frame_index)
            open_event = None
            if result_limit_reached():
                return result()

        if open_event is None and in_merge and suppressed_event_id != event_id:
            premerge = pending_premerge or prior
            pending_premerge = None
            if premerge is None or not _premerge_identity_is_trusted(premerge):
                diagnostics.append(
                    BinaryEventExtractionDiagnostic(
                        frame.frame_index,
                        "premerge_identity_untrusted",
                        len(frame.candidates),
                    )
                )
                suppressed_event_id = event_id
                if result_limit_reached():
                    return result()
            else:
                snapshot = _build_premerge_snapshot(premerge, trusted_separate_frames)
                if snapshot is None:
                    diagnostics.append(
                        BinaryEventExtractionDiagnostic(
                            frame.frame_index,
                            "premerge_identity_untrusted",
                            len(frame.candidates),
                        )
                    )
                    suppressed_event_id = event_id
                    if result_limit_reached():
                        return result()
                else:
                    open_event = _OpenEvent(
                        event_id=event_id,
                        premerge=snapshot,
                        merge_frame_indices=[],
                        split_frame_indices=[],
                        parent_bboxes=[],
                        split_observations=[],
                        reason=state_event.reason,
                    )

        if open_event is not None:
            if in_merge:
                open_event.merge_frame_indices.append(frame.frame_index)
                parent = _merge_parent_bbox(frame.candidates, target_candidate or selected_candidate)
                if parent is not None:
                    open_event.parent_bboxes.append(parent)
            elif len(frame.candidates) >= 2 and detector.pending_merge_state is None:
                children, reason = collapse_physical_candidates(
                    frame.candidates,
                    open_event.parent_bboxes,
                )
                if children is None:
                    diagnostics.append(
                        BinaryEventExtractionDiagnostic(frame.frame_index, reason, len(frame.candidates))
                    )
                    if result_limit_reached():
                        return result()
                else:
                    child_ids = {child.candidate_id for child in children}
                    open_event.split_frame_indices.append(frame.frame_index)
                    open_event.split_observations.append(
                        BinarySplitObservation(
                            frame_index=frame.frame_index,
                            children=children,
                            context_candidates=tuple(
                                candidate for candidate in frame.candidates if candidate.candidate_id not in child_ids
                            ),
                        )
                    )

        if not in_merge and open_event is None and event_id == suppressed_event_id:
            suppressed_event_id = None
        if not in_merge and detector.pending_merge_state is None:
            pending_premerge = None
        if (
            target_candidate is not None
            and previous_detector_state in (MergeState.SEPARATE, MergeState.REACQUIRED)
            and detector.pending_merge_state is None
        ):
            stable_area = _bbox_area(target_candidate.bbox)

        if (
            state_event.state is MergeState.SEPARATE
            and detector.pending_merge_state is None
            and _premerge_identity_is_trusted(frame)
        ):
            trusted_separate_frames.append(frame)

        prior = frame

    if open_event is not None:
        _finalize_open_event(open_event, events, diagnostics, frame_rows[-1].frame_index)
    return result()


def collapse_physical_candidates(
    candidates: Sequence[Candidate],
    parent_bboxes: Sequence[tuple[float, float, float, float]],
) -> tuple[tuple[Candidate, Candidate] | None, str]:
    """Collapse duplicate detections and retain only a physically valid pair."""
    parent_union = _bbox_union_many(parent_bboxes)
    if parent_union is None:
        return None, "missing_merge_parent"
    scale = max(1.0, _bbox_diagonal(parent_union))
    in_region = tuple(
        candidate
        for candidate in candidates
        if _point_to_bbox_distance(candidate.center, parent_union) <= _PARENT_REGION_TOLERANCE * scale
    )
    if len(in_region) < 2:
        return None, "parent_region_violation"

    clusters: list[list[Candidate]] = []
    for candidate in sorted(in_region, key=lambda row: (-row.score, row.candidate_id)):
        matching_indices = [
            index
            for index, cluster in enumerate(clusters)
            if any(_is_physical_duplicate(candidate, representative) for representative in cluster)
        ]
        if not matching_indices:
            clusters.append([candidate])
        else:
            primary_index = matching_indices[0]
            clusters[primary_index].append(candidate)
            for index in reversed(matching_indices[1:]):
                clusters[primary_index].extend(clusters.pop(index))
    representatives = tuple(
        max(cluster, key=lambda row: (row.score, row.candidate_id)) for cluster in clusters
    )
    if len(representatives) != 2:
        return None, "duplicate_detection_unresolved"
    return (representatives[0], representatives[1]), "available"


def build_child_evidence(
    *,
    event: BinaryMergeEventWindow,
    child: Candidate,
    other_child: Candidate,
    context_candidates: Sequence[Candidate],
    flow_profile: BackgroundFlowProfile,
    evidence: Mapping[str, CandidateEvidence],
    frame_shape: tuple[int, int],
) -> BinaryRoleEvidence:
    width = max(1.0, float(frame_shape[1]))
    height = max(1.0, float(frame_shape[0]))
    elapsed = max(1, child.frame_index - event.premerge.frame_index)
    predicted_target = (
        event.premerge.target_center[0] + elapsed * event.premerge.target_velocity[0],
        event.premerge.target_center[1] + elapsed * event.premerge.target_velocity[1],
    )
    flow_dx, flow_dy = flow_profile.velocity_ratio or (0.0, 0.0)
    predicted_background = (
        event.premerge.background_center[0] + elapsed * flow_dx * width,
        event.premerge.background_center[1] + elapsed * flow_dy * height,
    )
    scale = max(
        1.0,
        _bbox_diagonal(event.premerge.target_bbox),
        _bbox_diagonal(event.premerge.background_bbox),
    )
    target_residual = _point_distance(child.center, predicted_target) / scale
    background_residual = (
        _point_distance(child.center, predicted_background) / scale
        if flow_profile.available
        else float("nan")
    )
    ancestry_residual = _children_parent_union_residual(event, child, other_child, scale)
    shape_residual = min(
        _bbox_shape_residual(child.bbox, event.premerge.target_bbox),
        _bbox_shape_residual(child.bbox, event.premerge.background_bbox),
    )
    _candidate_evidence = evidence.get(child.candidate_id)
    neighbor_residual = _neighbor_relation_residual(
        event.premerge.neighbor_relations,
        assumed_background_child=child,
        context_candidates=context_candidates,
        elapsed=elapsed,
        flow_profile=flow_profile,
        frame_shape=frame_shape,
        scale=scale,
    )
    yolo_floor = _relative_yolo_floor((child, other_child))
    return BinaryRoleEvidence(
        candidate_id=child.candidate_id,
        target_motion_residual=target_residual,
        background_motion_residual=background_residual,
        neighbor_relation_residual=neighbor_residual,
        ancestry_residual=ancestry_residual,
        shape_residual=shape_residual,
        yolo_shortfall=max(0.0, yolo_floor - child.score),
        uncertainty=max(
            flow_profile.dispersion if flow_profile.available else 1.0,
            ancestry_residual * 0.25,
        ),
    )


@dataclass(frozen=True)
class _FrameRuntime:
    frame_index: int
    candidates: tuple[Candidate, ...]
    target_point: tuple[float, float] | None
    identity_state: str | None
    white_anchor_point: tuple[float, float] | None


def _index_runtime_rows(rows: Sequence[dict[str, Any]]) -> tuple[_FrameRuntime, ...]:
    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        row_type = row.get("type")
        frame_index = row.get("frame_index")
        payload = row.get("payload")
        if not isinstance(row_type, str) or not isinstance(frame_index, int) or not isinstance(payload, Mapping):
            continue
        current = indexed.setdefault(frame_index, {})
        if row_type == "CANDIDATES":
            current["candidates"] = tuple(
                candidate
                for candidate in (
                    _candidate_from_trace(raw, frame_index) for raw in payload.get("candidates", ())
                )
                if candidate is not None
            )
        elif row_type == "TARGET_SELECTION":
            current["target_point"] = _point_from_value(payload.get("point"))
        elif row_type == "IDENTITY_STATE":
            state = payload.get("state")
            current["identity_state"] = state if isinstance(state, str) else None
        elif row_type == "TEMPORAL_SELECTOR":
            current["white_anchor_point"] = _visible_white_anchor_point(payload)
    return tuple(
        _FrameRuntime(
            frame_index=frame_index,
            candidates=tuple(values.get("candidates", ())),
            target_point=values.get("target_point"),
            identity_state=values.get("identity_state"),
            white_anchor_point=values.get("white_anchor_point"),
        )
        for frame_index, values in sorted(indexed.items())
        if values.get("candidates") is not None
    )


def _candidate_from_trace(raw: object, frame_index: int) -> Candidate | None:
    if not isinstance(raw, Mapping):
        return None
    candidate_id = raw.get("candidate_id")
    bbox = _bbox_from_value(raw.get("bbox"))
    center = _point_from_value(raw.get("center"))
    score = raw.get("score", 0.0)
    source = raw.get("source", "runtime")
    if not isinstance(candidate_id, str) or bbox is None or center is None:
        return None
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not isfinite(score):
        return None
    return Candidate(candidate_id, frame_index, bbox, center, float(score), str(source))


def _build_premerge_snapshot(
    frame: _FrameRuntime,
    trusted_separate_frames: Sequence[_FrameRuntime],
) -> BinaryPremergeSnapshot | None:
    target = _selected_candidate(frame.candidates, frame.target_point)
    if target is None:
        return None
    background = _nearest_other_candidate(target, frame.candidates)
    if background is None:
        return None
    scale = max(1.0, _bbox_diagonal(target.bbox), _bbox_diagonal(background.bbox))
    relations = tuple(
        BackgroundRelationSnapshot(
            anchor_candidate_id=candidate.candidate_id,
            anchor_center=candidate.center,
            relative_vector_ratio=(
                (candidate.center[0] - background.center[0]) / scale,
                (candidate.center[1] - background.center[1]) / scale,
            ),
        )
        for candidate in frame.candidates
        if candidate.candidate_id not in {target.candidate_id, background.candidate_id}
    )
    target_velocity = _selection_velocity(frame, trusted_separate_frames)
    background_velocity = _candidate_velocity(background, frame, trusted_separate_frames)
    return BinaryPremergeSnapshot(
        frame_index=frame.frame_index,
        target_candidate_id=target.candidate_id,
        background_candidate_id=background.candidate_id,
        target_center=target.center,
        background_center=background.center,
        target_bbox=target.bbox,
        background_bbox=background.bbox,
        target_velocity=target_velocity,
        background_velocity=background_velocity,
        neighbor_relations=relations,
    )


def _selection_velocity(
    frame: _FrameRuntime,
    trusted_separate_frames: Sequence[_FrameRuntime],
) -> tuple[float, float]:
    if not any(row.frame_index == frame.frame_index for row in trusted_separate_frames):
        return (0.0, 0.0)
    previous = next(
        (
            row
            for row in reversed(trusted_separate_frames)
            if row.frame_index < frame.frame_index and row.target_point is not None
        ),
        None,
    )
    if previous is None or frame.target_point is None:
        return (0.0, 0.0)
    elapsed = max(1, frame.frame_index - previous.frame_index)
    return (
        (frame.target_point[0] - previous.target_point[0]) / elapsed,
        (frame.target_point[1] - previous.target_point[1]) / elapsed,
    )


def _candidate_velocity(candidate: Candidate, frame: _FrameRuntime, all_frames: Sequence[_FrameRuntime]) -> tuple[float, float]:
    previous = next((row for row in reversed(all_frames) if row.frame_index < frame.frame_index), None)
    if previous is None:
        return (0.0, 0.0)
    prior_candidate = _nearest_candidate(candidate.center, previous.candidates)
    if prior_candidate is None:
        return (0.0, 0.0)
    elapsed = max(1, frame.frame_index - previous.frame_index)
    return (
        (candidate.center[0] - prior_candidate.center[0]) / elapsed,
        (candidate.center[1] - prior_candidate.center[1]) / elapsed,
    )


def _premerge_identity_is_trusted(frame: _FrameRuntime) -> bool:
    if frame.identity_state == "TRACK_CONFIDENT":
        return True
    if frame.identity_state == "IDENTITY_HOLD":
        return False
    if frame.white_anchor_point is None or frame.target_point is None:
        return False
    anchor_candidate = _selected_candidate(frame.candidates, frame.white_anchor_point)
    selected_candidate = _selected_candidate(frame.candidates, frame.target_point)
    return (
        anchor_candidate is not None
        and selected_candidate is not None
        and anchor_candidate.candidate_id == selected_candidate.candidate_id
    )


def _merge_parent_bbox(candidates: Sequence[Candidate], target: Candidate | None) -> tuple[float, float, float, float] | None:
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0].bbox
    if target is None:
        return None
    other = max(
        (candidate for candidate in candidates if candidate.candidate_id != target.candidate_id),
        key=lambda candidate: _bbox_iou(target.bbox, candidate.bbox),
        default=None,
    )
    if other is None or _bbox_iou(target.bbox, other.bbox) <= 0.0:
        return target.bbox
    return _bbox_union(target.bbox, other.bbox)


def _freeze_event(event: _OpenEvent) -> BinaryMergeEventWindow:
    return BinaryMergeEventWindow(
        event_id=event.event_id,
        premerge=event.premerge,
        merge_frame_indices=tuple(event.merge_frame_indices),
        split_frame_indices=tuple(event.split_frame_indices),
        parent_bboxes=tuple(event.parent_bboxes),
        split_observations=tuple(event.split_observations),
        reason=event.reason,
    )


def _finalize_open_event(
    event: _OpenEvent,
    events: list[BinaryMergeEventWindow],
    diagnostics: list[BinaryEventExtractionDiagnostic],
    frame_index: int,
) -> None:
    if event.split_observations:
        events.append(_freeze_event(event))
        return
    diagnostics.append(
        BinaryEventExtractionDiagnostic(
            frame_index,
            "missing_split_children",
            0,
        )
    )


def _selected_candidate(candidates: Sequence[Candidate], point: tuple[float, float] | None) -> Candidate | None:
    if point is None:
        return None
    return _nearest_candidate(point, candidates)


def _nearest_candidate(point: tuple[float, float], candidates: Sequence[Candidate]) -> Candidate | None:
    return min(candidates, key=lambda candidate: _point_distance(point, candidate.center), default=None)


def _nearest_other_candidate(target: Candidate | None, candidates: Sequence[Candidate]) -> Candidate | None:
    if target is None:
        return None
    return min(
        (candidate for candidate in candidates if candidate.candidate_id != target.candidate_id),
        key=lambda candidate: _point_distance(target.center, candidate.center),
        default=None,
    )


def _visible_white_anchor_point(payload: Mapping[str, Any]) -> tuple[float, float] | None:
    debug = payload.get("debug")
    if not isinstance(debug, Mapping):
        return None
    gate = debug.get("kinematic_wide_beam_debug")
    if not isinstance(gate, Mapping) or gate.get("reason") != "white_anchor":
        return None
    return _point_from_value(gate.get("point"))


def _children_parent_union_residual(
    event: BinaryMergeEventWindow,
    child: Candidate,
    other_child: Candidate,
    scale: float,
) -> float:
    parent_union = _bbox_union_many(event.parent_bboxes)
    if parent_union is None:
        return float("inf")
    child_union = _bbox_union(child.bbox, other_child.bbox)
    parent_width = parent_union[2] - parent_union[0]
    parent_height = parent_union[3] - parent_union[1]
    child_width = child_union[2] - child_union[0]
    child_height = child_union[3] - child_union[1]
    return (abs(child_width - parent_width) + abs(child_height - parent_height)) / (2.0 * scale)


def _bbox_shape_residual(
    current: tuple[float, float, float, float],
    reference: tuple[float, float, float, float],
) -> float:
    current_width = max(1e-6, current[2] - current[0])
    current_height = max(1e-6, current[3] - current[1])
    reference_width = max(1e-6, reference[2] - reference[0])
    reference_height = max(1e-6, reference[3] - reference[1])
    return hypot(
        (current_width - reference_width) / max(current_width, reference_width),
        (current_height - reference_height) / max(current_height, reference_height),
    )


def _neighbor_relation_residual(
    relations: Sequence[BackgroundRelationSnapshot],
    *,
    assumed_background_child: Candidate,
    context_candidates: Sequence[Candidate],
    elapsed: int,
    flow_profile: BackgroundFlowProfile,
    frame_shape: tuple[int, int],
    scale: float,
) -> float | None:
    if not relations or not flow_profile.available or flow_profile.velocity_ratio is None:
        return None
    width = max(1.0, float(frame_shape[1]))
    height = max(1.0, float(frame_shape[0]))
    flow_x, flow_y = flow_profile.velocity_ratio
    residuals: list[float] = []
    used_anchor_ids: set[str] = set()
    for relation in relations:
        predicted_anchor = (
            relation.anchor_center[0] + elapsed * flow_x * width,
            relation.anchor_center[1] + elapsed * flow_y * height,
        )
        ranked = sorted(
            (
                (_point_distance(candidate.center, predicted_anchor), candidate)
                for candidate in context_candidates
            ),
            key=lambda row: (row[0], row[1].candidate_id),
        )
        if not ranked or ranked[0][0] > scale:
            return None
        if len(ranked) > 1 and ranked[1][0] - ranked[0][0] <= 0.10 * scale:
            return None
        anchor = ranked[0][1]
        if anchor.candidate_id in used_anchor_ids:
            return None
        used_anchor_ids.add(anchor.candidate_id)
        current_ratio = (
            (anchor.center[0] - assumed_background_child.center[0]) / scale,
            (anchor.center[1] - assumed_background_child.center[1]) / scale,
        )
        residuals.append(_point_distance(current_ratio, relation.relative_vector_ratio))
    return median(residuals) if len(residuals) == len(relations) else None


def _relative_yolo_floor(children: tuple[Candidate, Candidate]) -> float:
    return float(median(child.score for child in children))


def _is_physical_duplicate(left: Candidate, right: Candidate) -> bool:
    return (
        _bbox_iou(left.bbox, right.bbox) >= _DUPLICATE_IOU
        and _point_distance(left.center, right.center) <= max(_bbox_diagonal(left.bbox), _bbox_diagonal(right.bbox))
    )


def _bbox_diagonal(bbox: tuple[float, float, float, float]) -> float:
    return hypot(max(0.0, bbox[2] - bbox[0]), max(0.0, bbox[3] - bbox[1]))


def _point_distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return hypot(left[0] - right[0], left[1] - right[1])


def _bbox_union(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return min(left[0], right[0]), min(left[1], right[1]), max(left[2], right[2]), max(left[3], right[3])


def _bbox_union_many(bboxes: Sequence[tuple[float, float, float, float]]) -> tuple[float, float, float, float] | None:
    if not bboxes:
        return None
    result = bboxes[0]
    for bbox in bboxes[1:]:
        result = _bbox_union(result, bbox)
    return result


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def _bbox_iou(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> float:
    overlap = (
        max(left[0], right[0]),
        max(left[1], right[1]),
        min(left[2], right[2]),
        min(left[3], right[3]),
    )
    intersection = _bbox_area(overlap)
    union = _bbox_area(left) + _bbox_area(right) - intersection
    return intersection / union if union > 0.0 else 0.0


def _point_to_bbox_distance(point: tuple[float, float], bbox: tuple[float, float, float, float]) -> float:
    dx = max(bbox[0] - point[0], 0.0, point[0] - bbox[2])
    dy = max(bbox[1] - point[1], 0.0, point[1] - bbox[3])
    return hypot(dx, dy)


def _point_from_value(value: object) -> tuple[float, float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
        return None
    if not all(isinstance(item, (int, float)) and not isinstance(item, bool) and isfinite(item) for item in value):
        return None
    return float(value[0]), float(value[1])


def _bbox_from_value(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 4:
        return None
    if not all(isinstance(item, (int, float)) and not isinstance(item, bool) and isfinite(item) for item in value):
        return None
    bbox = tuple(float(item) for item in value)
    if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
        return None
    return bbox


def replay_binary_merge_events(
    trace_jsonl: str | Path,
    event_limit: int | None = None,
) -> tuple[BinaryEventReplay, ...]:
    """Replay binary merge decisions from runtime trace data only."""
    rows = _read_jsonl(Path(trace_jsonl))
    frame_shape = _board_frame_shape(rows)
    extraction = extract_binary_merge_events(rows, event_limit=event_limit)
    resolver = BinaryMergeIdentityResolver()
    replays: list[BinaryEventReplay] = []

    for event in extraction.events:
        profile = _profile_from_preparation_rows(
            rows,
            frame_shape,
            before_frame_index=event.premerge.frame_index,
        )
        decisions: list[tuple[int, BinaryTransferDecision]] = []
        for observation in event.split_observations:
            child_a, child_b = observation.children
            evidence = _evidence_for_frame(rows, observation.frame_index)
            decision = resolver.evaluate(
                event_id=event.event_id,
                child_a=build_child_evidence(
                    event=event,
                    child=child_a,
                    other_child=child_b,
                    context_candidates=observation.context_candidates,
                    flow_profile=profile,
                    evidence=evidence,
                    frame_shape=frame_shape,
                ),
                child_b=build_child_evidence(
                    event=event,
                    child=child_b,
                    other_child=child_a,
                    context_candidates=observation.context_candidates,
                    flow_profile=profile,
                    evidence=evidence,
                    frame_shape=frame_shape,
                ),
            )
            decisions.append((observation.frame_index, decision))
            if decision.status is BinaryTransferStatus.RESOLVED:
                break
        replays.append(_event_replay_from_decisions(event, decisions))

    for index, diagnostic in enumerate(extraction.diagnostics, start=1):
        replays.append(
            BinaryEventReplay(
                event_id=-index,
                premerge_frame=diagnostic.frame_index,
                split_frame=diagnostic.frame_index,
                decision_frame=None,
                split_observations_evaluated=0,
                selected_target_candidate_id=None,
                selected_background_candidate_id=None,
                decision_reason=diagnostic.reason,
                hold=True,
                diagnostics={
                    "source": "extraction",
                    "extraction_reason": diagnostic.reason,
                    "candidate_count": diagnostic.candidate_count,
                },
            )
        )
    return tuple(sorted(replays, key=lambda replay: (replay.premerge_frame, replay.event_id)))


def score_binary_merge_events(
    replays: Sequence[BinaryEventReplay],
    score_jsonl: str | Path,
    trace_jsonl: str | Path,
) -> tuple[BinaryEventScore, ...]:
    """Associate ground truth with completed runtime replay rows only after replay."""
    score_rows = _read_jsonl(Path(score_jsonl))
    candidate_rows = _candidate_rows_by_frame(_read_jsonl(Path(trace_jsonl)))
    results: list[BinaryEventScore] = []
    for replay in replays:
        scoring_frame = replay.decision_frame or replay.split_frame
        target_point = _aligned_target_point(score_rows, scoring_frame)
        target_candidate_id = _target_child_id(
            target_point,
            scoring_frame,
            candidate_rows,
            _physical_child_ids(replay, scoring_frame),
        )
        results.append(_score_one_event(replay, target_candidate_id))
    return tuple(results)


def summarize_binary_merge_events(scores: Sequence[BinaryEventScore]) -> BinaryEventSummary:
    counts = {outcome: 0 for outcome in BinaryEventOutcome}
    for score in scores:
        counts[score.outcome] += 1
    delays = [
        score.recovery_delay_ratio
        for score in scores
        if score.recovery_delay_ratio is not None
    ]
    resolved_outcomes = {
        BinaryEventOutcome.CORRECT_TRANSFER,
        BinaryEventOutcome.WRONG_SWITCH,
        BinaryEventOutcome.LATE_RECOVERY,
    }
    return BinaryEventSummary(
        total_events=len(scores),
        correct_transfer=counts[BinaryEventOutcome.CORRECT_TRANSFER],
        wrong_switches=counts[BinaryEventOutcome.WRONG_SWITCH],
        safe_hold=counts[BinaryEventOutcome.SAFE_HOLD],
        late_recovery=counts[BinaryEventOutcome.LATE_RECOVERY],
        target_not_in_candidates=counts[BinaryEventOutcome.TARGET_NOT_IN_CANDIDATES],
        event_detection_failure=counts[BinaryEventOutcome.EVENT_DETECTION_FAILURE],
        duplicate_detection_unresolved=counts[BinaryEventOutcome.DUPLICATE_DETECTION_UNRESOLVED],
        resolved_events=sum(1 for score in scores if score.outcome in resolved_outcomes),
        median_normalized_recovery_delay=median(delays) if delays else None,
    )


def evaluate_binary_merge_gate(
    replays: Sequence[BinaryEventReplay],
    scores: Sequence[BinaryEventScore],
) -> BinaryGateDecision:
    if len(replays) != 1 or len(scores) != 1:
        return BinaryGateDecision("GATE_FAILED", "event_detection", False)
    replay = replays[0]
    score = scores[0]
    extraction_reason = replay.diagnostics.get("extraction_reason")
    if isinstance(extraction_reason, str):
        return BinaryGateDecision(
            "GATE_FAILED",
            _canonical_failure_stage(extraction_reason, score.outcome),
            False,
        )
    if replay.split_frame is None:
        return BinaryGateDecision("GATE_FAILED", "event_detection", False)
    if replay.decision_frame is not None and replay.decision_frame < replay.split_frame:
        return BinaryGateDecision("GATE_FAILED", "target_judge", False)
    if score.outcome is BinaryEventOutcome.TARGET_NOT_IN_CANDIDATES:
        return BinaryGateDecision("GATE_FAILED", "candidate_absence", False)
    if replay.hold:
        return BinaryGateDecision(
            "GATE_FAILED",
            _canonical_failure_stage(replay.decision_reason, score.outcome),
            False,
        )
    correct_outcomes = {
        BinaryEventOutcome.CORRECT_TRANSFER,
        BinaryEventOutcome.LATE_RECOVERY,
    }
    if (
        score.outcome not in correct_outcomes
        or score.target_candidate_id is None
        or score.target_candidate_id != replay.selected_target_candidate_id
    ):
        return BinaryGateDecision(
            "GATE_FAILED",
            _canonical_failure_stage(score.reason, score.outcome),
            False,
        )
    return BinaryGateDecision("PASSED", None, True)


def render_binary_merge_event_markdown(
    replays: Sequence[BinaryEventReplay],
    scores: Sequence[BinaryEventScore],
    gate_decision: BinaryGateDecision | None = None,
) -> str:
    """Render one compact diagnostic section per binary merge event."""
    summary = summarize_binary_merge_events(scores)
    gate = gate_decision or evaluate_binary_merge_gate(replays, scores)
    score_by_event = {score.event_id: score for score in scores}
    lines = [
        "# Binary Merge Event Summary",
        "",
        f"- gate_verdict: {gate.gate_verdict}",
        f"- failure_stage: {gate.failure_stage or 'none'}",
        f"- expand_allowed: {str(gate.expand_allowed).lower()}",
        "",
        f"- total_events: {summary.total_events}",
        f"- resolved_events: {summary.resolved_events}",
        f"- correct_transfer: {summary.correct_transfer}",
        f"- wrong_switches: {summary.wrong_switches}",
        f"- safe_hold: {summary.safe_hold}",
        f"- late_recovery: {summary.late_recovery}",
        f"- target_not_in_candidates: {summary.target_not_in_candidates}",
        f"- event_detection_failure: {summary.event_detection_failure}",
        f"- duplicate_detection_unresolved: {summary.duplicate_detection_unresolved}",
        "",
    ]
    for replay in replays:
        score = score_by_event.get(replay.event_id)
        decisions = replay.diagnostics.get("decisions")
        final_decision = decisions[-1] if isinstance(decisions, tuple) and decisions else None
        lines.extend(
            [
                f"## Event {replay.event_id}",
                "",
                f"- outcome: {score.outcome.value if score else 'unscored'}",
                f"- runtime_decision: {replay.decision_reason}",
                f"- selected_target: {replay.selected_target_candidate_id or 'none'}",
                f"- ground_truth_target: {score.target_candidate_id if score and score.target_candidate_id else 'none'}",
            ]
        )
        if replay.hold:
            lines.append(f"- HOLD: {replay.decision_reason}")
        lines.append(f"- H1: {_render_hypothesis_contribution(final_decision, 'h1')}")
        lines.append(f"- H2: {_render_hypothesis_contribution(final_decision, 'h2')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _binary_merge_event_output_row(
    replay: BinaryEventReplay,
    score: BinaryEventScore,
    gate_decision: BinaryGateDecision,
) -> dict[str, object]:
    return {
        "event_id": replay.event_id,
        "gate_verdict": gate_decision.gate_verdict,
        "failure_stage": gate_decision.failure_stage,
        "expand_allowed": gate_decision.expand_allowed,
        "runtime_decision": {
            "premerge_frame": replay.premerge_frame,
            "split_frame": replay.split_frame,
            "decision_frame": replay.decision_frame,
            "split_observations_evaluated": replay.split_observations_evaluated,
            "selected_target_candidate_id": replay.selected_target_candidate_id,
            "selected_background_candidate_id": replay.selected_background_candidate_id,
            "reason": replay.decision_reason,
            "hold": replay.hold,
        },
        "post_hoc_score": {
            "outcome": score.outcome.value,
            "target_candidate_id": score.target_candidate_id,
            "selected_candidate_id": score.selected_candidate_id,
            "recovery_delay_ratio": score.recovery_delay_ratio,
            "reason": score.reason,
        },
        "judge_diagnostics": replay.diagnostics,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate binary merge identity transfer events.")
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--score", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--event-limit", type=int, default=None)
    args = parser.parse_args(argv)
    if args.event_limit is not None and args.event_limit < 1:
        parser.error("--event-limit must be at least 1")

    replays = replay_binary_merge_events(args.trace, event_limit=args.event_limit)
    scores = score_binary_merge_events(replays, args.score, args.trace)
    gate_decision = evaluate_binary_merge_gate(replays, scores)
    args.output.mkdir(parents=True, exist_ok=True)
    event_rows = (
        json.dumps(
            _binary_merge_event_output_row(replay, score, gate_decision),
            ensure_ascii=False,
            sort_keys=True,
        )
        for replay, score in zip(replays, scores)
    )
    (args.output / "binary_merge_events.jsonl").write_text(
        "".join(f"{row}\n" for row in event_rows),
        encoding="utf-8",
    )
    (args.output / "binary_merge_validation.md").write_text(
        render_binary_merge_event_markdown(replays, scores, gate_decision),
        encoding="utf-8",
    )
    return 0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _board_frame_shape(rows: Sequence[dict[str, Any]]) -> tuple[int, int]:
    for row in rows:
        if row.get("type") != "SESSION_START":
            continue
        payload = row.get("payload")
        board_roi = payload.get("board_roi") if isinstance(payload, Mapping) else None
        if not isinstance(board_roi, Mapping):
            continue
        frame_shape = _frame_shape_from_value((board_roi.get("h"), board_roi.get("w")))
        if frame_shape is not None:
            return frame_shape
    for row in rows:
        payload = row.get("payload")
        if not isinstance(payload, Mapping):
            continue
        frame_shape = _frame_shape_from_value(payload.get("frame_shape"))
        if frame_shape is not None:
            return frame_shape
    return (1, 1)


def _profile_from_preparation_rows(
    rows: Sequence[dict[str, Any]],
    frame_shape: tuple[int, int],
    *,
    before_frame_index: int,
) -> BackgroundFlowProfile:
    preparation_frames: list[tuple[int, tuple[Candidate, ...]]] = []
    for frame in _index_runtime_rows(rows):
        if frame.frame_index >= before_frame_index:
            break
        candidates = frame.candidates
        if _premerge_identity_is_trusted(frame):
            known_target = _selected_candidate(frame.candidates, frame.target_point)
            if known_target is not None:
                candidates = tuple(
                    candidate
                    for candidate in candidates
                    if candidate.candidate_id != known_target.candidate_id
                )
        preparation_frames.append((frame.frame_index, candidates))
    return build_background_flow_profile(tuple(preparation_frames), frame_shape=frame_shape)


def _evidence_for_frame(
    rows: Sequence[dict[str, Any]],
    frame_index: int,
) -> dict[str, CandidateEvidence]:
    evidence: dict[str, CandidateEvidence] = {}
    for row in rows:
        if row.get("type") != "EVIDENCE" or row.get("frame_index") != frame_index:
            continue
        payload = row.get("payload")
        raw_evidence = payload.get("evidence") if isinstance(payload, Mapping) else None
        if not isinstance(raw_evidence, Sequence) or isinstance(raw_evidence, (str, bytes)):
            continue
        for raw in raw_evidence:
            if not isinstance(raw, Mapping):
                continue
            candidate_id = raw.get("candidate_id")
            if not isinstance(candidate_id, str) or not candidate_id:
                continue
            notes = raw.get("notes")
            evidence[candidate_id] = CandidateEvidence(
                candidate_id=candidate_id,
                bg_score=_nonnegative_float(raw.get("bg_score")),
                motion_divergence=_nonnegative_float(raw.get("motion_divergence")),
                rigid_violation=_nonnegative_float(raw.get("rigid_violation")),
                local_rigid_residual=_nonnegative_float(raw.get("local_rigid_residual")),
                phase_similarity=_nonnegative_float(raw.get("phase_similarity")),
                texture_bg_score=_nonnegative_float(raw.get("texture_bg_score")),
                color_residual=_nonnegative_float(raw.get("color_residual")),
                merge_likelihood=_nonnegative_float(raw.get("merge_likelihood")),
                notes=tuple(note for note in notes if isinstance(note, str))
                if isinstance(notes, Sequence) and not isinstance(notes, (str, bytes))
                else (),
            )
    return evidence


def _event_replay_from_decisions(
    event: BinaryMergeEventWindow,
    decisions: Sequence[tuple[int, BinaryTransferDecision]],
) -> BinaryEventReplay:
    resolved = next(
        ((frame_index, decision) for frame_index, decision in decisions if decision.status is BinaryTransferStatus.RESOLVED),
        None,
    )
    final_decision = decisions[-1][1] if decisions else None
    split_child_ids = {
        observation.frame_index: tuple(child.candidate_id for child in observation.children)
        for observation in event.split_observations
    }
    return BinaryEventReplay(
        event_id=event.event_id,
        premerge_frame=event.premerge.frame_index,
        split_frame=event.split_observations[0].frame_index if event.split_observations else None,
        decision_frame=resolved[0] if resolved is not None else None,
        split_observations_evaluated=len(decisions),
        selected_target_candidate_id=resolved[1].target_candidate_id if resolved is not None else None,
        selected_background_candidate_id=resolved[1].background_candidate_id if resolved is not None else None,
        decision_reason=final_decision.reason if final_decision is not None else "missing_split_observations",
        hold=resolved is None,
        diagnostics={
            "source": "runtime_replay",
            "event_reason": event.reason,
            "split_child_ids": split_child_ids,
            "physical_child_ids_by_frame": split_child_ids,
            "decisions": tuple(
                _decision_diagnostic(frame_index, decision) for frame_index, decision in decisions
            ),
        },
    )


def _candidate_rows_by_frame(rows: Sequence[dict[str, Any]]) -> dict[int, tuple[Candidate, ...]]:
    candidates_by_frame: dict[int, tuple[Candidate, ...]] = {}
    for row in rows:
        if row.get("type") != "CANDIDATES":
            continue
        frame_index = row.get("frame_index")
        payload = row.get("payload")
        if not isinstance(frame_index, int) or not isinstance(payload, Mapping):
            continue
        raw_candidates = payload.get("candidates")
        if not isinstance(raw_candidates, Sequence) or isinstance(raw_candidates, (str, bytes)):
            continue
        candidates_by_frame[frame_index] = tuple(
            candidate
            for candidate in (
                _candidate_from_trace(raw_candidate, frame_index) for raw_candidate in raw_candidates
            )
            if candidate is not None
        )
    return candidates_by_frame


def _aligned_target_point(
    score_rows: Sequence[dict[str, Any]],
    frame_index: int | None,
) -> tuple[float, float] | None:
    if frame_index is None:
        return None
    for row in score_rows:
        score_frame = row.get("solver_frame_index", row.get("frame_index"))
        if score_frame != frame_index:
            continue
        target_point = _point_from_value(row.get("target_point"))
        if target_point is not None:
            return target_point
        target_x = row.get("target_x")
        target_y = row.get("target_y")
        if _is_finite_number(target_x) and _is_finite_number(target_y):
            return float(target_x), float(target_y)
    return None


def _target_child_id(
    target_point: tuple[float, float] | None,
    frame_index: int | None,
    candidate_rows: Mapping[int, Sequence[Candidate]],
    physical_child_ids: Sequence[str],
) -> str | None:
    if target_point is None or frame_index is None:
        return None
    physical_ids = set(physical_child_ids)
    candidates = tuple(
        candidate
        for candidate in candidate_rows.get(frame_index, ())
        if candidate.candidate_id in physical_ids
    )
    covered = [candidate for candidate in candidates if _point_in_bbox(target_point, candidate.bbox)]
    if covered:
        return min(
            covered,
            key=lambda candidate: (_point_distance(target_point, candidate.center), candidate.candidate_id),
        ).candidate_id
    centered = [
        candidate
        for candidate in candidates
        if _point_distance(target_point, candidate.center) <= 1e-6
    ]
    return min(centered, key=lambda candidate: candidate.candidate_id).candidate_id if centered else None


def _score_one_event(
    replay: BinaryEventReplay,
    target_candidate_id: str | None,
) -> BinaryEventScore:
    extraction_reason = replay.diagnostics.get("extraction_reason")
    if isinstance(extraction_reason, str):
        outcome = (
            BinaryEventOutcome.DUPLICATE_DETECTION_UNRESOLVED
            if extraction_reason == "duplicate_detection_unresolved"
            else BinaryEventOutcome.EVENT_DETECTION_FAILURE
        )
        return BinaryEventScore(
            event_id=replay.event_id,
            outcome=outcome,
            target_candidate_id=None,
            selected_candidate_id=None,
            recovery_delay_ratio=None,
            reason=extraction_reason,
        )

    scoring_frame = replay.decision_frame or replay.split_frame
    if target_candidate_id not in _physical_child_ids(replay, scoring_frame):
        return BinaryEventScore(
            event_id=replay.event_id,
            outcome=BinaryEventOutcome.TARGET_NOT_IN_CANDIDATES,
            target_candidate_id=target_candidate_id,
            selected_candidate_id=replay.selected_target_candidate_id,
            recovery_delay_ratio=_recovery_delay_ratio(replay),
            reason="target_not_in_physical_children",
        )
    if replay.hold or replay.selected_target_candidate_id is None:
        return BinaryEventScore(
            event_id=replay.event_id,
            outcome=BinaryEventOutcome.SAFE_HOLD,
            target_candidate_id=target_candidate_id,
            selected_candidate_id=None,
            recovery_delay_ratio=None,
            reason=replay.decision_reason,
        )

    delay = _recovery_delay_ratio(replay)
    if replay.selected_target_candidate_id != target_candidate_id:
        return BinaryEventScore(
            event_id=replay.event_id,
            outcome=BinaryEventOutcome.WRONG_SWITCH,
            target_candidate_id=target_candidate_id,
            selected_candidate_id=replay.selected_target_candidate_id,
            recovery_delay_ratio=delay,
            reason="selected_wrong_split_child",
        )
    return BinaryEventScore(
        event_id=replay.event_id,
        outcome=(
            BinaryEventOutcome.LATE_RECOVERY
            if delay is not None and delay > 0.0
            else BinaryEventOutcome.CORRECT_TRANSFER
        ),
        target_candidate_id=target_candidate_id,
        selected_candidate_id=replay.selected_target_candidate_id,
        recovery_delay_ratio=delay,
        reason="target_identity_transferred",
    )


def _canonical_failure_stage(
    reason: str,
    outcome: BinaryEventOutcome,
) -> str:
    if reason in {
        "duplicate_detection_unresolved",
        "parent_region_violation",
        "missing_merge_parent",
    }:
        return "candidate_normalization"
    if outcome is BinaryEventOutcome.TARGET_NOT_IN_CANDIDATES:
        return "candidate_absence"
    if outcome in {
        BinaryEventOutcome.EVENT_DETECTION_FAILURE,
        BinaryEventOutcome.DUPLICATE_DETECTION_UNRESOLVED,
    }:
        return "event_detection"
    if "background" in reason:
        return "background_judge"
    if "ancestry" in reason:
        return "ancestry"
    if "ambiguous" in reason:
        return "ambiguity"
    return "target_judge"


def _decision_diagnostic(
    frame_index: int,
    decision: BinaryTransferDecision,
) -> dict[str, object]:
    return {
        "frame_index": frame_index,
        "status": decision.status.value,
        "reason": decision.reason,
        "normalized_margin": decision.normalized_margin,
        "h1": _hypothesis_diagnostic(decision.debug.get("h1")),
        "h2": _hypothesis_diagnostic(decision.debug.get("h2")),
    }


def _hypothesis_diagnostic(hypothesis: object) -> dict[str, object] | None:
    if hypothesis is None:
        return None
    support_groups = getattr(hypothesis, "support_groups", ())
    if not isinstance(support_groups, tuple):
        return None
    return {
        "target_candidate_id": getattr(hypothesis, "target_candidate_id", None),
        "background_candidate_id": getattr(hypothesis, "background_candidate_id", None),
        "target_cost": getattr(hypothesis, "target_cost", None),
        "background_cost": getattr(hypothesis, "background_cost", None),
        "support_groups": support_groups,
    }


def _physical_child_ids(replay: BinaryEventReplay, frame_index: int | None) -> tuple[str, ...]:
    if frame_index is None:
        return ()
    for key in ("split_child_ids", "physical_child_ids_by_frame"):
        frames = replay.diagnostics.get(key)
        if not isinstance(frames, Mapping):
            continue
        candidate_ids = frames.get(frame_index)
        if not isinstance(candidate_ids, Sequence) or isinstance(candidate_ids, (str, bytes)):
            continue
        return tuple(candidate_id for candidate_id in candidate_ids if isinstance(candidate_id, str))
    return ()


def _recovery_delay_ratio(replay: BinaryEventReplay) -> float | None:
    if replay.decision_frame is None or replay.split_observations_evaluated <= 0:
        return None
    return (replay.split_observations_evaluated - 1) / max(
        1,
        replay.split_observations_evaluated - 1,
    )


def _render_hypothesis_contribution(decision: object, name: str) -> str:
    if not isinstance(decision, Mapping):
        return "unavailable"
    hypothesis = decision.get(name)
    if not isinstance(hypothesis, Mapping):
        return "unavailable"
    support_groups = hypothesis.get("support_groups")
    support = ", ".join(group for group in support_groups if isinstance(group, str)) if isinstance(support_groups, Sequence) else ""
    return (
        f"target={hypothesis.get('target_candidate_id') or 'none'}, "
        f"background={hypothesis.get('background_candidate_id') or 'none'}, "
        f"target_cost={hypothesis.get('target_cost')}, "
        f"background_cost={hypothesis.get('background_cost')}, "
        f"support={support or 'none'}"
    )


def _frame_shape_from_value(value: object) -> tuple[int, int] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) != 2:
        return None
    height, width = value
    if not _is_finite_number(height) or not _is_finite_number(width):
        return None
    if height <= 0 or width <= 0:
        return None
    return int(height), int(width)


def _point_in_bbox(point: tuple[float, float], bbox: tuple[float, float, float, float]) -> bool:
    return bbox[0] <= point[0] <= bbox[2] and bbox[1] <= point[1] <= bbox[3]


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


def _nonnegative_float(value: object) -> float:
    return float(value) if _is_finite_number(value) and value >= 0.0 else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
