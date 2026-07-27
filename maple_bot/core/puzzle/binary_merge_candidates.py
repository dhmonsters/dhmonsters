# 병합 사건 지역의 검출 제안을 물리 후보 쌍으로 정규화한다.
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import hypot
from statistics import median
from typing import Sequence

from .models import Candidate


BoundingBox = tuple[float, float, float, float]

_DUPLICATE_CENTER_RATIO = 0.25
_DUPLICATE_IOU = 0.50
_DUPLICATE_SHAPE_RATIO = 0.70


@dataclass(frozen=True)
class CandidateLocalizationContext:
    target_center: tuple[float, float]
    background_center: tuple[float, float]
    target_bbox: BoundingBox
    background_bbox: BoundingBox
    parent_bboxes: tuple[BoundingBox, ...]
    uncertainty_ratio: float


@dataclass(frozen=True)
class CandidateCluster:
    candidate: Candidate
    members: tuple[Candidate, ...]


@dataclass(frozen=True)
class CandidatePairHypothesis:
    clusters: tuple[CandidateCluster, CandidateCluster]
    target_residual: float
    background_residual: float
    parent_residual: float


@dataclass(frozen=True)
class CandidatePairLocalization:
    clusters: tuple[CandidateCluster, ...]
    pairs: tuple[CandidatePairHypothesis, ...]
    reason: str


def localize_candidate_pairs(
    candidates: Sequence[Candidate],
    context: CandidateLocalizationContext,
) -> CandidatePairLocalization:
    """Return all non-dominated physical candidate pairs in the event region."""
    parent_union = _bbox_union_many(context.parent_bboxes)
    if parent_union is None:
        return CandidatePairLocalization((), (), "candidate_absent")

    stable_scale = max(
        1.0,
        median((_bbox_diagonal(context.target_bbox), _bbox_diagonal(context.background_bbox))),
    )
    uncertainty = max(0.0, float(context.uncertainty_ratio))
    role_radius = stable_scale * (1.0 + uncertainty)
    parent_radius = stable_scale * (0.25 + uncertainty)
    local_candidates = tuple(
        candidate
        for candidate in candidates
        if _point_to_bbox_distance(candidate.center, parent_union) <= parent_radius
        and min(
            _point_distance(candidate.center, context.target_center),
            _point_distance(candidate.center, context.background_center),
        ) <= role_radius
    )
    clusters = _physical_clusters(local_candidates)
    pairs = _nondominated_pairs(
        clusters,
        context,
        stable_scale,
        parent_union,
        role_radius,
        uncertainty,
    )
    reason = "candidate_absent" if not pairs else "available" if len(pairs) == 1 else "pair_ambiguous"
    return CandidatePairLocalization(clusters, pairs, reason)


def _physical_clusters(candidates: Sequence[Candidate]) -> tuple[CandidateCluster, ...]:
    ordered = tuple(sorted(candidates, key=lambda candidate: candidate.candidate_id))
    connected: list[set[int]] = [{index} for index in range(len(ordered))]
    for left_index, right_index in combinations(range(len(ordered)), 2):
        if _same_physical_candidate(ordered[left_index], ordered[right_index]):
            connected[left_index].add(right_index)
            connected[right_index].add(left_index)

    components: list[tuple[Candidate, ...]] = []
    unseen = set(range(len(ordered)))
    while unseen:
        pending = [min(unseen)]
        component: set[int] = set()
        while pending:
            current = pending.pop()
            if current in component:
                continue
            component.add(current)
            pending.extend(connected[current] - component)
        unseen -= component
        components.append(tuple(ordered[index] for index in sorted(component)))

    clusters = tuple(
        CandidateCluster(
            candidate=max(members, key=lambda candidate: (candidate.score, candidate.candidate_id)),
            members=members,
        )
        for members in components
    )
    return tuple(sorted(clusters, key=lambda cluster: cluster.candidate.candidate_id))


def _same_physical_candidate(left: Candidate, right: Candidate) -> bool:
    left_size = _bbox_size(left.bbox)
    right_size = _bbox_size(right.bbox)
    shape_ratio = min(
        left_size[0] / max(1e-6, right_size[0]),
        right_size[0] / max(1e-6, left_size[0]),
        left_size[1] / max(1e-6, right_size[1]),
        right_size[1] / max(1e-6, left_size[1]),
    )
    center_scale = max(1.0, _bbox_diagonal(left.bbox), _bbox_diagonal(right.bbox))
    return (
        _point_distance(left.center, right.center) / center_scale <= _DUPLICATE_CENTER_RATIO
        and _bbox_iou(left.bbox, right.bbox) >= _DUPLICATE_IOU
        and shape_ratio >= _DUPLICATE_SHAPE_RATIO
    )


