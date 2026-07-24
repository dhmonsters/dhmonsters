# 병합된 투명도형의 배경 상대 좌표와 분리 신분을 복원합니다.
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from itertools import combinations
from math import hypot
from statistics import median
from typing import Mapping, Sequence

from .models import Candidate, CandidateEvidence


Point = tuple[float, float]
_MAX_PHASE_FINGERPRINT_ANCHORS = 6
_MIN_AFFINE_TRIANGLE_QUALITY = 0.05


@dataclass(frozen=True)
class RelativeCoordinate:
    u: float
    v: float


@dataclass(frozen=True)
class AffineCoordinate:
    a: float
    b: float
    c: float


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


def affine_coordinate(
    point: Point,
    anchor_a: Point,
    anchor_b: Point,
    anchor_c: Point,
) -> AffineCoordinate | None:
    bx = anchor_b[0] - anchor_a[0]
    by = anchor_b[1] - anchor_a[1]
    cx = anchor_c[0] - anchor_a[0]
    cy = anchor_c[1] - anchor_a[1]
    determinant = bx * cy - by * cx
    scale_squared = max(
        bx * bx + by * by,
        cx * cx + cy * cy,
        (anchor_c[0] - anchor_b[0]) ** 2 + (anchor_c[1] - anchor_b[1]) ** 2,
    )
    if (
        abs(determinant) / max(1e-6, scale_squared)
        <= _MIN_AFFINE_TRIANGLE_QUALITY
    ):
        return None

    px = point[0] - anchor_a[0]
    py = point[1] - anchor_a[1]
    b = (px * cy - py * cx) / determinant
    c = (bx * py - by * px) / determinant
    return AffineCoordinate(a=1.0 - b - c, b=b, c=c)


def affine_coordinate_residual(
    current: AffineCoordinate,
    expected: AffineCoordinate,
    jitter: float,
) -> float:
    distance = hypot(
        current.a - expected.a,
        current.b - expected.b,
        current.c - expected.c,
    )
    return distance / max(1e-6, float(jitter))


@dataclass(frozen=True)
class CyclePhaseContext:
    period: int | None
    local_lag: int | None
    period_score: float | None = None


@dataclass(frozen=True)
class AnchorObservation:
    frame_index: int
    candidate_id: str
    point: Point
    bbox: tuple[float, float, float, float]
    area: float
    aspect: float
    clipped: bool
    merge_like: bool


@dataclass(frozen=True)
class BackgroundAnchor:
    track_id: str
    point: Point
    stable_observations: int
    clipped: bool = False
    candidate_id: str | None = None
    qualified_cycle: bool = False
    cycle_survival: float = 0.0
    loop_residual: float | None = None
    disqualified_reason: str | None = None


def nearest_background_anchors(
    *,
    background_point: Point,
    anchors: Sequence[BackgroundAnchor],
    limit: int = 3,
) -> tuple[BackgroundAnchor, ...]:
    usable = [anchor for anchor in anchors if not anchor.clipped]
    usable.sort(
        key=lambda anchor: hypot(
            anchor.point[0] - background_point[0],
            anchor.point[1] - background_point[1],
        )
    )
    return tuple(usable[: max(0, int(limit))])


def _bounded_phase_reference_anchors(
    *,
    background_point: Point,
    anchors: Sequence[BackgroundAnchor],
    limit: int,
) -> tuple[BackgroundAnchor, ...]:
    selected, _quality = _select_bounded_phase_reference_anchors(
        background_point=background_point,
        anchors=anchors,
        limit=limit,
    )
    return selected


def _select_bounded_phase_reference_anchors(
    *,
    background_point: Point,
    anchors: Sequence[BackgroundAnchor],
    limit: int,
) -> tuple[tuple[BackgroundAnchor, ...], float | None]:
    ordered = tuple(
        sorted(
            anchors,
            key=lambda anchor: (
                hypot(
                    anchor.point[0] - background_point[0],
                    anchor.point[1] - background_point[1],
                ),
                anchor.track_id,
            ),
        )
    )
    maximum = max(0, int(limit))
    if maximum <= 0:
        return (), None

    def distance(anchor: BackgroundAnchor) -> float:
        return hypot(
            anchor.point[0] - background_point[0],
            anchor.point[1] - background_point[1],
        )

    coordinate_scale = max(1.0, *(distance(anchor) for anchor in ordered))
    duplicate_tolerance = 1e-6 * coordinate_scale
    unique_anchors: list[BackgroundAnchor] = []
    for anchor in ordered:
        if any(
            hypot(
                anchor.point[0] - representative.point[0],
                anchor.point[1] - representative.point[1],
            )
            <= duplicate_tolerance
            for representative in unique_anchors
        ):
            continue
        unique_anchors.append(anchor)
    if len(unique_anchors) <= 1 or maximum <= 1:
        return tuple(unique_anchors[:maximum]), None

    def triangle_quality(
        first: BackgroundAnchor,
        second: BackgroundAnchor,
        third: BackgroundAnchor,
    ) -> float:
        first_to_second = (
            second.point[0] - first.point[0],
            second.point[1] - first.point[1],
        )
        first_to_third = (
            third.point[0] - first.point[0],
            third.point[1] - first.point[1],
        )
        determinant = abs(
            first_to_second[0] * first_to_third[1]
            - first_to_second[1] * first_to_third[0]
        )
        scale_squared = max(
            first_to_second[0] ** 2 + first_to_second[1] ** 2,
            first_to_third[0] ** 2 + first_to_third[1] ** 2,
            (third.point[0] - second.point[0]) ** 2
            + (third.point[1] - second.point[1]) ** 2,
        )
        return determinant / max(1e-6, scale_squared)

    best_triple: tuple[BackgroundAnchor, BackgroundAnchor, BackgroundAnchor] | None = None
    best_quality: float | None = None
    if maximum >= 3:
        for triple in combinations(unique_anchors, 3):
            quality = triangle_quality(*triple)
            if quality <= _MIN_AFFINE_TRIANGLE_QUALITY:
                continue
            if best_triple is None or best_quality is None or (
                -quality,
                sum(distance(anchor) for anchor in triple),
                tuple(anchor.track_id for anchor in triple),
            ) < (
                -best_quality,
                sum(distance(anchor) for anchor in best_triple),
                tuple(anchor.track_id for anchor in best_triple),
            ):
                best_triple = triple
                best_quality = quality

    selected: list[BackgroundAnchor] = []
    if best_triple is not None:
        first = min(best_triple, key=lambda anchor: (distance(anchor), anchor.track_id))
        remaining = tuple(anchor for anchor in best_triple if anchor is not first)
        second = min(
            remaining,
            key=lambda anchor: (
                -hypot(
                    anchor.point[0] - first.point[0],
                    anchor.point[1] - first.point[1],
                ),
                anchor.track_id,
            ),
        )
        third = next(anchor for anchor in remaining if anchor is not second)
        selected.extend((first, second, third))

    selected_ids = {anchor.track_id for anchor in selected}
    selected.extend(
        anchor
        for anchor in unique_anchors
        if anchor.track_id not in selected_ids
    )
    return tuple(selected[:maximum]), best_quality


@dataclass
class _BackgroundAnchorTrack:
    track_id: str
    observations: dict[int, AnchorObservation]
    qualification_by_frame: dict[int, "_AnchorQualificationSnapshot"] = field(
        default_factory=dict
    )
    lifetime_disqualified_reason: str | None = None
    qualified_cycle: bool = False
    cycle_survival: float = 0.0
    loop_residual: float | None = None
    disqualified_reason: str | None = None

    @property
    def latest_observation(self) -> AnchorObservation:
        return self.observations[max(self.observations)]


@dataclass(frozen=True)
class _AnchorQualificationSnapshot:
    stable_observations: int
    qualified_cycle: bool
    cycle_survival: float
    loop_residual: float | None
    disqualified_reason: str | None


