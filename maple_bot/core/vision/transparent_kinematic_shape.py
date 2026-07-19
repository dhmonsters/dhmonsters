# 투명도형 후보의 위치, 속도, 박스 형태를 함께 이어 주는 시간축 추적기입니다.
from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass


Point = tuple[float, float]
Candidate = tuple[float, float, float, float, float]


@dataclass
class _BeamState:
    cost: float
    point: Point
    velocity: Point
    area: float | None
    aspect: float | None
    candidate_key: int | str


class TransparentKinematicShapeTracker:
    def __init__(
        self,
        *,
        velocity_alpha: float = 0.9,
        area_weight: float = 40.0,
        aspect_weight: float = 40.0,
    ) -> None:
        self.velocity_alpha = max(0.0, min(1.0, float(velocity_alpha)))
        self.area_weight = max(0.0, float(area_weight))
        self.aspect_weight = max(0.0, float(aspect_weight))
        self.reset()

    def reset(self) -> None:
        self.last_point: Point | None = None
        self.velocity: Point = (0.0, 0.0)
        self.last_area: float | None = None
        self.last_aspect: float | None = None
        self.last_debug: dict[str, object] = {}

    def update(
        self,
        candidates: Sequence[Sequence[float]],
        *,
        white_anchor: Sequence[float] | None = None,
    ) -> Point | None:
        normalized = [self._candidate(row) for row in candidates if len(row) >= 2]
        anchor = self._point(white_anchor)
        if anchor is not None:
            nearest = min(
                normalized,
                key=lambda candidate: self._distance(candidate[:2], anchor),
                default=None,
            )
            area, aspect = self._shape(nearest)
            self._commit(anchor, area=area, aspect=aspect)
            self.last_debug = {
                "reason": "white_anchor",
                "point": anchor,
                "velocity": self.velocity,
            }
            return anchor

        if self.last_point is None:
            if not normalized:
                return None
            selected = max(normalized, key=lambda candidate: candidate[2])
            point = (selected[0], selected[1])
            area, aspect = self._shape(selected)
            self._commit(point, area=area, aspect=aspect)
            self.last_debug = {"reason": "cold_start", "point": point}
            return point

        predicted = (
            self.last_point[0] + self.velocity[0],
            self.last_point[1] + self.velocity[1],
        )
        if not normalized:
            self._commit(predicted, area=self.last_area, aspect=self.last_aspect)
            self.last_debug = {"reason": "coast", "point": predicted}
            return predicted

        selected = min(normalized, key=lambda candidate: self._cost(candidate, predicted))
        point = (selected[0], selected[1])
        area, aspect = self._shape(selected)
        self._commit(point, area=area, aspect=aspect)
        self.last_debug = {
            "reason": "shape_motion_cost",
            "point": point,
            "predicted": predicted,
            "velocity": self.velocity,
            "area": area,
            "aspect": aspect,
        }
        return point

    def _cost(self, candidate: Candidate, predicted: Point) -> float:
        area, aspect = self._shape(candidate)
        position_cost = self._distance(candidate[:2], predicted)
        area_cost = 0.0
        if self.last_area is not None:
            area_cost = self.area_weight * abs(math.log(area / self.last_area))
        aspect_cost = 0.0
        if self.last_aspect is not None:
            aspect_cost = self.aspect_weight * abs(math.log(aspect / self.last_aspect))
        return position_cost + area_cost + aspect_cost

    def _commit(self, point: Point, *, area: float | None, aspect: float | None) -> None:
        point = (float(point[0]), float(point[1]))
        if self.last_point is not None:
            measured = (
                point[0] - self.last_point[0],
                point[1] - self.last_point[1],
            )
            alpha = self.velocity_alpha
            self.velocity = (
                self.velocity[0] * alpha + measured[0] * (1.0 - alpha),
                self.velocity[1] * alpha + measured[1] * (1.0 - alpha),
            )
        self.last_point = point
        if area is not None:
            self.last_area = area
        if aspect is not None:
            self.last_aspect = aspect

    @staticmethod
    def _candidate(row: Sequence[float]) -> Candidate:
        return (
            float(row[0]),
            float(row[1]),
            float(row[2]) if len(row) >= 3 else 0.0,
            max(1.0, float(row[3])) if len(row) >= 4 else 24.0,
            max(1.0, float(row[4])) if len(row) >= 5 else 24.0,
        )

    @staticmethod
    def _point(value: Sequence[float] | None) -> Point | None:
        if value is None or len(value) < 2:
            return None
        return (float(value[0]), float(value[1]))

    @staticmethod
    def _shape(candidate: Candidate | None) -> tuple[float | None, float | None]:
        if candidate is None:
            return (None, None)
        width = max(1.0, float(candidate[3]))
        height = max(1.0, float(candidate[4]))
        return (width * height, width / height)

    @staticmethod
    def _distance(left: Sequence[float], right: Sequence[float]) -> float:
        return math.hypot(float(left[0]) - float(right[0]), float(left[1]) - float(right[1]))