def _nondominated_pairs(
    clusters: Sequence[CandidateCluster],
    context: CandidateLocalizationContext,
    stable_scale: float,
    parent_union: BoundingBox,
    role_radius: float,
    uncertainty: float,
) -> tuple[CandidatePairHypothesis, ...]:
    hypotheses: list[CandidatePairHypothesis] = []
    for left, right in combinations(clusters, 2):
        role_residuals = _role_residuals(
            left.candidate,
            right.candidate,
            context,
            stable_scale,
            role_radius,
        )
        if role_residuals is None:
            continue
        parent_residual = _parent_residual(left.candidate.bbox, right.candidate.bbox, parent_union, stable_scale)
        if parent_residual > 0.50 + uncertainty:
            continue
        hypotheses.append(
            CandidatePairHypothesis(
                clusters=(left, right),
                target_residual=role_residuals[0],
                background_residual=role_residuals[1],
                parent_residual=parent_residual,
            )
        )

    retained = tuple(
        hypothesis
        for hypothesis in hypotheses
        if not any(
            _dominates(other, hypothesis)
            for other in hypotheses
            if other is not hypothesis
        )
    )
    return tuple(sorted(retained, key=_pair_sort_key))


def _role_residuals(
    left: Candidate,
    right: Candidate,
    context: CandidateLocalizationContext,
    stable_scale: float,
    role_radius: float,
) -> tuple[float, float] | None:
    assignments = []
    for target, background in ((left, right), (right, left)):
        target_distance = _point_distance(target.center, context.target_center)
        background_distance = _point_distance(background.center, context.background_center)
        if target_distance <= role_radius and background_distance <= role_radius:
            assignments.append((target_distance / stable_scale, background_distance / stable_scale))
    return min(assignments, key=lambda residuals: (sum(residuals), residuals)) if assignments else None


def _parent_residual(
    left: BoundingBox,
    right: BoundingBox,
    parent: BoundingBox,
    stable_scale: float,
) -> float:
    child_union = _bbox_union(left, right)
    return sum(abs(child_union[index] - parent[index]) for index in range(4)) / (4.0 * stable_scale)


def _dominates(left: CandidatePairHypothesis, right: CandidatePairHypothesis) -> bool:
    left_residuals = (left.target_residual, left.background_residual, left.parent_residual)
    right_residuals = (right.target_residual, right.background_residual, right.parent_residual)
    return all(left_value <= right_value for left_value, right_value in zip(left_residuals, right_residuals)) and any(
        left_value < right_value for left_value, right_value in zip(left_residuals, right_residuals)
    )


def _pair_sort_key(hypothesis: CandidatePairHypothesis) -> tuple[tuple[str, str], tuple[float, float, float]]:
    return (
        tuple(cluster.candidate.candidate_id for cluster in hypothesis.clusters),
        (hypothesis.target_residual, hypothesis.background_residual, hypothesis.parent_residual),
    )


def _bbox_union_many(bboxes: Sequence[BoundingBox]) -> BoundingBox | None:
    if not bboxes:
        return None
    return (
        min(bbox[0] for bbox in bboxes),
        min(bbox[1] for bbox in bboxes),
        max(bbox[2] for bbox in bboxes),
        max(bbox[3] for bbox in bboxes),
    )


def _bbox_union(left: BoundingBox, right: BoundingBox) -> BoundingBox:
    return (
        min(left[0], right[0]),
        min(left[1], right[1]),
        max(left[2], right[2]),
        max(left[3], right[3]),
    )


def _bbox_iou(left: BoundingBox, right: BoundingBox) -> float:
    intersection = max(0.0, min(left[2], right[2]) - max(left[0], right[0])) * max(
        0.0,
        min(left[3], right[3]) - max(left[1], right[1]),
    )
    union = _bbox_area(left) + _bbox_area(right) - intersection
    return intersection / union if union > 0.0 else 0.0


def _bbox_area(bbox: BoundingBox) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def _bbox_size(bbox: BoundingBox) -> tuple[float, float]:
    return max(0.0, bbox[2] - bbox[0]), max(0.0, bbox[3] - bbox[1])


def _bbox_diagonal(bbox: BoundingBox) -> float:
    width, height = _bbox_size(bbox)
    return hypot(width, height)


def _point_distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return hypot(left[0] - right[0], left[1] - right[1])


def _point_to_bbox_distance(point: tuple[float, float], bbox: BoundingBox) -> float:
    return hypot(
        max(bbox[0] - point[0], 0.0, point[0] - bbox[2]),
        max(bbox[1] - point[1], 0.0, point[1] - bbox[3]),
    )
