# 준비 구간의 지역 배경 흐름과 불확실성을 강건하게 요약합니다.
from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from statistics import median

from .models import Candidate


_MINIMUM_BACKGROUND_MATCHES = 3


@dataclass(frozen=True)
class BackgroundFlowSample:
    frame_index: int
    dx_ratio: float
    dy_ratio: float
    matched_count: int
    dispersion: float


@dataclass(frozen=True)
class BackgroundFlowProfile:
    velocity_ratio: tuple[float, float] | None
    dispersion: float
    valid_transitions: int
    missing_transitions: int
    reason: str

    @property
    def available(self) -> bool:
        return self.velocity_ratio is not None and self.valid_transitions > 0


def build_background_flow_profile(
    frames: tuple[tuple[int, tuple[Candidate, ...]], ...],
    *,
    frame_shape: tuple[int, int],
) -> BackgroundFlowProfile:
    width = max(1.0, float(frame_shape[1]))
    height = max(1.0, float(frame_shape[0]))
    samples: list[BackgroundFlowSample] = []
    missing = 0

    for (frame_index, previous), (_next_index, current) in zip(frames, frames[1:]):
        matches = _minimum_cost_background_matches(previous, current, frame_shape)
        if not matches:
            missing += 1
            continue

        dx_values = [(right.center[0] - left.center[0]) / width for left, right in matches]
        dy_values = [(right.center[1] - left.center[1]) / height for left, right in matches]
        dx_ratio = median(dx_values)
        dy_ratio = median(dy_values)
        residuals = [
            hypot(dx - dx_ratio, dy - dy_ratio)
            for dx, dy in zip(dx_values, dy_values)
        ]
        samples.append(
            BackgroundFlowSample(
                frame_index=frame_index,
                dx_ratio=dx_ratio,
                dy_ratio=dy_ratio,
                matched_count=len(matches),
                dispersion=median(residuals),
            )
        )

    if not samples:
        return BackgroundFlowProfile(
            None,
            float("inf"),
            0,
            missing,
            "insufficient_background_motion",
        )

    velocity = (
        median(sample.dx_ratio for sample in samples),
        median(sample.dy_ratio for sample in samples),
    )
    return BackgroundFlowProfile(
        velocity,
        median(sample.dispersion for sample in samples),
        len(samples),
        missing,
        "available",
    )


def _minimum_cost_background_matches(
    previous: tuple[Candidate, ...],
    current: tuple[Candidate, ...],
    frame_shape: tuple[int, int],
) -> tuple[tuple[Candidate, Candidate], ...]:
    previous = _deduplicate_candidates(previous)
    current = _deduplicate_candidates(current)
    if not previous or not current:
        return ()

    height = max(1.0, float(frame_shape[0]))
    width = max(1.0, float(frame_shape[1]))
    if len(previous) <= len(current):
        costs = [
            [_normalized_distance(left, right, width, height) for right in current]
            for left in previous
        ]
        assignment = _minimum_cost_assignment(costs)
        pairs = tuple((previous[index], current[column]) for index, column in enumerate(assignment))
    else:
        costs = [
            [_normalized_distance(left, right, width, height) for right in previous]
            for left in current
        ]
        assignment = _minimum_cost_assignment(costs)
        pairs = tuple((previous[column], current[index]) for index, column in enumerate(assignment))

    if len(pairs) < _MINIMUM_BACKGROUND_MATCHES:
        return ()

    costs_by_pair = [
        _normalized_distance(left, right, width, height)
        for left, right in pairs
    ]
    median_cost = median(costs_by_pair)
    cost_mad = median(abs(cost - median_cost) for cost in costs_by_pair)
    maximum_cost = median_cost + cost_mad
    reliable_pairs = tuple(
        pair
        for pair, cost in zip(pairs, costs_by_pair)
        if cost <= maximum_cost
    )
    return reliable_pairs


def _deduplicate_candidates(candidates: tuple[Candidate, ...]) -> tuple[Candidate, ...]:
    representatives: list[Candidate] = []
    for candidate in sorted(candidates, key=_candidate_sort_key):
        if any(_are_duplicate_observations(candidate, existing) for existing in representatives):
            continue
        representatives.append(candidate)
    return tuple(representatives)


def _candidate_sort_key(candidate: Candidate) -> tuple[float, tuple[float, float, float, float], str]:
    return (-float(candidate.score), candidate.bbox, candidate.candidate_id)


def _are_duplicate_observations(left: Candidate, right: Candidate) -> bool:
    left_area = _bbox_area(left.bbox)
    right_area = _bbox_area(right.bbox)
    smaller_area = min(left_area, right_area)
    larger_area = max(left_area, right_area)
    if smaller_area <= 0.0 or larger_area <= 0.0:
        return False

    center_distance = hypot(
        left.center[0] - right.center[0],
        left.center[1] - right.center[1],
    )
    return (
        smaller_area / larger_area >= 0.7
        and _bbox_intersection(left.bbox, right.bbox) / smaller_area >= 0.7
        and center_distance / max(1.0, left_area**0.5) <= 0.25
    )


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    return max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])


def _bbox_intersection(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    return max(0.0, min(left[2], right[2]) - max(left[0], right[0])) * max(
        0.0,
        min(left[3], right[3]) - max(left[1], right[1]),
    )


def _normalized_distance(
    left: Candidate,
    right: Candidate,
    width: float,
    height: float,
) -> float:
    return hypot(
        (right.center[0] - left.center[0]) / width,
        (right.center[1] - left.center[1]) / height,
    )


def _minimum_cost_assignment(costs: list[list[float]]) -> tuple[int, ...]:
    row_count = len(costs)
    column_count = len(costs[0])
    row_potential = [0.0] * (row_count + 1)
    column_potential = [0.0] * (column_count + 1)
    column_owner = [0] * (column_count + 1)
    predecessor = [0] * (column_count + 1)

    for row_index in range(1, row_count + 1):
        column_owner[0] = row_index
        minimum = [float("inf")] * (column_count + 1)
        used = [False] * (column_count + 1)
        current_column = 0
        while True:
            used[current_column] = True
            current_row = column_owner[current_column]
            delta = float("inf")
            next_column = 0
            for column_index in range(1, column_count + 1):
                if used[column_index]:
                    continue
                reduced_cost = (
                    costs[current_row - 1][column_index - 1]
                    - row_potential[current_row]
                    - column_potential[column_index]
                )
                if reduced_cost < minimum[column_index]:
                    minimum[column_index] = reduced_cost
                    predecessor[column_index] = current_column
                if minimum[column_index] < delta:
                    delta = minimum[column_index]
                    next_column = column_index
            for column_index in range(column_count + 1):
                if used[column_index]:
                    row_potential[column_owner[column_index]] += delta
                    column_potential[column_index] -= delta
                else:
                    minimum[column_index] -= delta
            current_column = next_column
            if column_owner[current_column] == 0:
                break
        while True:
            previous_column = predecessor[current_column]
            column_owner[current_column] = column_owner[previous_column]
            current_column = previous_column
            if current_column == 0:
                break

    assignment = [-1] * row_count
    for column_index in range(1, column_count + 1):
        owner = column_owner[column_index]
        if owner:
            assignment[owner - 1] = column_index - 1
    return tuple(assignment)
