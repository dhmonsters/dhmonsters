# 병합된 투명도형의 배경 상대 좌표와 분리 신분을 복원합니다.
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot
from statistics import median
from typing import Mapping, Sequence

from .models import Candidate, CandidateEvidence


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


def relative_coordinate_residual(
    current: RelativeCoordinate,
    expected: RelativeCoordinate,
    jitter: float,
) -> float:
    distance = hypot(current.u - expected.u, current.v - expected.v)
    return distance / max(1e-6, float(jitter))


@dataclass(frozen=True)
class BackgroundAnchor:
    track_id: str
    point: Point
    stable_observations: int
    clipped: bool = False


class BackgroundAnchorManager:
    def __init__(self, *, minimum_stable_observations: int = 3) -> None:
        self.minimum_stable_observations = max(1, int(minimum_stable_observations))
        self.reset()

    def reset(self) -> None:
        self._tracks: dict[str, BackgroundAnchor] = {}
        self._next_track_number = 1

    def update(
        self,
        *,
        candidates: Sequence[Candidate],
        target_candidate: Candidate | None,
        evidence: Mapping[str, CandidateEvidence],
        frame_shape: tuple[int, int] | None,
        stable_scale_px: float,
    ) -> tuple[BackgroundAnchor, ...]:
        del evidence
        eligible = [
            candidate
            for candidate in candidates
            if target_candidate is None
            or candidate.candidate_id != target_candidate.candidate_id
        ]
        remaining = list(eligible)
        updated: dict[str, BackgroundAnchor] = {}
        association_limit = max(1.0, float(stable_scale_px))

        for track_id, previous in self._tracks.items():
            if not remaining:
                break
            candidate = min(
                remaining,
                key=lambda row: hypot(
                    row.center[0] - previous.point[0],
                    row.center[1] - previous.point[1],
                ),
            )
            distance = hypot(
                candidate.center[0] - previous.point[0],
                candidate.center[1] - previous.point[1],
            )
            if distance > association_limit:
                continue
            remaining.remove(candidate)
            updated[track_id] = BackgroundAnchor(
                track_id=track_id,
                point=candidate.center,
                stable_observations=previous.stable_observations + 1,
                clipped=_candidate_is_clipped(candidate, frame_shape),
            )

        for candidate in remaining:
            track_id = f"anchor-{self._next_track_number}"
            self._next_track_number += 1
            updated[track_id] = BackgroundAnchor(
                track_id=track_id,
                point=candidate.center,
                stable_observations=1,
                clipped=_candidate_is_clipped(candidate, frame_shape),
            )

        self._tracks = updated
        return tuple(
            anchor
            for anchor in self._tracks.values()
            if anchor.stable_observations >= self.minimum_stable_observations
        )


@dataclass(frozen=True)
class RelationFingerprint:
    pair_coordinates: tuple[tuple[str, str, RelativeCoordinate], ...]
    jitter: float

    @classmethod
    def from_observations(
        cls,
        *,
        background_point: Point,
        anchors: Sequence[BackgroundAnchor],
        jitter: float,
    ) -> "RelationFingerprint":
        rows: list[tuple[str, str, RelativeCoordinate]] = []
        for left_index, left in enumerate(anchors):
            for right in anchors[left_index + 1 :]:
                coordinate = relative_coordinate(background_point, left.point, right.point)
                if coordinate is not None and not left.clipped and not right.clipped:
                    rows.append((left.track_id, right.track_id, coordinate))
        return cls(pair_coordinates=tuple(rows), jitter=max(1e-6, float(jitter)))


@dataclass(frozen=True)
class MergeSplitDecision:
    state: "MergeState"
    background_candidate_id: str | None
    target_candidate_id: str | None
    target_point: Point | None
    relative_margin: float | None
    reason: str
    debug: dict[str, object]


def assign_split_children(
    *,
    children: Sequence[Candidate],
    anchors: Sequence[BackgroundAnchor],
    fingerprint: RelationFingerprint,
    predicted_target_point: Point,
) -> MergeSplitDecision:
    usable = {anchor.track_id: anchor for anchor in anchors if not anchor.clipped}
    child_residuals: list[tuple[float, Candidate]] = []
    for child in children:
        residuals: list[float] = []
        for left_id, right_id, expected in fingerprint.pair_coordinates:
            if left_id not in usable or right_id not in usable:
                continue
            current = relative_coordinate(
                child.center,
                usable[left_id].point,
                usable[right_id].point,
            )
            if current is not None:
                residuals.append(
                    relative_coordinate_residual(current, expected, fingerprint.jitter)
                )
        if residuals:
            child_residuals.append((float(median(residuals)), child))

    debug = {
        "child_residuals": tuple(
            (candidate.candidate_id, residual)
            for residual, candidate in sorted(child_residuals, key=lambda row: row[0])
        ),
        "usable_anchor_ids": tuple(usable),
    }
    if len(child_residuals) < 2:
        return _hold_decision("insufficient_anchors", debug=debug)

    child_residuals.sort(key=lambda row: row[0])
    background_residual, background = child_residuals[0]
    relative_margin = child_residuals[1][0] - background_residual
    if relative_margin <= 1.0:
        return _hold_decision(
            "ambiguous_relation",
            relative_margin=relative_margin,
            debug=debug,
        )

    remaining = [row[1] for row in child_residuals[1:]]
    target = min(
        remaining,
        key=lambda candidate: hypot(
            candidate.center[0] - predicted_target_point[0],
            candidate.center[1] - predicted_target_point[1],
        ),
    )
    return MergeSplitDecision(
        state=MergeState.SPLITTING,
        background_candidate_id=background.candidate_id,
        target_candidate_id=target.candidate_id,
        target_point=target.center,
        relative_margin=relative_margin,
        reason="background_relation_assigned",
        debug=debug,
    )