class BackgroundAnchorManager:
    def __init__(
        self,
        *,
        minimum_stable_observations: int = 3,
        minimum_cycle_survival: float = 0.95,
        maximum_cycle_gap_ratio: float = 0.05,
        loop_position_tolerance: float = 0.75,
        loop_shape_tolerance: float = 0.25,
    ) -> None:
        self.minimum_stable_observations = max(1, int(minimum_stable_observations))
        self.minimum_cycle_survival = min(1.0, max(0.0, float(minimum_cycle_survival)))
        self.maximum_cycle_gap_ratio = min(
            1.0, max(0.0, float(maximum_cycle_gap_ratio))
        )
        self.loop_position_tolerance = max(0.0, float(loop_position_tolerance))
        self.loop_shape_tolerance = max(0.0, float(loop_shape_tolerance))
        self.reset()

    def reset(self) -> None:
        self._tracks: dict[str, _BackgroundAnchorTrack] = {}
        self._active_track_ids: set[str] = set()
        self._candidate_track_ids: dict[str, str] = {}
        self._next_track_number = 1
        self._implicit_frame_index = -1

    def update(
        self,
        *,
        candidates: Sequence[Candidate],
        target_candidate: Candidate | None,
        evidence: Mapping[str, CandidateEvidence],
        frame_shape: tuple[int, int] | None,
        stable_scale_px: float,
        excluded_candidate_ids: Sequence[str] = (),
        frame_index: int | None = None,
        phase_context: CyclePhaseContext | None = None,
    ) -> tuple[BackgroundAnchor, ...]:
        current_frame = self._resolve_frame_index(frame_index)
        excluded_ids = set(excluded_candidate_ids)
        eligible = [
            candidate
            for candidate in candidates
            if candidate.candidate_id not in excluded_ids
            and (
                target_candidate is None
                or candidate.candidate_id != target_candidate.candidate_id
            )
        ]
        remaining = list(eligible)
        association_limit = max(1.0, float(stable_scale_px))

        for track_id in self._tracks:
            if track_id not in self._active_track_ids:
                continue
            if not remaining:
                break
            track = self._tracks[track_id]
            candidate = min(
                remaining,
                key=lambda row: self._track_distance(
                    track, row, current_frame, phase_context
                ),
            )
            distance = self._track_distance(
                track, candidate, current_frame, phase_context
            )
            if distance > association_limit:
                continue
            remaining.remove(candidate)
            track.observations[current_frame] = self._observation(
                candidate, current_frame, evidence, frame_shape
            )
            self._candidate_track_ids[candidate.candidate_id] = track_id
            self._refresh_cycle_status(
                track, current_frame, phase_context, stable_scale_px
            )

        matched_track_ids = {
            track_id
            for track_id in self._tracks
            if track_id in self._active_track_ids
            and current_frame in self._tracks[track_id].observations
        }
        self._active_track_ids = matched_track_ids

        for candidate in remaining:
            track_id = f"anchor-{self._next_track_number}"
            self._next_track_number += 1
            track = _BackgroundAnchorTrack(
                track_id=track_id,
                observations={
                    current_frame: self._observation(
                        candidate, current_frame, evidence, frame_shape
                    )
                },
            )
            self._tracks[track_id] = track
            self._active_track_ids.add(track_id)
            self._candidate_track_ids[candidate.candidate_id] = track_id
            self._refresh_cycle_status(
                track, current_frame, phase_context, stable_scale_px
            )

        return tuple(
            self._anchor_for_track(track)
            for track_id, track in self._tracks.items()
            if track_id in self._active_track_ids
            and len(track.observations) >= self.minimum_stable_observations
            and (
                not self._has_cycle_gate(phase_context)
                or track.qualified_cycle
            )
        )

    def track_id_for_candidate(self, candidate_id: str) -> str | None:
        return self._candidate_track_ids.get(str(candidate_id))

    def reference_anchor(
        self,
        track_id: str,
        frame_index: int,
    ) -> BackgroundAnchor | None:
        track = self._tracks.get(str(track_id))
        if track is None:
            return None
        observation = track.observations.get(int(frame_index))
        if observation is None:
            return None
        return self._anchor_for_track(track, observation)

    def qualified_reference_anchors(
        self,
        frame_index: int,
    ) -> tuple[BackgroundAnchor, ...]:
        anchors: list[BackgroundAnchor] = []
        for track_id in sorted(self._tracks):
            anchor = self.reference_anchor(track_id, frame_index)
            if anchor is not None and anchor.qualified_cycle and not anchor.clipped:
                anchors.append(anchor)
        return tuple(anchors)

    def _resolve_frame_index(self, frame_index: int | None) -> int:
        if frame_index is None:
            self._implicit_frame_index += 1
            return self._implicit_frame_index
        current_frame = int(frame_index)
        self._implicit_frame_index = max(self._implicit_frame_index, current_frame)
        return current_frame

    def _observation(
        self,
        candidate: Candidate,
        frame_index: int,
        evidence: Mapping[str, CandidateEvidence],
        frame_shape: tuple[int, int] | None,
    ) -> AnchorObservation:
        x1, y1, x2, y2 = candidate.bbox
        width = max(1e-6, float(x2) - float(x1))
        height = max(1e-6, float(y2) - float(y1))
        candidate_evidence = evidence.get(candidate.candidate_id)
        return AnchorObservation(
            frame_index=frame_index,
            candidate_id=candidate.candidate_id,
            point=candidate.center,
            bbox=candidate.bbox,
            area=width * height,
            aspect=width / height,
            clipped=_candidate_is_clipped(candidate, frame_shape),
            merge_like=(
                candidate_evidence is not None
                and candidate_evidence.merge_likelihood > 0.0
            ),
        )

    def _track_distance(
        self,
        track: _BackgroundAnchorTrack,
        candidate: Candidate,
        frame_index: int,
        phase_context: CyclePhaseContext | None,
    ) -> float:
        points = [track.latest_observation.point]
        if self._has_cycle_gate(phase_context):
            assert phase_context is not None
            reference = track.observations.get(
                frame_index - int(phase_context.local_lag)
            )
            if reference is not None:
                points.append(reference.point)
        return min(
            hypot(candidate.center[0] - point[0], candidate.center[1] - point[1])
            for point in points
        )

    def _refresh_cycle_status(
        self,
        track: _BackgroundAnchorTrack,
        frame_index: int,
        phase_context: CyclePhaseContext | None,
        stable_scale_px: float,
    ) -> None:
        track.qualified_cycle = False
        track.cycle_survival = 0.0
        track.loop_residual = None
        track.disqualified_reason = None
        if not self._has_cycle_gate(phase_context):
            self._record_qualification_snapshot(track, frame_index)
            return

        assert phase_context is not None
        self._update_lifetime_disqualification(track)
        if track.lifetime_disqualified_reason is not None:
            track.disqualified_reason = track.lifetime_disqualified_reason
            self._record_qualification_snapshot(track, frame_index)
            return

        cycle_start = frame_index - int(phase_context.period)
        reference_frame = frame_index - int(phase_context.local_lag)
        if cycle_start not in track.observations:
            track.disqualified_reason = "cycle_incomplete"
            self._record_qualification_snapshot(track, frame_index)
            return
        if reference_frame not in track.observations:
            track.disqualified_reason = "cycle_reference"
            self._record_qualification_snapshot(track, frame_index)
            return

        # Skipped frame indexes count as missing expected cycle observations.
        cycle_frames = range(cycle_start, frame_index + 1)
        observed_frames = [
            observed_frame
            for observed_frame in cycle_frames
            if observed_frame in track.observations
        ]
        total_frames = len(cycle_frames)
        track.cycle_survival = len(observed_frames) / max(1, total_frames)
        largest_gap = self._largest_cycle_gap(cycle_frames, track.observations)
        if track.cycle_survival < self.minimum_cycle_survival:
            track.disqualified_reason = "cycle_survival"
            self._record_qualification_snapshot(track, frame_index)
            return
        if largest_gap / max(1, total_frames) > self.maximum_cycle_gap_ratio:
            track.disqualified_reason = "cycle_gap"
            self._record_qualification_snapshot(track, frame_index)
            return

        reference = track.observations[reference_frame]
        current = track.observations[frame_index]
        scale = max(1e-6, float(stable_scale_px))
        track.loop_residual = hypot(
            current.point[0] - reference.point[0],
            current.point[1] - reference.point[1],
        ) / scale
        if (
            phase_context.period_score is not None
            and float(phase_context.period_score) / scale
            > self.loop_position_tolerance
        ):
            track.disqualified_reason = "period_score"
            self._record_qualification_snapshot(track, frame_index)
            return
        if track.loop_residual > self.loop_position_tolerance:
            track.disqualified_reason = "loop_position"
            self._record_qualification_snapshot(track, frame_index)
            return
        if self._shape_residual(reference, current) > self.loop_shape_tolerance:
            track.disqualified_reason = "loop_shape"
            self._record_qualification_snapshot(track, frame_index)
            return
        track.qualified_cycle = True
        self._record_qualification_snapshot(track, frame_index)

    @staticmethod
    def _update_lifetime_disqualification(track: _BackgroundAnchorTrack) -> None:
        if track.lifetime_disqualified_reason is not None:
            return
        if any(observation.clipped for observation in track.observations.values()):
            track.lifetime_disqualified_reason = "cycle_clipped"
        elif any(observation.merge_like for observation in track.observations.values()):
            track.lifetime_disqualified_reason = "cycle_merge_like"

    @staticmethod
    def _record_qualification_snapshot(
        track: _BackgroundAnchorTrack,
        frame_index: int,
    ) -> None:
        track.qualification_by_frame[frame_index] = _AnchorQualificationSnapshot(
            stable_observations=len(track.observations),
            qualified_cycle=track.qualified_cycle,
            cycle_survival=track.cycle_survival,
            loop_residual=track.loop_residual,
            disqualified_reason=track.disqualified_reason,
        )

    @staticmethod
    def _largest_cycle_gap(
        cycle_frames: range,
        observations: Mapping[int, AnchorObservation],
    ) -> int:
        largest_gap = 0
        current_gap = 0
        for frame_index in cycle_frames:
            if frame_index in observations:
                largest_gap = max(largest_gap, current_gap)
                current_gap = 0
            else:
                current_gap += 1
        return max(largest_gap, current_gap)

    @staticmethod
    def _shape_residual(
        reference: AnchorObservation,
        current: AnchorObservation,
    ) -> float:
        area_residual = abs(reference.area - current.area) / max(
            1e-6, reference.area, current.area
        )
        aspect_residual = abs(reference.aspect - current.aspect) / max(
            1e-6, reference.aspect, current.aspect
        )
        return max(area_residual, aspect_residual)

    @staticmethod
    def _has_cycle_gate(phase_context: CyclePhaseContext | None) -> bool:
        return bool(
            phase_context is not None
            and phase_context.period is not None
            and phase_context.local_lag is not None
            and int(phase_context.period) > 0
            and int(phase_context.local_lag) > 0
        )

    @staticmethod
    def _anchor_for_track(
        track: _BackgroundAnchorTrack,
        observation: AnchorObservation | None = None,
    ) -> BackgroundAnchor:
        current = observation or track.latest_observation
        snapshot = track.qualification_by_frame.get(current.frame_index)
        lifetime_disqualified_reason = track.lifetime_disqualified_reason
        return BackgroundAnchor(
            track_id=track.track_id,
            point=current.point,
            stable_observations=(
                snapshot.stable_observations
                if snapshot is not None
                else len(track.observations)
            ),
            clipped=current.clipped,
            candidate_id=current.candidate_id,
            qualified_cycle=(
                False
                if lifetime_disqualified_reason is not None
                else (
                    snapshot.qualified_cycle
                    if snapshot is not None
                    else track.qualified_cycle
                )
            ),
            cycle_survival=(
                snapshot.cycle_survival
                if snapshot is not None
                else track.cycle_survival
            ),
            loop_residual=(
                snapshot.loop_residual
                if snapshot is not None
                else track.loop_residual
            ),
            disqualified_reason=(
                lifetime_disqualified_reason
                if lifetime_disqualified_reason is not None
                else (
                    snapshot.disqualified_reason
                    if snapshot is not None
                    else track.disqualified_reason
                )
            ),
        )


