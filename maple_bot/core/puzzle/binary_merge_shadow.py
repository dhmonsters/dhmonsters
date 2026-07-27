# 런타임 추적에서 이진 병합 사건과 자식 역할 증거를 구성합니다.
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from statistics import median
from typing import Any, Mapping, Sequence

from .binary_merge_background import BackgroundFlowProfile
from .binary_merge_identity import BinaryRoleEvidence
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


@dataclass
class _OpenEvent:
    event_id: int
    premerge: BinaryPremergeSnapshot
    merge_frame_indices: list[int]
    split_frame_indices: list[int]
    parent_bboxes: list[tuple[float, float, float, float]]
    split_observations: list[BinarySplitObservation]
    reason: str


def extract_binary_merge_events(rows: Sequence[dict[str, Any]]) -> BinaryEventExtractionResult:
    """Extract scoreable binary events from runtime trace rows only."""
    frame_rows = _index_runtime_rows(rows)
    detector = MergeSplitEventDetector(confirm_observations=1)
    events: list[BinaryMergeEventWindow] = []
    diagnostics: list[BinaryEventExtractionDiagnostic] = []
    open_event: _OpenEvent | None = None
    suppressed_event_id: int | None = None
    prior: _FrameRuntime | None = None

    for frame in frame_rows:
        target_candidate = _selected_candidate(frame.candidates, frame.target_point)
        stable_target = (
            open_event.premerge.target_bbox
            if open_event is not None
            else (
                _selected_candidate(prior.candidates, prior.target_point).bbox
                if prior is not None and _selected_candidate(prior.candidates, prior.target_point) is not None
                else None
            )
        )
        stable_area = _bbox_area(stable_target) if stable_target is not None else 0.0
        predicted_point = frame.target_point or (target_candidate.center if target_candidate else (0.0, 0.0))
        state_event = detector.update(
            target_candidate=target_candidate,
            candidates=frame.candidates,
            stable_area=stable_area,
            predicted_target_point=predicted_point,
        )
        in_merge = state_event.state in (MergeState.PARTIAL_OVERLAP, MergeState.MERGED)

        if open_event is None and in_merge and suppressed_event_id != state_event.event_id:
            if prior is None or not _premerge_identity_is_trusted(prior):
                diagnostics.append(
                    BinaryEventExtractionDiagnostic(
                        frame.frame_index,
                        "premerge_identity_untrusted",
                        len(frame.candidates),
                    )
                )
                suppressed_event_id = state_event.event_id
            else:
                snapshot = _build_premerge_snapshot(prior, frame_rows)
                if snapshot is None:
                    diagnostics.append(
                        BinaryEventExtractionDiagnostic(
                            frame.frame_index,
                            "premerge_identity_untrusted",
                            len(frame.candidates),
                        )
                    )
                    suppressed_event_id = state_event.event_id
                else:
                    open_event = _OpenEvent(
                        event_id=state_event.event_id,
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
                parent = _merge_parent_bbox(frame.candidates, target_candidate)
                if parent is not None:
                    open_event.parent_bboxes.append(parent)
            elif len(frame.candidates) >= 2:
                children, reason = collapse_physical_candidates(
                    frame.candidates,
                    open_event.parent_bboxes,
                )
                if children is None:
                    diagnostics.append(
                        BinaryEventExtractionDiagnostic(frame.frame_index, reason, len(frame.candidates))
                    )
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
                    events.append(_freeze_event(open_event))
                    detector.complete_split_recovery()
                    open_event = None

        if not in_merge and open_event is None and state_event.event_id == suppressed_event_id:
            suppressed_event_id = None

        prior = frame

    if open_event is not None:
        if not open_event.split_observations:
            diagnostics.append(
                BinaryEventExtractionDiagnostic(
                    open_event.merge_frame_indices[-1],
                    "missing_split_children",
                    0,
                )
            )
        else:
            events.append(_freeze_event(open_event))
    return BinaryEventExtractionResult(tuple(events), tuple(diagnostics))


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
        matching = next(
            (
                cluster
                for cluster in clusters
                if any(_is_physical_duplicate(candidate, representative) for representative in cluster)
            ),
            None,
        )
        if matching is None:
            clusters.append([candidate])
        else:
            matching.append(candidate)
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
    white_anchor: bool


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
            current["white_anchor"] = _has_visible_white_anchor(payload)
    return tuple(
        _FrameRuntime(
            frame_index=frame_index,
            candidates=tuple(values.get("candidates", ())),
            target_point=values.get("target_point"),
            identity_state=values.get("identity_state"),
            white_anchor=bool(values.get("white_anchor")),
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


def _build_premerge_snapshot(frame: _FrameRuntime, all_frames: Sequence[_FrameRuntime]) -> BinaryPremergeSnapshot | None:
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
    target_velocity = _selection_velocity(frame, all_frames)
    background_velocity = _candidate_velocity(background, frame, all_frames)
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


def _selection_velocity(frame: _FrameRuntime, all_frames: Sequence[_FrameRuntime]) -> tuple[float, float]:
    previous = next((row for row in reversed(all_frames) if row.frame_index < frame.frame_index and row.target_point is not None), None)
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
    return frame.identity_state == "TRACK_CONFIDENT" or frame.white_anchor


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


def _selected_candidate(candidates: Sequence[Candidate], point: tuple[float, float] | None) -> Candidate | None:
    if point is None:
        return None
    return _nearest_candidate(point, candidates)


def _nearest_candidate(point: tuple[float, float], candidates: Sequence[Candidate]) -> Candidate | None:
    return min(candidates, key=lambda candidate: _point_distance(point, candidate.center), default=None)


def _nearest_other_candidate(target: Candidate, candidates: Sequence[Candidate]) -> Candidate | None:
    return min(
        (candidate for candidate in candidates if candidate.candidate_id != target.candidate_id),
        key=lambda candidate: _point_distance(target.center, candidate.center),
        default=None,
    )


def _has_visible_white_anchor(payload: Mapping[str, Any]) -> bool:
    debug = payload.get("debug")
    if not isinstance(debug, Mapping):
        return False
    gate = debug.get("kinematic_wide_beam_debug")
    return isinstance(gate, Mapping) and gate.get("reason") == "white_anchor"


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
    return sum(abs(left - right) for left, right in zip(child_union, parent_union)) / (4.0 * scale)


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
    for relation in relations:
        predicted_anchor = (
            relation.anchor_center[0] + elapsed * flow_x * width,
            relation.anchor_center[1] + elapsed * flow_y * height,
        )
        anchor = _nearest_candidate(predicted_anchor, context_candidates)
        if anchor is None or _point_distance(anchor.center, predicted_anchor) > scale:
            continue
        current_ratio = (
            (anchor.center[0] - assumed_background_child.center[0]) / scale,
            (anchor.center[1] - assumed_background_child.center[1]) / scale,
        )
        residuals.append(_point_distance(current_ratio, relation.relative_vector_ratio))
    return median(residuals) if residuals else None


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