def _hold_decision(
    reason: str,
    *,
    relative_margin: float | None = None,
    debug: dict[str, object] | None = None,
) -> MergeSplitDecision:
    return MergeSplitDecision(
        state=MergeState.SPLITTING,
        background_candidate_id=None,
        target_candidate_id=None,
        target_point=None,
        relative_margin=relative_margin,
        reason=reason,
        debug=debug or {},
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

    def reset(self) -> None:
        self.state = MergeState.SEPARATE
        self.event_id = 0
        self._pending_state = None
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

        if stable_area > 0.0:
            scale = max(1.0, stable_area**0.5)
            expanded_nearby = []
            for candidate in candidates:
                area_ratio = _bbox_area(candidate.bbox) / stable_area
                proximity = (
                    _point_to_bbox_distance(predicted_target_point, candidate.bbox) / scale
                )
                if area_ratio > 1.25 and proximity <= 0.5:
                    expanded_nearby.append((area_ratio, candidate))
            if len(expanded_nearby) == 1:
                area_ratio, _candidate = expanded_nearby[0]
                return MergeState.MERGED, "expanded_near_prediction", 0.0, area_ratio
            if len(expanded_nearby) > 1:
                return MergeState.SEPARATE, "ambiguous_expanded_candidates", 0.0, max(
                    row[0] for row in expanded_nearby
                )

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


class MergeSplitRelativeResolver:
    def __init__(
        self,
        *,
        event_confirm_observations: int = 2,
        minimum_anchor_observations: int = 3,
    ) -> None:
        self._event_detector = MergeSplitEventDetector(
            confirm_observations=event_confirm_observations
        )
        self._anchor_manager = BackgroundAnchorManager(
            minimum_stable_observations=minimum_anchor_observations
        )
        self.reset()

    def reset(self) -> None:
        self._event_detector.reset()
        self._anchor_manager.reset()
        self._target_points: list[Point] = []
        self._current_anchors: tuple[BackgroundAnchor, ...] = ()
        self._fingerprint: RelationFingerprint | None = None
        self._merge_center: Point | None = None

    def update(
        self,
        *,
        incumbent_point: Point | None,
        candidates: Sequence[Candidate],
        evidence: Mapping[str, CandidateEvidence],
        stable_area: float,
        frame_shape: tuple[int, int] | None,
    ) -> MergeSplitDecision:
        candidate_tuple = tuple(candidates)
        predicted = self._predicted_target_point(incumbent_point, candidate_tuple)
        nearest = _nearest_candidate(candidate_tuple, incumbent_point)
        target_candidate = None
        if nearest is not None:
            area_ratio = _bbox_area(nearest.bbox) / max(1.0, stable_area)
            if area_ratio <= 1.25:
                target_candidate = nearest

        event = self._event_detector.update(
            target_candidate=target_candidate,
            candidates=candidate_tuple,
            stable_area=stable_area,
            predicted_target_point=predicted,
        )
        scale = max(1.0, stable_area**0.5)

        if event.state is MergeState.SEPARATE:
            collision = _nearest_other_candidate(candidate_tuple, target_candidate)
            anchor_candidates = tuple(
                candidate
                for candidate in candidate_tuple
                if (target_candidate is None or candidate is not target_candidate)
                and (collision is None or candidate is not collision)
            )
            self._current_anchors = self._anchor_manager.update(
                candidates=anchor_candidates,
                target_candidate=None,
                evidence=evidence,
                frame_shape=frame_shape,
                stable_scale_px=scale,
            )
            self._remember_target(target_candidate)
            if collision is not None and len(self._current_anchors) >= 2:
                collision_evidence = evidence.get(collision.candidate_id)
                normalized_jitter = 0.0
                if collision_evidence is not None:
                    normalized_jitter = collision_evidence.local_rigid_residual / scale
                self._fingerprint = RelationFingerprint.from_observations(
                    background_point=collision.center,
                    anchors=self._current_anchors[:3],
                    jitter=max(0.02, normalized_jitter),
                )
            self._merge_center = None
            return self._event_hold(event, "separate")

        self._current_anchors = self._anchor_manager.update(
            candidates=candidate_tuple,
            target_candidate=target_candidate,
            evidence=evidence,
            frame_shape=frame_shape,
            stable_scale_px=scale,
        )

        if event.state is MergeState.PARTIAL_OVERLAP:
            overlapping = _most_overlapping_candidate(target_candidate, candidate_tuple)
            if target_candidate is not None and overlapping is not None:
                self._merge_center = (
                    (target_candidate.center[0] + overlapping.center[0]) / 2.0,
                    (target_candidate.center[1] + overlapping.center[1]) / 2.0,
                )
            return self._event_hold(event, "partial_overlap")

        if event.state is MergeState.MERGED:
            merged = _expanded_candidate_near(
                candidate_tuple,
                predicted,
                stable_area,
            )
            if merged is not None:
                self._merge_center = merged.center
            self._advance_latent_target(incumbent_point)
            return self._event_hold(event, "merged_identity_hold")

        if event.state is MergeState.SPLITTING and self._fingerprint is not None:
            child_center = self._merge_center or predicted
            local_children = tuple(
                candidate
                for candidate in candidate_tuple
                if hypot(
                    candidate.center[0] - child_center[0],
                    candidate.center[1] - child_center[1],
                )
                <= 4.0 * scale
            )
            decision = assign_split_children(
                children=local_children,
                anchors=self._current_anchors,
                fingerprint=self._fingerprint,
                predicted_target_point=self._predicted_target_point(
                    incumbent_point,
                    candidate_tuple,
                ),
            )
            return MergeSplitDecision(
                state=event.state,
                background_candidate_id=decision.background_candidate_id,
                target_candidate_id=decision.target_candidate_id,
                target_point=decision.target_point,
                relative_margin=decision.relative_margin,
                reason=decision.reason,
                debug={
                    **decision.debug,
                    "event_id": event.event_id,
                    "local_child_ids": tuple(
                        candidate.candidate_id for candidate in local_children
                    ),
                },
            )

        return self._event_hold(event, "missing_fingerprint")

    def _remember_target(self, candidate: Candidate | None) -> None:
        if candidate is None:
            return
        self._target_points.append(candidate.center)
        self._target_points = self._target_points[-8:]

    def _advance_latent_target(self, fallback: Point | None) -> None:
        point = self._predicted_target_point(fallback, ())
        self._target_points.append(point)
        self._target_points = self._target_points[-8:]

    def _predicted_target_point(
        self,
        fallback: Point | None,
        candidates: Sequence[Candidate],
    ) -> Point:
        if len(self._target_points) >= 2:
            previous = self._target_points[-2]
            latest = self._target_points[-1]
            return (
                latest[0] + latest[0] - previous[0],
                latest[1] + latest[1] - previous[1],
            )
        if self._target_points:
            return self._target_points[-1]
        if fallback is not None:
            return fallback
        if candidates:
            return candidates[0].center
        return (0.0, 0.0)

    @staticmethod
    def _event_hold(event: MergeEvent, reason: str) -> MergeSplitDecision:
        return MergeSplitDecision(
            state=event.state,
            background_candidate_id=None,
            target_candidate_id=None,
            target_point=None,
            relative_margin=None,
            reason=reason,
            debug={
                "event_id": event.event_id,
                "event_reason": event.reason,
                "overlap_ratio": event.overlap_ratio,
                "area_ratio": event.area_ratio,
            },
        )


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


def _nearest_candidate(
    candidates: Sequence[Candidate],
    point: Point | None,
) -> Candidate | None:
    if not candidates or point is None:
        return None
    return min(
        candidates,
        key=lambda candidate: hypot(
            candidate.center[0] - point[0],
            candidate.center[1] - point[1],
        ),
    )


def _nearest_other_candidate(
    candidates: Sequence[Candidate],
    target_candidate: Candidate | None,
) -> Candidate | None:
    if target_candidate is None:
        return None
    others = [candidate for candidate in candidates if candidate is not target_candidate]
    return _nearest_candidate(others, target_candidate.center)


def _most_overlapping_candidate(
    target_candidate: Candidate | None,
    candidates: Sequence[Candidate],
) -> Candidate | None:
    if target_candidate is None:
        return None
    others = [candidate for candidate in candidates if candidate is not target_candidate]
    if not others:
        return None
    candidate = max(
        others,
        key=lambda row: _bbox_intersection(target_candidate.bbox, row.bbox),
    )
    if _bbox_intersection(target_candidate.bbox, candidate.bbox) <= 0.0:
        return None
    return candidate


def _expanded_candidate_near(
    candidates: Sequence[Candidate],
    point: Point,
    stable_area: float,
) -> Candidate | None:
    if stable_area <= 0.0:
        return None
    scale = max(1.0, stable_area**0.5)
    eligible = [
        candidate
        for candidate in candidates
        if _bbox_area(candidate.bbox) / stable_area > 1.25
        and _point_to_bbox_distance(point, candidate.bbox) / scale <= 0.5
    ]
    if len(eligible) != 1:
        return None
    return eligible[0]


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


def _candidate_is_clipped(
    candidate: Candidate,
    frame_shape: tuple[int, int] | None,
) -> bool:
    if frame_shape is None:
        return False
    height, width = frame_shape
    x1, y1, x2, y2 = candidate.bbox
    return x1 <= 0.0 or y1 <= 0.0 or x2 >= float(width) or y2 >= float(height)
