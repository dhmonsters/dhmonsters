# 병합된 투명도형의 배경 상대 좌표와 분리 신분을 복원합니다.
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot

from .models import Candidate


Point = tuple[float, float]


@dataclass(frozen=True)
class RelativeCoordinate:
    u: float
    v: float


def relative_coordinate(
    point: Point,
    anchor_a: Point,
    anchor_b: Point,
) -> RelativeCoordinate | None:
    dx = anchor_b[0] - anchor_a[0]
    dy = anchor_b[1] - anchor_a[1]
    length = hypot(dx, dy)
    if length <= 1e-6:
        return None

    px = point[0] - anchor_a[0]
    py = point[1] - anchor_a[1]
    denominator = length * length
    return RelativeCoordinate(
        u=(px * dx + py * dy) / denominator,
        v=(dx * py - dy * px) / denominator,
    )


class MergeState(str, Enum):
    SEPARATE = "separate"
    PARTIAL_OVERLAP = "partial_overlap"
    MERGED = "merged"
    SPLITTING = "splitting"
    REACQUIRED = "reacquired"


@dataclass(frozen=True)
class MergeEvent:
    event_id: int
    state: MergeState
    reason: str
    overlap_ratio: float
    area_ratio: float
    candidate_count: int


class MergeSplitEventDetector:
    def __init__(self, *, confirm_observations: int = 2) -> None:
        if confirm_observations < 1:
            raise ValueError("confirm_observations must be positive")
        self.confirm_observations = confirm_observations
        self.state = MergeState.SEPARATE
        self.event_id = 0
        self._pending_state: MergeState | None = None
        self._pending_count = 0

    def update(
        self,
        *,
        target_candidate: Candidate | None,
        candidates: tuple[Candidate, ...],
        stable_area: float,
        predicted_target_point: Point,
    ) -> MergeEvent:
        observed, reason, overlap_ratio, area_ratio = self._observe(
            target_candidate=target_candidate,
            candidates=candidates,
            stable_area=stable_area,
            predicted_target_point=predicted_target_point,
        )

        if (
            self.state in (MergeState.PARTIAL_OVERLAP, MergeState.MERGED)
            and observed is MergeState.SEPARATE
            and len(candidates) >= 2
        ):
            self._set_state(MergeState.SPLITTING)
            reason = "children_separated"
        elif self.state is MergeState.SPLITTING and observed is MergeState.SEPARATE:
            self._set_state(MergeState.REACQUIRED)
            reason = "split_reacquired"
        elif observed in (MergeState.PARTIAL_OVERLAP, MergeState.MERGED):
            if observed is self._pending_state:
                self._pending_count += 1
            else:
                self._pending_state = observed
                self._pending_count = 1
            if self._pending_count >= self.confirm_observations:
                self._set_state(observed)
        elif self.state in (MergeState.SEPARATE, MergeState.REACQUIRED):
            self._set_state(MergeState.SEPARATE, increment_event=False)

        return MergeEvent(
            event_id=self.event_id,
            state=self.state,
            reason=reason,
            overlap_ratio=overlap_ratio,
            area_ratio=area_ratio,
            candidate_count=len(candidates),
        )

    def _observe(
        self,
        *,
        target_candidate: Candidate | None,
        candidates: tuple[Candidate, ...],
        stable_area: float,
        predicted_target_point: Point,
    ) -> tuple[MergeState, str, float, float]:
        overlap_ratio = _maximum_target_overlap(target_candidate, candidates)
        if overlap_ratio >= 0.15:
            return MergeState.PARTIAL_OVERLAP, "target_overlap", overlap_ratio, 1.0

        if len(candidates) == 1 and stable_area > 0.0:
            candidate = candidates[0]
            area_ratio = _bbox_area(candidate.bbox) / stable_area
            scale = max(1.0, stable_area**0.5)
            proximity = _point_to_bbox_distance(predicted_target_point, candidate.bbox) / scale
            if area_ratio > 1.25 and proximity <= 0.5:
                return MergeState.MERGED, "expanded_near_prediction", 0.0, area_ratio
            return MergeState.SEPARATE, "single_candidate", 0.0, area_ratio

        return MergeState.SEPARATE, "separate_candidates", overlap_ratio, 1.0

    def _set_state(self, state: MergeState, *, increment_event: bool = True) -> None:
        if state is self.state:
            return
        if increment_event and state in (
            MergeState.PARTIAL_OVERLAP,
            MergeState.MERGED,
            MergeState.SPLITTING,
        ):
            self.event_id += 1
        self.state = state
        self._pending_state = None
        self._pending_count = 0


def _maximum_target_overlap(
    target_candidate: Candidate | None,
    candidates: tuple[Candidate, ...],
) -> float:
    if target_candidate is None:
        return 0.0
    target_area = _bbox_area(target_candidate.bbox)
    if target_area <= 0.0:
        return 0.0
    return max(
        (
            _bbox_intersection(target_candidate.bbox, candidate.bbox) / target_area
            for candidate in candidates
            if candidate.candidate_id != target_candidate.candidate_id
        ),
        default=0.0,
    )


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def _bbox_intersection(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    width = max(0.0, min(left[2], right[2]) - max(left[0], right[0]))
    height = max(0.0, min(left[3], right[3]) - max(left[1], right[1]))
    return width * height


def _point_to_bbox_distance(
    point: Point,
    bbox: tuple[float, float, float, float],
) -> float:
    dx = max(bbox[0] - point[0], 0.0, point[0] - bbox[2])
    dy = max(bbox[1] - point[1], 0.0, point[1] - bbox[3])
    return hypot(dx, dy)
