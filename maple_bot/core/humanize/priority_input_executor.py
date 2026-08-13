# 사다리 점프 입력을 별도 큐 없이 즉시 순서대로 전송한다.
from __future__ import annotations

import time

from core.humanize.timing import down_5


class PriorityInputExecutor:
    def __init__(self, input_backend, direction_owner, sleep_fn=None):
        self._backend = input_backend
        self._directions = direction_owner
        self._sleep = sleep_fn or time.sleep
        self._ladder_critical = False

    def ladder_critical_active(self) -> bool:
        return self._ladder_critical

    def perform_ladder_jump(
        self,
        jump_key: str,
        jump_hold_sec: float,
        up_delay_sec: float,
        direction: str | None = None,
        trace_fn=None,
    ) -> dict[str, float]:
        self._ladder_critical = True
        jump_hold = down_5(jump_hold_sec)
        up_delay = max(0.0, float(up_delay_sec))
        started_at = time.monotonic()
        try:
            self._backend.begin_priority()
            if direction:
                self._directions.hold_direction(direction)
            jump_down_at = time.monotonic()
            self._backend.key_down(jump_key)
            self._sleep(jump_hold)
            self._backend.key_up(jump_key)
            jump_up_at = time.monotonic()
            self._directions.release_direction()
            remaining = max(0.0, up_delay - jump_hold)
            if remaining:
                self._sleep(remaining)
            self._backend.key_down("up")
            up_down_at = time.monotonic()
            if trace_fn:
                trace_fn(
                    f"사다리 즉시 입력 완료 Alt={jump_hold:.4f}초, "
                    f"Up={up_delay:.4f}초"
                )
            return {
                "jump_down_at": jump_down_at,
                "jump_up_at": jump_up_at,
                "up_down_at": up_down_at,
                "worker_started_at": started_at,
                "worker_queue_sec": 0.0,
            }
        finally:
            try:
                self._backend.end_priority()
            finally:
                self._ladder_critical = False

    def release_ladder_inputs(self) -> None:
        self._backend.key_up("up")
        self._directions.release_direction()