class TransparentKinematicBeamTracker:
    def __init__(
        self,
        *,
        width: int = 4,
        branch: int = 3,
        cost_decay: float = 0.8,
        velocity_alpha: float = 0.9,
        acceleration_weight: float = 0.5,
        area_weight: float = 40.0,
        aspect_weight: float = 40.0,
        yolo_penalty_weight: float = 4.0,
        yolo_full_score: float = 0.4,
        max_jump: float = 140.0,
    ) -> None:
        self.width = max(1, int(width))
        self.branch = max(1, int(branch))
        self.cost_decay = max(0.0, min(1.0, float(cost_decay)))
        self.velocity_alpha = max(0.0, min(1.0, float(velocity_alpha)))
        self.acceleration_weight = max(0.0, float(acceleration_weight))
        self.area_weight = max(0.0, float(area_weight))
        self.aspect_weight = max(0.0, float(aspect_weight))
        self.yolo_penalty_weight = max(0.0, float(yolo_penalty_weight))
        self.yolo_full_score = max(0.01, float(yolo_full_score))
        self.max_jump = max(1.0, float(max_jump))
        self.reset()

    def reset(self) -> None:
        self._states: list[_BeamState] = []
        self.last_debug: dict[str, object] = {}

    @property
    def hypothesis_points(self) -> tuple[Point, ...]:
        return tuple(state.point for state in self._states)

    def update(
        self,
        candidates: Sequence[Sequence[float]],
        *,
        white_anchor: Sequence[float] | None = None,
    ) -> Point | None:
        normalized = [self._candidate(row) for row in candidates if len(row) >= 2]
        anchor = self._point(white_anchor)
        if anchor is not None:
            return self._update_anchor(normalized, anchor)
        if not self._states:
            return self._cold_start(normalized)

        expanded: list[_BeamState] = []
        for state in self._states:
            predicted = (
                state.point[0] + state.velocity[0],
                state.point[1] + state.velocity[1],
            )
            if not normalized:
                expanded.append(_BeamState(
                    self.cost_decay * state.cost + 20.0,
                    predicted,
                    (state.velocity[0] * 0.98, state.velocity[1] * 0.98),
                    state.area,
                    state.aspect,
                    "coast",
                ))
                continue
            local = [
                (self._transition_cost(state, predicted, candidate), index, candidate)
                for index, candidate in enumerate(normalized)
                if self._distance(candidate[:2], predicted) <= self.max_jump
            ]
            if not local:
                local = [
                    (self._transition_cost(state, predicted, candidate), index, candidate)
                    for index, candidate in enumerate(normalized)
                ]
            for local_cost, candidate_index, candidate in sorted(local)[: self.branch]:
                point = (candidate[0], candidate[1])
                measured = (
                    point[0] - state.point[0],
                    point[1] - state.point[1],
                )
                alpha = self.velocity_alpha
                velocity = (
                    state.velocity[0] * alpha + measured[0] * (1.0 - alpha),
                    state.velocity[1] * alpha + measured[1] * (1.0 - alpha),
                )
                area, aspect = self._shape(candidate)
                expanded.append(_BeamState(
                    self.cost_decay * state.cost + local_cost,
                    point,
                    velocity,
                    area,
                    aspect,
                    candidate_index,
                ))

        self._states = self._prune(expanded)
        if not self._states:
            self.last_debug = {"reason": "empty", "state_count": 0}
            return None
        best = self._states[0]
        margin = self._states[1].cost - best.cost if len(self._states) >= 2 else 0.0
        self.last_debug = {
            "reason": "beam",
            "point": best.point,
            "velocity": best.velocity,
            "best_cost": best.cost,
            "cost_margin": margin,
            "state_count": len(self._states),
        }
        return best.point

    def _update_anchor(self, candidates: list[Candidate], anchor: Point) -> Point:
        nearest = min(
            candidates,
            key=lambda candidate: self._distance(candidate[:2], anchor),
            default=None,
        )
        area, aspect = self._shape(nearest)
        velocity = (0.0, 0.0)
        if self._states:
            previous = self._states[0]
            measured = (
                anchor[0] - previous.point[0],
                anchor[1] - previous.point[1],
            )
            alpha = self.velocity_alpha
            velocity = (
                previous.velocity[0] * alpha + measured[0] * (1.0 - alpha),
                previous.velocity[1] * alpha + measured[1] * (1.0 - alpha),
            )
        self._states = [_BeamState(0.0, anchor, velocity, area, aspect, "anchor")]
        self.last_debug = {
            "reason": "white_anchor",
            "point": anchor,
            "velocity": velocity,
            "cost_margin": 0.0,
            "state_count": 1,
        }
        return anchor

    def _cold_start(self, candidates: list[Candidate]) -> Point | None:
        if not candidates:
            return None
        selected = max(candidates, key=lambda candidate: candidate[2])
        point = (selected[0], selected[1])
        area, aspect = self._shape(selected)
        self._states = [_BeamState(0.0, point, (0.0, 0.0), area, aspect, 0)]
        self.last_debug = {
            "reason": "cold_start",
            "point": point,
            "velocity": (0.0, 0.0),
            "cost_margin": 0.0,
            "state_count": 1,
        }
        return point

    def _transition_cost(self, state: _BeamState, predicted: Point, candidate: Candidate) -> float:
        point = (candidate[0], candidate[1])
        measured = (
            point[0] - state.point[0],
            point[1] - state.point[1],
        )
        position_cost = self._distance(point, predicted)
        acceleration_cost = self.acceleration_weight * self._distance(measured, state.velocity)
        area, aspect = self._shape(candidate)
        area_cost = 0.0
        if state.area is not None and area is not None:
            area_cost = self.area_weight * abs(math.log(area / state.area))
        aspect_cost = 0.0
        if state.aspect is not None and aspect is not None:
            aspect_cost = self.aspect_weight * abs(math.log(aspect / state.aspect))
        yolo_ratio = min(max(candidate[2], 0.0) / self.yolo_full_score, 1.0)
        yolo_cost = self.yolo_penalty_weight * (1.0 - yolo_ratio)
        return position_cost + acceleration_cost + area_cost + aspect_cost + yolo_cost

    def _prune(self, states: list[_BeamState]) -> list[_BeamState]:
        kept: list[_BeamState] = []
        per_candidate: defaultdict[int | str, int] = defaultdict(int)
        for state in sorted(states, key=lambda row: row.cost):
            if per_candidate[state.candidate_key] >= 2:
                continue
            kept.append(state)
            per_candidate[state.candidate_key] += 1
            if len(kept) >= self.width:
                break
        return kept

    @staticmethod
    def _candidate(row: Sequence[float]) -> Candidate:
        return TransparentKinematicShapeTracker._candidate(row)

    @staticmethod
    def _point(value: Sequence[float] | None) -> Point | None:
        return TransparentKinematicShapeTracker._point(value)

    @staticmethod
    def _shape(candidate: Candidate | None) -> tuple[float | None, float | None]:
        return TransparentKinematicShapeTracker._shape(candidate)

    @staticmethod
    def _distance(left: Sequence[float], right: Sequence[float]) -> float:
        return TransparentKinematicShapeTracker._distance(left, right)
