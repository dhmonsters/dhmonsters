# 동선 단계 실패 시 재시도와 복구 단계 이동 정책을 결정한다.
from __future__ import annotations

from core.navigation.route_state import FailureAction, PositionSample, RouteStep, RouteStepType


class RouteRecoveryResolver:
    @staticmethod
    def _floor_y(step: RouteStep) -> int | None:
        value = step.parameters.get("pos_y")
        if value is not None:
            return int(value)
        y_min = step.parameters.get("y_min")
        y_max = step.parameters.get("y_max")
        if y_min is not None and y_max is not None:
            return int(round((float(y_min) + float(y_max)) / 2.0))
        return None

    @staticmethod
    def _x_distance(step: RouteStep, x: int) -> int:
        params = step.parameters
        start_x = int(params.get("start_x", params.get("target_x", 0)))
        end_x = int(params.get("end_x", params.get("target_x", start_x)))
        left_x, right_x = sorted((start_x, end_x))
        if left_x <= x <= right_x:
            return 0
        return min(abs(x - left_x), abs(x - right_x))

    def nearest_move_index(self, steps: list[RouteStep],
                           sample: PositionSample) -> int | None:
        candidates: list[tuple[int, int, int]] = []
        for index, step in enumerate(steps):
            if step.type != RouteStepType.MOVE:
                continue
            floor_y = self._floor_y(step)
            if floor_y is None:
                continue
            candidates.append((abs(sample.y - floor_y), self._x_distance(step, sample.x), index))
        if not candidates:
            return None
        return min(candidates)[2]

    def is_floor_change(self, current: RouteStep, candidate: RouteStep,
                        sample: PositionSample, tolerance: int = 8,
                        hysteresis: int = 4) -> bool:
        current_y = self._floor_y(current)
        candidate_y = self._floor_y(candidate)
        if current_y is None or candidate_y is None or current_y == candidate_y:
            return False
        current_gap = abs(sample.y - current_y)
        candidate_gap = abs(sample.y - candidate_y)
        return current_gap > max(0, int(tolerance)) and (
            candidate_gap + max(0, int(hysteresis)) < current_gap
        )

    def resolve(self, step: RouteStep, retry_count: int,
                id_to_index: dict[str, int]) -> tuple[str, int | None]:
        policy = step.failure
        if retry_count < max(0, int(policy.max_retries)):
            return "retry", None
        if policy.action == FailureAction.REAPPROACH and policy.recovery_step_id:
            target = id_to_index.get(policy.recovery_step_id)
            if target is not None:
                return "recover", target
        if policy.action == FailureAction.SKIP:
            return "skip", None
        return "stop", None