@dataclass(frozen=True)
class RelationFingerprint:
    pair_coordinates: tuple[tuple[str, str, RelativeCoordinate], ...]
    jitter: float
    triplet_coordinates: tuple[
        tuple[str, str, str, AffineCoordinate], ...
    ] = ()

    @classmethod
    def from_observations(
        cls,
        *,
        background_point: Point,
        anchors: Sequence[BackgroundAnchor],
        jitter: float,
    ) -> "RelationFingerprint":
        rows: list[tuple[str, str, RelativeCoordinate]] = []
        triplets: list[tuple[str, str, str, AffineCoordinate]] = []
        for left_index, left in enumerate(anchors):
            for right in anchors[left_index + 1 :]:
                coordinate = relative_coordinate(background_point, left.point, right.point)
                if coordinate is not None and not left.clipped and not right.clipped:
                    rows.append((left.track_id, right.track_id, coordinate))
        for left, middle, right in combinations(anchors, 3):
            coordinate = affine_coordinate(
                background_point,
                left.point,
                middle.point,
                right.point,
            )
            if (
                coordinate is not None
                and not left.clipped
                and not middle.clipped
                and not right.clipped
            ):
                triplets.append(
                    (left.track_id, middle.track_id, right.track_id, coordinate)
                )
        return cls(
            pair_coordinates=tuple(rows),
            jitter=max(1e-6, float(jitter)),
            triplet_coordinates=tuple(triplets),
        )


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
    incumbent_candidate_id: str | None = None,
    phase_conditioned: bool = False,
) -> MergeSplitDecision:
    if not phase_conditioned:
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
                        relative_coordinate_residual(
                            current,
                            expected,
                            fingerprint.jitter,
                        )
                    )
            if residuals:
                child_residuals.append((float(median(residuals)), child))

        debug = {
            "child_residuals": tuple(
                (candidate.candidate_id, residual)
                for residual, candidate in sorted(
                    child_residuals,
                    key=lambda row: row[0],
                )
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
        incumbent = next(
            (
                candidate
                for candidate in remaining
                if candidate.candidate_id == incumbent_candidate_id
            ),
            None,
        )
        target = incumbent or min(
            remaining,
            key=lambda candidate: hypot(
                candidate.center[0] - predicted_target_point[0],
                candidate.center[1] - predicted_target_point[1],
            ),
        )
        debug["target_selection_basis"] = (
            "incumbent_identity" if incumbent is not None else "motion_prediction"
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

    usable = {
        anchor.track_id: anchor
        for anchor in anchors
        if not anchor.clipped and anchor.qualified_cycle
    }
    valid_pairs = tuple(
        (left_id, right_id, expected)
        for left_id, right_id, expected in fingerprint.pair_coordinates
        if left_id in usable and right_id in usable
    )
    valid_triplets = tuple(
        (left_id, middle_id, right_id, expected)
        for left_id, middle_id, right_id, expected in fingerprint.triplet_coordinates
        if left_id in usable and middle_id in usable and right_id in usable
    )
    reference_affine_triplets = fingerprint.triplet_coordinates
    reference_pairs = fingerprint.pair_coordinates
    relation_basis = "affine_triplet" if reference_affine_triplets else "pair"
    debug = {
        "qualified_anchor_count": len(usable),
        "valid_anchor_pair_count": len(valid_pairs),
        "valid_affine_triplet_count": len(valid_triplets),
        "reference_affine_triplet_count": len(reference_affine_triplets),
        "reference_anchor_pair_count": len(reference_pairs),
        "relation_basis": relation_basis,
        "usable_anchor_ids": tuple(usable),
    }
    if not reference_affine_triplets and not reference_pairs:
        return _hold_decision("insufficient_cycle_anchors", debug=debug)

    child_residuals: list[tuple[float, Candidate]] = []
    basis_rows: list[tuple[str, str, tuple[str, ...], object]] = []
    if reference_affine_triplets:
        basis_rows = [
            (
                f"affine_triplet:{left_id},{middle_id},{right_id}",
                "affine_triplet",
                (left_id, middle_id, right_id),
                expected,
            )
            for left_id, middle_id, right_id, expected in reference_affine_triplets
        ]
    else:
        basis_rows = [
            (f"pair:{left_id},{right_id}", "pair", (left_id, right_id), expected)
            for left_id, right_id, expected in reference_pairs
        ]
    residuals_by_child: dict[str, dict[str, float]] = {}
    for child in children:
        residuals: dict[str, float] = {}
        for basis_id, basis, track_ids, expected in basis_rows:
            if basis == "affine_triplet":
                left_id, middle_id, right_id = track_ids
                current = (
                    affine_coordinate(
                        child.center,
                        usable[left_id].point,
                        usable[middle_id].point,
                        usable[right_id].point,
                    )
                    if (
                        left_id in usable
                        and middle_id in usable
                        and right_id in usable
                    )
                    else None
                )
                if current is not None:
                    residuals[basis_id] = affine_coordinate_residual(
                            current,
                            expected,
                            fingerprint.jitter,
                    )
            else:
                left_id, right_id = track_ids
                current = (
                    relative_coordinate(
                        child.center,
                        usable[left_id].point,
                        usable[right_id].point,
                    )
                    if left_id in usable and right_id in usable
                    else None
                )
                if current is not None:
                    residuals[basis_id] = relative_coordinate_residual(
                            current,
                            expected,
                            fingerprint.jitter,
                    )
        if residuals:
            child_residuals.append((float(median(residuals.values())), child))
            residuals_by_child[child.candidate_id] = residuals

    missing_basis_ids = tuple(
        basis_id
        for basis_id, _basis, _track_ids, _expected in basis_rows
        if any(
            basis_id not in residuals_by_child.get(child.candidate_id, {})
            for child in children
        )
    )
    required_anchor_ids = {
        track_id
        for _basis_id, _basis, track_ids, _expected in basis_rows
        for track_id in track_ids
    }
    debug["child_residuals"] = tuple(
        (candidate.candidate_id, residual)
        for residual, candidate in sorted(child_residuals, key=lambda row: row[0])
    )
    debug["missing_basis_ids"] = missing_basis_ids
    debug["missing_basis_count"] = len(missing_basis_ids)
    debug["missing_current_anchor_ids"] = tuple(
        sorted(required_anchor_ids.difference(usable))
    )
    if missing_basis_ids:
        return _hold_decision("ambiguous_phase_relation", debug=debug)
    if len(child_residuals) < 2:
        return _hold_decision("insufficient_cycle_anchors", debug=debug)

    anchor_votes: list[dict[str, object]] = []
    ambiguous_basis_ids: list[str] = []
    for basis_id, basis, track_ids, _expected in basis_rows:
        contenders = sorted(
            (
                (residuals_by_child[candidate.candidate_id][basis_id], candidate)
                for _residual, candidate in child_residuals
                if candidate.candidate_id in residuals_by_child
                and basis_id in residuals_by_child[candidate.candidate_id]
            ),
            key=lambda row: row[0],
        )
        if len(contenders) < 2:
            continue
        winner_residual, winner = contenders[0]
        runner_residual, runner = contenders[1]
        ambiguous = runner_residual - winner_residual <= 1.0
        if ambiguous:
            ambiguous_basis_ids.append(basis_id)
        anchor_votes.append(
            {
                "basis_id": basis_id,
                "basis": basis,
                "anchor_track_ids": track_ids,
                "supported_candidate_id": (
                    None if ambiguous else winner.candidate_id
                ),
                "supported_residual": winner_residual,
                "runner_candidate_id": runner.candidate_id,
                "runner_residual": runner_residual,
                "residual_margin": runner_residual - winner_residual,
                "ambiguous": ambiguous,
            }
        )
    supported_ids = {
        vote["supported_candidate_id"]
        for vote in anchor_votes
        if vote["supported_candidate_id"] is not None
    }
    debug["anchor_votes"] = tuple(anchor_votes)
    debug["ambiguous_basis_ids"] = tuple(ambiguous_basis_ids)
    debug["relation_vote_quorum"] = {
        "support_count": len(supported_ids),
        "basis_count": len(anchor_votes),
        "ambiguous_basis_count": len(ambiguous_basis_ids),
        "conflicting": len(supported_ids) > 1,
    }
    if ambiguous_basis_ids or len(supported_ids) > 1:
        return _hold_decision("ambiguous_phase_relation", debug=debug)

    child_residuals.sort(key=lambda row: row[0])
    background_residual, background = child_residuals[0]
    relative_margin = child_residuals[1][0] - background_residual
    if relative_margin <= 1.0:
        return _hold_decision(
            "ambiguous_phase_relation",
            relative_margin=relative_margin,
            debug=debug,
        )

    remaining = [row[1] for row in child_residuals[1:]]
    incumbent = next(
        (
            candidate
            for candidate in remaining
            if candidate.candidate_id == incumbent_candidate_id
        ),
        None,
    )
    target = incumbent or min(
        remaining,
        key=lambda candidate: hypot(
            candidate.center[0] - predicted_target_point[0],
            candidate.center[1] - predicted_target_point[1],
        ),
    )
    debug["target_selection_basis"] = (
        "incumbent_identity" if incumbent is not None else "motion_prediction"
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


@dataclass
class MergeEventContext:
    event_id: int
    target_candidate_id: str
    background_track_id: str
    anchor_track_ids: tuple[str, ...]
    premerge_target_point: Point
    premerge_target_bbox: tuple[float, float, float, float]
    premerge_background_bbox: tuple[float, float, float, float]
    merge_bbox: tuple[float, float, float, float] | None
    opened_frame: int
    last_frame: int
    phase_anchor_track_ids: tuple[str, ...] = ()
    phase_anchor_selection_count: int = 0
    phase_anchor_best_triangle_quality: float | None = None


@dataclass(frozen=True)
class _VisiblePair:
    target: Candidate
    background: Candidate
    event_id: int
    background_track_id: str | None = None


@dataclass(frozen=True)
class SplitChildPair:
    children: tuple[Candidate, Candidate]
    union_residual: float
    ancestry_residual: float
    score_margin: float


def _duplicate_equivalence_representatives(
    candidates: Sequence[Candidate],
) -> tuple[Candidate, ...]:
    def representative_key(candidate: Candidate) -> tuple[float, object, str]:
        return (-float(candidate.score), candidate.bbox, candidate.candidate_id)

    clusters: list[list[Candidate]] = []
    for candidate in sorted(candidates, key=representative_key):
        matching_indices = [
            index
            for index, cluster in enumerate(clusters)
            if any(
                _is_duplicate_observation(candidate, member)
                or _is_duplicate_observation(member, candidate)
                for member in cluster
            )
        ]
        if not matching_indices:
            clusters.append([candidate])
            continue

        primary_index = matching_indices[0]
        clusters[primary_index].append(candidate)
        for index in reversed(matching_indices[1:]):
            clusters[primary_index].extend(clusters.pop(index))

    return tuple(
        min(cluster, key=representative_key)
        for cluster in clusters
    )


def select_split_child_pair(
    *,
    context: MergeEventContext,
    candidates: Sequence[Candidate],
    predicted_target_point: Point,
    stable_scale_px: float,
) -> SplitChildPair | None:
    candidates = _duplicate_equivalence_representatives(candidates)
    if len(candidates) < 2:
        return None

    scale = max(1e-6, float(stable_scale_px))
    merge_bbox = context.merge_bbox or _bbox_union(
        context.premerge_target_bbox,
        context.premerge_background_bbox,
    )
    premerge_sizes = (
        _bbox_size(context.premerge_target_bbox),
        _bbox_size(context.premerge_background_bbox),
    )
    scored_pairs: list[tuple[float, float, float, tuple[Candidate, Candidate]]] = []
    for left, right in combinations(candidates, 2):
        child_union = _bbox_union(left.bbox, right.bbox)
        union_residual = _bbox_edge_residual(child_union, merge_bbox, scale)
        ancestry_residual = min(
            _bbox_size_residual(left.bbox, premerge_sizes[0], scale)
            + _bbox_size_residual(right.bbox, premerge_sizes[1], scale),
            _bbox_size_residual(left.bbox, premerge_sizes[1], scale)
            + _bbox_size_residual(right.bbox, premerge_sizes[0], scale),
        )
        merge_region_residual = (
            _point_to_bbox_distance(left.center, merge_bbox)
            + _point_to_bbox_distance(right.center, merge_bbox)
        ) / (2.0 * scale)
        predicted_target_residual = min(
            hypot(
                left.center[0] - predicted_target_point[0],
                left.center[1] - predicted_target_point[1],
            ),
            hypot(
                right.center[0] - predicted_target_point[0],
                right.center[1] - predicted_target_point[1],
            ),
        ) / scale
        cost = (
            union_residual
            + 0.75 * ancestry_residual
            + 0.50 * merge_region_residual
            + 0.25 * predicted_target_residual
        )
        scored_pairs.append((cost, union_residual, ancestry_residual, (left, right)))

    if not scored_pairs:
        return None
    scored_pairs.sort(key=lambda row: row[0])
    best_cost, union_residual, ancestry_residual, children = scored_pairs[0]
    runner_up_cost = scored_pairs[1][0] if len(scored_pairs) > 1 else None
    score_margin = (
        runner_up_cost - best_cost if runner_up_cost is not None else float("inf")
    )
    if best_cost > 1.5 or score_margin <= 0.15:
        return None
    return SplitChildPair(
        children=children,
        union_residual=union_residual,
        ancestry_residual=ancestry_residual,
        score_margin=score_margin,
    )


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

    def complete_split_recovery(self) -> None:
        self._pending_state = None
        self._pending_count = 0
        self._set_state(MergeState.SEPARATE, increment_event=False)

    @property
    def pending_merge_state(self) -> MergeState | None:
        if (
            self._pending_state in (MergeState.PARTIAL_OVERLAP, MergeState.MERGED)
            and self._pending_count < self.confirm_observations
        ):
            return self._pending_state
        return None

    def open_confirmed_merge_event(self) -> int:
        if self.state not in (MergeState.PARTIAL_OVERLAP, MergeState.MERGED):
            raise ValueError("confirmed merge event requires a merge state")
        self.event_id += 1
        return self.event_id

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
            self._pending_state = None
            self._pending_count = 0
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
        if (
            increment_event
            and self.state in (MergeState.SEPARATE, MergeState.REACQUIRED)
            and state in (MergeState.PARTIAL_OVERLAP, MergeState.MERGED)
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
        self._fingerprint_mode: str | None = None
        self._phase_reference_frame: int | None = None
        self._phase_fingerprint_frame: int | None = None
        self._fingerprint_event_id: int | None = None
        self._merge_context: MergeEventContext | None = None
        self._last_visible_pair: _VisiblePair | None = None
        self._merge_center: Point | None = None
        self._merge_bbox: tuple[float, float, float, float] | None = None
        self._split_recovery_remaining = 0
        self._split_recovery_success_count = 0
        self._split_first_unresolved_held = False
        self._split_recovery_unresolved = False

    def update(
        self,
        *,
        incumbent_point: Point | None,
        candidates: Sequence[Candidate],
        evidence: Mapping[str, CandidateEvidence],
        stable_area: float,
        frame_shape: tuple[int, int] | None,
        frame_index: int | None = None,
        phase_context: CyclePhaseContext | None = None,
    ) -> MergeSplitDecision:
        candidate_tuple = tuple(candidates)
        predicted = self._predicted_target_point(incumbent_point, candidate_tuple)
        nearest = _nearest_candidate(candidate_tuple, incumbent_point)
        target_candidate = None
        if nearest is not None:
            area_ratio = _bbox_area(nearest.bbox) / max(1.0, stable_area)
            if area_ratio <= 1.25:
                target_candidate = nearest

        collision_candidate = _nearest_other_candidate(candidate_tuple, target_candidate)
        event_candidates = candidate_tuple
        if target_candidate is not None:
            event_candidates = (
                (target_candidate, collision_candidate)
                if collision_candidate is not None
                else (target_candidate,)
            )

        previous_detector_state = self._event_detector.state
        previous_event_id = self._event_detector.event_id
        event = self._event_detector.update(
            target_candidate=target_candidate,
            candidates=event_candidates,
            stable_area=stable_area,
            predicted_target_point=predicted,
        )
        scale = max(1.0, stable_area**0.5)
        if (
            event.state is MergeState.SPLITTING
            and self._split_recovery_remaining <= 0
        ):
            self._split_recovery_remaining = 3
            self._split_recovery_success_count = 0
            self._split_first_unresolved_held = False
            self._split_recovery_unresolved = True
        recovering_split = self._split_recovery_remaining > 0

        if (
            recovering_split
            and self._split_recovery_unresolved
            and event.state in (MergeState.PARTIAL_OVERLAP, MergeState.MERGED)
            and event.event_id != previous_event_id
        ):
            self._clear_split_recovery()
            self._clear_merge_event_context(
                clear_visible_pair=True,
                clear_relation_fingerprint=(
                    phase_context is not None and self._fingerprint_mode == "phase"
                ),
            )
            recovering_split = False

        if (
            recovering_split
            and self._event_detector.pending_merge_state is not None
        ):
            self._split_recovery_success_count = 0
            if self._split_recovery_unresolved:
                return self._unresolved_split_hold(
                    event,
                    "merge_confirmation_pending",
                )
            return self._bounded_split_recovery_hold(
                event,
                "merge_confirmation_pending",
            )

        # A resolved split still needs a short stability quorum, but a new
        # confirmed merge starts its own event instead of consuming that budget.
        if (
            recovering_split
            and not self._split_recovery_unresolved
            and event.state in (MergeState.PARTIAL_OVERLAP, MergeState.MERGED)
        ):
            if (
                previous_detector_state is MergeState.SPLITTING
                and event.event_id == previous_event_id
            ):
                event = MergeEvent(
                    event_id=self._event_detector.open_confirmed_merge_event(),
                    state=event.state,
                    reason=event.reason,
                    overlap_ratio=event.overlap_ratio,
                    area_ratio=event.area_ratio,
                    candidate_count=event.candidate_count,
                )
            self._clear_split_recovery()
            self._clear_merge_event_context(
                clear_relation_fingerprint=(
                    phase_context is not None and self._fingerprint_mode == "phase"
                ),
            )
            recovering_split = False

        if (
            event.state is MergeState.SEPARATE
            and not recovering_split
            and self._event_detector.pending_merge_state is not None
        ):
            return self._event_hold(event, "merge_confirmation_pending")

        if event.state is MergeState.SEPARATE and not recovering_split:
            collision = collision_candidate
            anchor_candidates = tuple(
                candidate
                for candidate in candidate_tuple
                if (target_candidate is None or candidate is not target_candidate)
                and (
                    phase_context is not None
                    or collision is None
                    or candidate is not collision
                )
            )
            self._current_anchors = self._anchor_manager.update(
                candidates=anchor_candidates,
                target_candidate=None,
                evidence=evidence,
                frame_shape=frame_shape,
                stable_scale_px=scale,
                frame_index=frame_index,
                phase_context=phase_context,
            )
            self._remember_target(target_candidate)
            if phase_context is None:
                self._remember_background_relation(collision, evidence, scale)
            if (
                target_candidate is None
                or collision is None
                or not _is_local_visible_pair(
                    target_candidate,
                    collision,
                    stable_scale_px=scale,
                )
            ):
                self._last_visible_pair = None
            else:
                self._remember_visible_pair(
                    target_candidate,
                    collision,
                    event_id=event.event_id,
                    background_track_id=(
                        self._anchor_manager.track_id_for_candidate(
                            collision.candidate_id
                        )
                        if phase_context is not None and collision is not None
                        else None
                    ),
                )
            if phase_context is not None:
                self._clear_merge_event_context(
                    clear_relation_fingerprint=self._fingerprint_mode == "phase",
                )
            else:
                self._merge_context = None
                self._merge_center = None
                self._merge_bbox = None
            return self._event_hold(event, "separate")

        overlapping = (
            _most_overlapping_candidate(target_candidate, candidate_tuple)
            if event.state is MergeState.PARTIAL_OVERLAP
            else None
        )
        merged = (
            _expanded_candidate_near(candidate_tuple, predicted, stable_area)
            if event.state is MergeState.MERGED
            else None
        )
        excluded_anchor_ids = tuple(
            candidate.candidate_id
            for candidate in (
                (merged,)
                if phase_context is not None
                else (overlapping, merged)
            )
            if candidate is not None
        )
        self._current_anchors = self._anchor_manager.update(
            candidates=candidate_tuple,
            target_candidate=target_candidate,
            evidence=evidence,
            frame_shape=frame_shape,
            stable_scale_px=scale,
            excluded_candidate_ids=excluded_anchor_ids,
            frame_index=frame_index,
            phase_context=phase_context,
        )

        if event.state is MergeState.PARTIAL_OVERLAP:
            if recovering_split and self._split_recovery_unresolved:
                return self._unresolved_split_hold(event, "partial_overlap")
            if target_candidate is not None and overlapping is not None:
                self._merge_center = (
                    (target_candidate.center[0] + overlapping.center[0]) / 2.0,
                    (target_candidate.center[1] + overlapping.center[1]) / 2.0,
                )
                self._merge_bbox = _bbox_union(
                    target_candidate.bbox,
                    overlapping.bbox,
                )
                self._refresh_merge_context(
                    event=event,
                    target_candidate=target_candidate,
                    background_candidate=overlapping,
                    frame_index=frame_index,
                    phase_context=phase_context,
                )
                self._remember_target(target_candidate)
                if phase_context is None:
                    self._remember_background_relation(overlapping, evidence, scale)
            return self._event_hold(event, "partial_overlap")

        if event.state is MergeState.MERGED:
            if recovering_split and self._split_recovery_unresolved:
                return self._unresolved_split_hold(event, "merged_identity_hold")
            if merged is not None:
                self._merge_center = merged.center
                self._merge_bbox = merged.bbox
                self._ensure_merge_context_for_merged_event(
                    event,
                    merged,
                    frame_index=frame_index,
                    phase_context=phase_context,
                )
            self._advance_latent_target(incumbent_point)
            return self._event_hold(event, "merged_identity_hold")

        if recovering_split:
            if phase_context is not None:
                phase_refresh_reason: str | None = None
                if frame_index is not None and self._merge_context is not None:
                    phase_refresh_reason = self._remember_phase_background_relation(
                        context=self._merge_context,
                        frame_index=frame_index,
                        phase_context=phase_context,
                    )
                if phase_refresh_reason is not None:
                    return self._unresolved_split_hold(
                        event,
                        phase_refresh_reason,
                    )
                if (
                    self._fingerprint_mode != "phase"
                    or self._phase_fingerprint_frame != frame_index
                    or self._merge_context is None
                    or self._fingerprint_event_id
                    != self._merge_context.event_id
                ):
                    return self._unresolved_split_hold(
                        event,
                        "insufficient_cycle_anchors",
                    )
            elif self._fingerprint_mode != "legacy":
                return self._unresolved_split_hold(event, "missing_fingerprint")
            child_center = self._merge_center or predicted
            local_children = tuple(
                candidate
                for candidate in candidate_tuple
                if (
                    _point_to_bbox_distance(candidate.center, self._merge_bbox)
                    <= 0.75 * scale
                    if self._merge_bbox is not None
                    else hypot(
                        candidate.center[0] - child_center[0],
                        candidate.center[1] - child_center[1],
                    )
                    <= 1.5 * scale
                )
            )
            predicted_target_point = self._predicted_target_point(
                incumbent_point,
                candidate_tuple,
            )
            split_pair = (
                select_split_child_pair(
                    context=self._merge_context,
                    candidates=local_children,
                    predicted_target_point=predicted_target_point,
                    stable_scale_px=scale,
                )
                if self._merge_context is not None
                else None
            )
            if split_pair is None:
                return self._unresolved_split_hold(
                    event,
                    (
                        "missing_split_pair"
                        if phase_context is not None
                        else "split_pair_ambiguous"
                    ),
                )
            decision = assign_split_children(
                children=split_pair.children,
                anchors=self._current_anchors,
                fingerprint=self._fingerprint,
                predicted_target_point=predicted_target_point,
                incumbent_candidate_id=(
                    target_candidate.candidate_id
                    if target_candidate is not None
                    else None
                ),
                phase_conditioned=phase_context is not None,
            )
            if (
                decision.target_candidate_id is None
                or decision.background_candidate_id is None
            ):
                return self._unresolved_split_hold(event, decision.reason)
            self._split_recovery_unresolved = False
            self._split_recovery_success_count += 1
            self._remember_visible_pair(
                next(
                    (
                        candidate
                        for candidate in split_pair.children
                        if candidate.candidate_id == decision.target_candidate_id
                    ),
                    None,
                ),
                next(
                    (
                        candidate
                        for candidate in split_pair.children
                        if candidate.candidate_id == decision.background_candidate_id
                    ),
                    None,
                ),
                event_id=event.event_id,
                background_track_id=(
                    self._anchor_manager.track_id_for_candidate(
                        decision.background_candidate_id
                    )
                    if phase_context is not None
                    else None
                ),
            )
            recovered = MergeSplitDecision(
                state=event.state,
                background_candidate_id=decision.background_candidate_id,
                target_candidate_id=decision.target_candidate_id,
                target_point=decision.target_point,
                relative_margin=decision.relative_margin,
                reason=decision.reason,
                debug={
                    **decision.debug,
                    "event_id": event.event_id,
                    "anchor_count": len(self._current_anchors),
                    "fingerprint_pair_count": len(self._fingerprint.pair_coordinates),
                    "fingerprint_mode": self._fingerprint_mode,
                    "phase_reference_frame": self._phase_reference_frame,
                    "phase_fingerprint_frame": self._phase_fingerprint_frame,
                    "phase_selected_anchor_count": (
                        self._merge_context.phase_anchor_selection_count
                        if self._merge_context is not None
                        else 0
                    ),
                    "phase_best_triangle_quality": (
                        self._merge_context.phase_anchor_best_triangle_quality
                        if self._merge_context is not None
                        else None
                    ),
                    "merge_bbox": self._merge_bbox,
                    "predicted_target_point": predicted_target_point,
                    "local_child_ids": tuple(
                        candidate.candidate_id for candidate in local_children
                    ),
                    "split_child_pair_ids": tuple(
                        candidate.candidate_id for candidate in split_pair.children
                    ),
                    "split_pair_union_residual": split_pair.union_residual,
                    "split_pair_ancestry_residual": split_pair.ancestry_residual,
                    "split_pair_score_margin": split_pair.score_margin,
                },
            )
            if self._split_recovery_success_count >= 3:
                self._event_detector.complete_split_recovery()
                self._clear_split_recovery()
                if self._fingerprint_mode == "phase":
                    self._clear_merge_event_context()
            return recovered

        return self._event_hold(event, "missing_fingerprint")

    def _clear_split_recovery(self) -> None:
        self._split_recovery_remaining = 0
        self._split_recovery_success_count = 0
        self._split_first_unresolved_held = False
        self._split_recovery_unresolved = False

    def _clear_relation_fingerprint(self) -> None:
        self._fingerprint = None
        self._fingerprint_mode = None
        self._phase_reference_frame = None
        self._phase_fingerprint_frame = None
        self._fingerprint_event_id = None

    def _clear_merge_event_context(
        self,
        *,
        clear_visible_pair: bool = False,
        clear_relation_fingerprint: bool = True,
    ) -> None:
        self._merge_context = None
        if clear_visible_pair:
            self._last_visible_pair = None
        if clear_relation_fingerprint:
            self._clear_relation_fingerprint()
        self._merge_center = None
        self._merge_bbox = None

    def _phase_reference_catalog_track_ids(
        self,
        *,
        background_track_id: str,
        frame_index: int | None,
        phase_context: CyclePhaseContext | None,
    ) -> tuple[str, ...]:
        if (
            frame_index is None
            or phase_context is None
            or phase_context.local_lag is None
            or int(phase_context.local_lag) <= 0
        ):
            return ()
        reference_frame = int(frame_index) - int(phase_context.local_lag)
        return tuple(
            anchor.track_id
            for anchor in self._anchor_manager.qualified_reference_anchors(
                reference_frame
            )
            if anchor.track_id != background_track_id
        )

    def _remember_target(self, candidate: Candidate | None) -> None:
        if candidate is None:
            return
        self._target_points.append(candidate.center)
        self._target_points = self._target_points[-8:]

    def _refresh_merge_context(
        self,
        *,
        event: MergeEvent,
        target_candidate: Candidate,
        background_candidate: Candidate,
        frame_index: int | None,
        phase_context: CyclePhaseContext | None,
    ) -> None:
        if self._merge_context is None or self._merge_context.event_id != event.event_id:
            background_track_id = background_candidate.candidate_id
            if phase_context is not None:
                background_track_id = (
                    self._anchor_manager.track_id_for_candidate(
                        background_candidate.candidate_id
                    )
                    or background_track_id
                )
            self._merge_context = MergeEventContext(
                event_id=event.event_id,
                target_candidate_id=target_candidate.candidate_id,
                background_track_id=background_track_id,
                anchor_track_ids=(
                    self._phase_reference_catalog_track_ids(
                        background_track_id=background_track_id,
                        frame_index=frame_index,
                        phase_context=phase_context,
                    )
                    if phase_context is not None
                    else tuple(
                        anchor.track_id
                        for anchor in self._current_anchors
                        if anchor.track_id != background_track_id
                    )
                ),
                premerge_target_point=target_candidate.center,
                premerge_target_bbox=target_candidate.bbox,
                premerge_background_bbox=background_candidate.bbox,
                merge_bbox=self._merge_bbox,
                opened_frame=target_candidate.frame_index,
                last_frame=target_candidate.frame_index,
            )
        else:
            self._merge_context.merge_bbox = self._merge_bbox
            self._merge_context.last_frame = target_candidate.frame_index

        if phase_context is not None and frame_index is not None:
            self._remember_phase_background_relation(
                context=self._merge_context,
                frame_index=frame_index,
                phase_context=phase_context,
            )

    def _ensure_merge_context_for_merged_event(
        self,
        event: MergeEvent,
        merged_candidate: Candidate,
        *,
        frame_index: int | None,
        phase_context: CyclePhaseContext | None,
    ) -> None:
        if self._merge_context is not None and self._merge_context.event_id == event.event_id:
            self._merge_context.merge_bbox = merged_candidate.bbox
            self._merge_context.last_frame = merged_candidate.frame_index
            if phase_context is not None and frame_index is not None:
                self._remember_phase_background_relation(
                    context=self._merge_context,
                    frame_index=frame_index,
                    phase_context=phase_context,
                )
            return
        visible_pair = self._last_visible_pair
        if visible_pair is None or visible_pair.event_id != event.event_id - 1:
            self._clear_merge_event_context(
                clear_relation_fingerprint=self._fingerprint_mode == "phase",
            )
            return
        background_track_id = (
            visible_pair.background_track_id
            if phase_context is not None
            else None
        ) or visible_pair.background.candidate_id
        self._merge_context = MergeEventContext(
            event_id=event.event_id,
            target_candidate_id=visible_pair.target.candidate_id,
            background_track_id=background_track_id,
            anchor_track_ids=(
                self._phase_reference_catalog_track_ids(
                    background_track_id=background_track_id,
                    frame_index=frame_index,
                    phase_context=phase_context,
                )
                if phase_context is not None
                else tuple(
                    anchor.track_id
                    for anchor in self._current_anchors
                    if anchor.track_id != background_track_id
                )
            ),
            premerge_target_point=visible_pair.target.center,
            premerge_target_bbox=visible_pair.target.bbox,
            premerge_background_bbox=visible_pair.background.bbox,
            merge_bbox=merged_candidate.bbox,
            opened_frame=visible_pair.target.frame_index,
            last_frame=merged_candidate.frame_index,
        )
        if phase_context is not None and frame_index is not None:
            self._remember_phase_background_relation(
                context=self._merge_context,
                frame_index=frame_index,
                phase_context=phase_context,
            )

    def _remember_visible_pair(
        self,
        target_candidate: Candidate | None,
        background_candidate: Candidate | None,
        *,
        event_id: int,
        background_track_id: str | None = None,
    ) -> None:
        if target_candidate is None or background_candidate is None:
            return
        self._last_visible_pair = _VisiblePair(
            target=target_candidate,
            background=background_candidate,
            event_id=event_id,
            background_track_id=background_track_id,
        )

    def _unresolved_split_hold(
        self,
        event: MergeEvent,
        reason: str,
    ) -> MergeSplitDecision:
        self._split_recovery_unresolved = True
        self._split_recovery_success_count = 0
        if (
            event.state is MergeState.SPLITTING
            and not self._split_first_unresolved_held
        ):
            self._split_first_unresolved_held = True
            return self._event_hold(event, reason)

        self._split_first_unresolved_held = True
        self._split_recovery_remaining = max(
            0,
            self._split_recovery_remaining - 1,
        )
        if self._split_recovery_remaining > 0:
            return self._event_hold(event, reason)

        return self._expire_split_recovery(event)

    def _bounded_split_recovery_hold(
        self,
        event: MergeEvent,
        reason: str,
    ) -> MergeSplitDecision:
        self._split_recovery_success_count = 0
        self._split_recovery_remaining = max(
            0,
            self._split_recovery_remaining - 1,
        )
        if self._split_recovery_remaining > 0:
            return self._event_hold(event, reason)

        return self._expire_split_recovery(event)

    def _expire_split_recovery(self, event: MergeEvent) -> MergeSplitDecision:
        self._event_detector.complete_split_recovery()
        self._clear_split_recovery()
        self._clear_merge_event_context(
            clear_visible_pair=True,
            clear_relation_fingerprint=self._fingerprint_mode == "phase",
        )
        expired_event = MergeEvent(
            event_id=event.event_id,
            state=MergeState.SEPARATE,
            reason="split_recovery_expired",
            overlap_ratio=event.overlap_ratio,
            area_ratio=event.area_ratio,
            candidate_count=event.candidate_count,
        )
        return self._event_hold(expired_event, "split_recovery_expired")

    def _remember_background_relation(
        self,
        candidate: Candidate | None,
        evidence: Mapping[str, CandidateEvidence],
        scale: float,
    ) -> None:
        if candidate is None or len(self._current_anchors) < 2:
            return
        candidate_evidence = evidence.get(candidate.candidate_id)
        normalized_jitter = 0.0
        if candidate_evidence is not None:
            normalized_jitter = candidate_evidence.local_rigid_residual / scale
        nearby_anchors = nearest_background_anchors(
            background_point=candidate.center,
            anchors=self._current_anchors,
            limit=3,
        )
        fingerprint = RelationFingerprint.from_observations(
            background_point=candidate.center,
            anchors=nearby_anchors,
            jitter=max(0.02, normalized_jitter),
        )
        if not fingerprint.pair_coordinates:
            return
        self._fingerprint = fingerprint
        self._fingerprint_mode = "legacy"
        self._phase_reference_frame = None
        self._phase_fingerprint_frame = None
        self._fingerprint_event_id = None

    def _remember_phase_background_relation(
        self,
        *,
        context: MergeEventContext,
        frame_index: int,
        phase_context: CyclePhaseContext,
    ) -> str | None:
        if phase_context.local_lag is None or int(phase_context.local_lag) <= 0:
            return "insufficient_cycle_anchors"
        reference_frame = int(frame_index) - int(phase_context.local_lag)
        reference_background = self._anchor_manager.reference_anchor(
            context.background_track_id,
            reference_frame,
        )
        if reference_background is None:
            return "insufficient_cycle_anchors"
        if not reference_background.qualified_cycle or reference_background.clipped:
            return "insufficient_cycle_anchors"
        if context.phase_anchor_track_ids:
            reference_track_ids = context.phase_anchor_track_ids
        else:
            eligible_reference_anchors = tuple(
                reference
                for track_id in context.anchor_track_ids
                for reference in (
                    self._anchor_manager.reference_anchor(track_id, reference_frame),
                )
                if reference is not None
                and reference.qualified_cycle
                and not reference.clipped
            )
            if len(eligible_reference_anchors) < 2:
                return "insufficient_cycle_anchors"
            selected_reference_anchors, best_triangle_quality = (
                _select_bounded_phase_reference_anchors(
                    background_point=reference_background.point,
                    anchors=eligible_reference_anchors,
                    limit=_MAX_PHASE_FINGERPRINT_ANCHORS,
                )
            )
            context.phase_anchor_track_ids = tuple(
                anchor.track_id for anchor in selected_reference_anchors
            )
            context.phase_anchor_selection_count = len(selected_reference_anchors)
            context.phase_anchor_best_triangle_quality = best_triangle_quality
            reference_track_ids = context.phase_anchor_track_ids

        reference_anchors: list[BackgroundAnchor] = []
        for track_id in reference_track_ids:
            reference = self._anchor_manager.reference_anchor(track_id, reference_frame)
            if (
                reference is None
                or not reference.qualified_cycle
                or reference.clipped
            ):
                return "insufficient_cycle_anchors"
            reference_anchors.append(reference)
        if len(reference_anchors) < 2:
            return "insufficient_cycle_anchors"
        fingerprint = RelationFingerprint.from_observations(
            background_point=reference_background.point,
            anchors=reference_anchors,
            jitter=0.02,
        )
        if not fingerprint.pair_coordinates:
            return "ambiguous_phase_relation"
        if (
            self._fingerprint_mode == "phase"
            and self._fingerprint is not None
            and self._fingerprint.triplet_coordinates
            and not fingerprint.triplet_coordinates
        ):
            return "ambiguous_phase_relation"
        self._fingerprint = fingerprint
        self._fingerprint_mode = "phase"
        self._phase_reference_frame = reference_frame
        self._phase_fingerprint_frame = frame_index
        self._fingerprint_event_id = context.event_id
        return None

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

    def _event_hold(self, event: MergeEvent, reason: str) -> MergeSplitDecision:
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
                "anchor_count": len(self._current_anchors),
                "fingerprint_pair_count": (
                    len(self._fingerprint.pair_coordinates)
                    if self._fingerprint is not None
                    else 0
                ),
                "fingerprint_mode": self._fingerprint_mode,
                "phase_reference_frame": self._phase_reference_frame,
                "phase_fingerprint_frame": self._phase_fingerprint_frame,
                "fingerprint_event_id": self._fingerprint_event_id,
                "phase_selected_anchor_count": (
                    self._merge_context.phase_anchor_selection_count
                    if self._merge_context is not None
                    else 0
                ),
                "phase_best_triangle_quality": (
                    self._merge_context.phase_anchor_best_triangle_quality
                    if self._merge_context is not None
                    else None
                ),
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
            and not _is_duplicate_observation(target_candidate, candidate)
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
    others = [
        candidate
        for candidate in candidates
        if candidate is not target_candidate
        and not _is_duplicate_observation(target_candidate, candidate)
    ]
    return _nearest_candidate(others, target_candidate.center)


def _is_local_visible_pair(
    target_candidate: Candidate,
    collision_candidate: Candidate,
    *,
    stable_scale_px: float,
) -> bool:
    target_bbox = target_candidate.bbox
    collision_bbox = collision_candidate.bbox
    horizontal_gap = max(
        target_bbox[0] - collision_bbox[2],
        collision_bbox[0] - target_bbox[2],
        0.0,
    )
    vertical_gap = max(
        target_bbox[1] - collision_bbox[3],
        collision_bbox[1] - target_bbox[3],
        0.0,
    )
    normalized_gap = hypot(horizontal_gap, vertical_gap) / max(
        1.0,
        stable_scale_px,
    )
    return normalized_gap <= 1.5


def _most_overlapping_candidate(
    target_candidate: Candidate | None,
    candidates: Sequence[Candidate],
) -> Candidate | None:
    if target_candidate is None:
        return None
    others = [
        candidate
        for candidate in candidates
        if candidate is not target_candidate
        and not _is_duplicate_observation(target_candidate, candidate)
    ]
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


def _bbox_union(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    return (
        min(left[0], right[0]),
        min(left[1], right[1]),
        max(left[2], right[2]),
        max(left[3], right[3]),
    )


def _bbox_size(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    return (max(0.0, bbox[2] - bbox[0]), max(0.0, bbox[3] - bbox[1]))


def _bbox_size_residual(
    bbox: tuple[float, float, float, float],
    expected_size: tuple[float, float],
    scale: float,
) -> float:
    width, height = _bbox_size(bbox)
    return (
        abs(width - expected_size[0]) + abs(height - expected_size[1])
    ) / (2.0 * scale)


def _bbox_edge_residual(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
    scale: float,
) -> float:
    return sum(abs(left[index] - right[index]) for index in range(4)) / (4.0 * scale)


def _is_duplicate_observation(left: Candidate, right: Candidate) -> bool:
    left_area = _bbox_area(left.bbox)
    right_area = _bbox_area(right.bbox)
    smaller_area = min(left_area, right_area)
    larger_area = max(left_area, right_area)
    if smaller_area <= 0.0 or larger_area <= 0.0:
        return False
    area_similarity = smaller_area / larger_area
    covered_fraction = _bbox_intersection(left.bbox, right.bbox) / smaller_area
    center_distance = hypot(
        left.center[0] - right.center[0],
        left.center[1] - right.center[1],
    )
    normalized_center_distance = center_distance / max(1.0, left_area**0.5)
    return (
        area_similarity >= 0.7
        and covered_fraction >= 0.7
        and normalized_center_distance <= 0.25
    )


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
