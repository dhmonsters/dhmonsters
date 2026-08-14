# MapleHunter 방식으로 사다리 접근부터 등반 완료까지 상태 기반으로 처리하는 컨트롤러
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import time

from core.humanize.priority_input_executor import PriorityInputExecutor
from core.navigation.ladder_trace import LadderTraceBuffer


class LadderState(Enum):
    APPROACH = auto()
    COMMIT = auto()
    VERIFY = auto()
    CLIMB = auto()
    ARRIVED = auto()
    RECOVER = auto()


@dataclass(frozen=True)
class LadderControllerConfig:
    launch_distance: float = 5.0
    jump_hold_sec: float = 0.10
    up_delay_sec: float = 0.125
    x_tolerance: int = 3
    y_rise_required: int = 3
    stable_samples: int = 2
    verify_timeout_sec: float = 0.10
    arrival_tolerance: int = 2
    poll_sec: float = 0.03


class LadderController:
    def __init__(
        self,
        input_backend,
        direction_owner,
        position_sample_fn,
        position_fn,
        finish_climb_fn,
        ladder_motion_fn,
        stop_fn,
        sleep_fn,
        log_fn,
        jump_key: str,
        config: LadderControllerConfig,
    ):
        self._backend = input_backend
        self._directions = direction_owner
        self._sample_fn = position_sample_fn
        self._position_fn = position_fn
        self._finish_climb = finish_climb_fn
        self._ladder_motion = ladder_motion_fn
        self._stop = stop_fn
        self._sleep = sleep_fn
        self._log = log_fn
        self._jump_key = jump_key
        self._cfg = config
        self._inputs = PriorityInputExecutor(input_backend, direction_owner, sleep_fn=sleep_fn)
        self.state = LadderState.APPROACH
        self._debug: dict | None = None

    def debug_state(self) -> dict | None:
        return dict(self._debug) if self._debug else None

    def _sample(self):
        if self._sample_fn is not None:
            position, observed_at = self._sample_fn()
            return position, observed_at
        position = self._position_fn()
        return position, time.monotonic() if position is not None else None

    def _set_state(self, state: LadderState, **details) -> None:
        self.state = state
        self._debug = {"phase": state.name, **details}

    def _direction_to(self, x: int, target_x: float, fallback: str = "right") -> str:
        if x < target_x:
            return "right"
        if x > target_x:
            return "left"
        return fallback

    def run(self, block, max_steps: int) -> bool:
        ladder_x = int(block.ladder_x)
        y_top = int(block.y_top)
        y_bot = int(block.y_bot)
        self._ladder_motion(True)
        try:
            while not self._stop():
                position, _observed_at = self._sample()
                if position is None:
                    self._inputs.release_ladder_inputs()
                    self._sleep(self._cfg.poll_sec)
                    continue
                x, y = position
                if y <= y_top + self._cfg.arrival_tolerance:
                    self._set_state(LadderState.ARRIVED, x=x, y=y)
                    return True

                already_grabbed = (
                    y <= y_bot - self._cfg.y_rise_required
                    and y > y_top + self._cfg.arrival_tolerance
                    and abs(x - ladder_x) <= self._cfg.x_tolerance
                )
                if already_grabbed:
                    self._set_state(LadderState.CLIMB, x=x, y=y, ladder_x=ladder_x)
                    self._directions.release_direction()
                    self._directions.hold_action("up")
                    if self._finish_climb(ladder_x, y_top, max_steps, "right"):
                        self._set_state(LadderState.ARRIVED, x=x, y=y)
                        return True

                if self._jump_attempt(ladder_x, y_top, max_steps):
                    self._set_state(LadderState.ARRIVED, ladder_x=ladder_x)
                    return True
                self._set_state(LadderState.RECOVER, reason="grab_failed")
                self._inputs.release_ladder_inputs()
            return False
        finally:
            self._inputs.release_ladder_inputs()
            self._ladder_motion(False)

    def _jump_attempt(self, ladder_x: int, y_top: int, max_steps: int) -> bool:
        trace = LadderTraceBuffer()
        launch_distance = min(8.0, max(2.0, float(self._cfg.launch_distance)))
        previous_x = None
        approach_direction = self._directions.direction
        launch_position = None
        jump_direction = None
        self._set_state(LadderState.APPROACH, ladder_x=ladder_x)

        for _ in range(max_steps):
            if self._stop():
                return False
            position, observed_at = self._sample()
            if position is None:
                self._sleep(self._cfg.poll_sec)
                continue
            x, y = position
            distance = abs(x - ladder_x)
            crossed = (
                previous_x is not None
                and min(previous_x, x) <= ladder_x <= max(previous_x, x)
            )
            if distance <= launch_distance:
                jump_direction = self._direction_to(
                    x,
                    ladder_x,
                    approach_direction if approach_direction in ("left", "right") else "right",
                )
                launch_position = (x, y, observed_at)
                break
            if crossed:
                approach_direction = self._direction_to(x, ladder_x, approach_direction or "right")
                self._directions.hold_direction(approach_direction)
                self._set_state(
                    LadderState.APPROACH,
                    x=x,
                    y=y,
                    ladder_x=ladder_x,
                    distance=distance,
                    direction=approach_direction,
                    crossed=True,
                )
                trace.add(
                    f"사다리 중심 통과 X={x}, 거리={distance:.2f}, "
                    f"{approach_direction} 방향 재접근"
                )
                previous_x = x
                self._sleep(self._cfg.poll_sec)
                continue
            approach_direction = self._direction_to(x, ladder_x, approach_direction or "right")
            self._directions.hold_direction(approach_direction)
            self._set_state(
                LadderState.APPROACH,
                x=x,
                y=y,
                ladder_x=ladder_x,
                distance=distance,
                direction=approach_direction,
            )
            previous_x = x
            self._sleep(self._cfg.poll_sec)

        if launch_position is None or jump_direction is None:
            trace.add("접근 단계에서 출발 위치를 확보하지 못함")
            trace.flush(self._log)
            return False

        start_x, start_y, start_observed_at = launch_position
        self._set_state(
            LadderState.COMMIT,
            x=start_x,
            y=start_y,
            ladder_x=ladder_x,
            distance=abs(start_x - ladder_x),
            direction=jump_direction,
        )
        trace.add(
            f"COMMIT X={start_x}, Y={start_y}, 거리={abs(start_x - ladder_x)}, "
            f"방향={jump_direction}"
        )
        self._directions.hold_direction(jump_direction)
        trace.add(f"점프 직전 사다리 방향 확정={jump_direction}")
        # 사다리는 별도 입력 경로에서 현재 이동 흐름을 끊지 않고 즉시 점프한다.
        sequence = self._inputs.perform_ladder_jump(
            jump_key=self._jump_key,
            jump_hold_sec=self._cfg.jump_hold_sec,
            up_delay_sec=self._cfg.up_delay_sec,
            direction=jump_direction,
            trace_fn=trace.add,
        )
        trace.add(
            f"입력 완료 Alt={sequence['jump_up_at'] - sequence['jump_down_at']:.4f}초, "
            f"Up={sequence['up_down_at'] - sequence['jump_down_at']:.4f}초"
        )

        self._set_state(LadderState.VERIFY, ladder_x=ladder_x, start_y=start_y)
        deadline = time.monotonic() + self._cfg.verify_timeout_sec
        stable = 0
        last_seen_at = start_observed_at
        last_position = (start_x, start_y)
        while time.monotonic() < deadline and not self._stop():
            position, observed_at = self._sample()
            if position is None or observed_at is None or observed_at <= (last_seen_at or 0.0):
                self._sleep(self._cfg.poll_sec)
                continue
            last_seen_at = observed_at
            current_x, current_y = position
            last_position = position
            x_aligned = abs(current_x - ladder_x) <= self._cfg.x_tolerance
            y_risen = current_y <= start_y - self._cfg.y_rise_required
            stable = stable + 1 if x_aligned and y_risen else 0
            self._set_state(
                LadderState.VERIFY,
                x=current_x,
                y=current_y,
                ladder_x=ladder_x,
                stable=stable,
            )
            if stable >= self._cfg.stable_samples:
                trace.add(
                    f"잡기 확인 X 오차={abs(current_x - ladder_x)}, "
                    f"Y={start_y}→{current_y}, 연속={stable}"
                )
                trace.flush(self._log)
                self._set_state(LadderState.CLIMB, x=current_x, y=current_y)
                return self._finish_climb(ladder_x, y_top, max_steps, jump_direction)
            self._sleep(self._cfg.poll_sec)

        trace.add(
            f"잡기 실패 마지막 X={last_position[0]}, Y={last_position[1]}, "
            f"X 오차={abs(last_position[0] - ladder_x)}, 연속={stable}"
        )
        trace.flush(self._log)
        return False
