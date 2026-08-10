# 모든 입력 시간에 ±5% 랜덤을 한 번만 적용하고 서로 다른 키의 동시 입력을 허용하는 입력 관리자
from __future__ import annotations

import random
import time
from typing import Callable

from core.humanize.intent import Intent
from core.humanize.timing import down_5


class Humanizer:
    def __init__(self, backend, sleep_fn: Callable[[float], None] | None = None,
                 rng: random.Random | None = None):
        self._backend = backend
        self._sleep = sleep_fn or time.sleep
        self._rng = rng or random.Random()
        self._held: str | None = None
        self._held_keys: set[str] = set()
        self._press_counts: dict[str, int] = {}

    def humanize(self, value: float) -> float:
        """입력된 수치에 ±5%를 한 번 적용해 소수점 넷째 자리로 반환한다."""
        return down_5(value, self._rng)

    def sleep_humanized(self, value: float) -> float:
        applied = self.humanize(value)
        self._sleep(applied)
        return applied

    def _press_key(self, key: str) -> bool:
        """키별 참조 수를 올리고 첫 입력일 때만 실제 key_down을 보낸다."""
        count = self._press_counts.get(key, 0)
        if count == 0:
            self._backend.key_down(key)
        self._press_counts[key] = count + 1
        return count == 0

    def _release_key(self, key: str) -> bool:
        """마지막 사용자가 키를 놓을 때만 실제 key_up을 보낸다."""
        count = self._press_counts.get(key, 0)
        if count <= 0:
            return False
        if count == 1:
            self._backend.key_up(key)
            self._press_counts.pop(key, None)
            return True
        self._press_counts[key] = count - 1
        return False

    def _force_press_key(self, key: str) -> int:
        """사다리 중요 입력은 남아 있는 참조를 정리하고 실제 key_down을 다시 보낸다."""
        previous_count = self._press_counts.pop(key, 0)
        self._held_keys.discard(key)
        if previous_count > 0:
            self._backend.key_up(key)
        self._backend.key_down(key)
        self._press_counts[key] = 1
        return previous_count

    def hold_dir(self, key: str) -> None:
        """같은 방향은 유지하고 방향 전환은 대기 없이 즉시 실행한다."""
        if self._held == key:
            return
        previous = self._held
        self._held = key
        if previous is not None:
            self._release_key(previous)
        self._press_key(key)

    def force_dir(self, key: str) -> dict[str, float | int | str]:
        """사다리 점프 직전 반대 방향을 실제 해제하고 목표 방향을 강제 재전송한다."""
        opposite = "left" if key == "right" else "right"
        started_at = time.monotonic()
        opposite_refs = self._press_counts.pop(opposite, 0)
        self._backend.key_up(opposite)
        opposite_up_at = time.monotonic()

        target_refs = self._press_counts.get(key, 0)
        self._backend.key_down(key)
        target_down_at = time.monotonic()

        self._press_counts[key] = 1
        self._held = key
        return {
            "direction": key,
            "opposite": opposite,
            "opposite_refs": opposite_refs,
            "target_refs": target_refs,
            "opposite_up_sec": opposite_up_at - started_at,
            "target_down_sec": target_down_at - opposite_up_at,
            "total_sec": target_down_at - started_at,
        }

    def refresh_dir(self) -> None:
        if self._held is not None:
            self._backend.key_down(self._held)

    def release_dir(self) -> None:
        if self._held is not None:
            key = self._held
            self._held = None
            self._release_key(key)

    def held_dir(self) -> str | None:
        return self._held

    def hold(self, key: str) -> None:
        if key not in self._held_keys:
            self._held_keys.add(key)
            self._press_key(key)

    def release(self, key: str) -> None:
        if key in self._held_keys:
            self._held_keys.discard(key)
            self._release_key(key)

    def force_release_key(self, key: str) -> None:
        """특정 키가 입력 상태로 남지 않도록 카운트를 정리하고 key_up을 보낸다."""
        if not key:
            return
        self._press_counts.pop(key, None)
        self._held_keys.discard(key)
        if self._held == key:
            self._held = None
        self._backend.key_up(key)

    def release_all(self) -> None:
        for key in list(self._press_counts):
            self._backend.key_up(key)
        self._press_counts.clear()
        self._held = None
        self._held_keys.clear()

    def perform(self, intent: Intent, trace_fn=None) -> float:
        """서로 다른 키를 막지 않고 즉시 입력한 뒤 적용된 유지시간 후 해제한다."""
        if intent.action in {"hold", "move_dir"}:
            self._backend.key_down(intent.key)
            return 0.0

        hold = self.humanize(intent.base_hold_sec)
        if trace_fn:
            trace_fn(
                f"점프 요청, 유지시간 설정={intent.base_hold_sec:.4f}, 적용={hold:.4f}초"
            )
            trace_fn("동시 입력 허용, 입력 대기=0.0000초")
        self._press_key(intent.key)
        if trace_fn:
            trace_fn(f"{intent.key} key_down 전달")
        try:
            self._sleep(hold)
        finally:
            self._release_key(intent.key)
            if trace_fn:
                trace_fn(f"{intent.key} key_up 전달, 실제 유지={hold:.4f}초")
        return hold

    def perform_ladder_jump(
        self,
        jump_key: str,
        jump_hold_sec: float,
        up_delay_sec: float,
        trace_fn=None,
    ) -> dict[str, float]:
        """사다리 점프와 Up을 실행하되 대기 중 전역 입력 잠금을 보유하지 않는다."""
        jump_hold = self.humanize(jump_hold_sec)
        if trace_fn:
            trace_fn(
                f"점프 요청, 유지시간 설정={jump_hold_sec:.4f}, "
                f"적용={jump_hold:.4f}초"
            )
            trace_fn("사다리 점프 우선 입력 시작")

        send_started_at = time.monotonic()
        previous_count = self._force_press_key(jump_key)
        jump_down_at = time.monotonic()
        if trace_fn:
            trace_fn(
                f"{jump_key} key_down 실제 전송, 이전 참조={previous_count}, "
                f"입력 호출={jump_down_at - send_started_at:.4f}초"
            )

        self._sleep(jump_hold)
        jump_release_started_at = time.monotonic()
        jump_released = self._release_key(jump_key)
        jump_up_at = time.monotonic()
        if trace_fn:
            trace_fn(
                f"{jump_key} key_up 실제 전송={jump_released}, "
                f"실제 유지={jump_up_at - jump_down_at:.4f}초, "
                f"입력 호출={jump_up_at - jump_release_started_at:.4f}초"
            )

        direction_release_started_at = time.monotonic()
        self.release_dir()
        direction_up_at = time.monotonic()
        if trace_fn:
            trace_fn(
                "점프키 해제 후 좌우 방향키 해제, "
                f"입력 호출={direction_up_at - direction_release_started_at:.4f}초"
            )

        up_deadline = jump_down_at + max(0.0, up_delay_sec)
        remaining = up_deadline - time.monotonic()
        if remaining > 0.0:
            self._sleep(remaining)

        up_requested_at = time.monotonic()
        self.hold("up")
        up_down_at = time.monotonic()
        if trace_fn:
            trace_fn("사다리 점프 우선 입력 종료")

        return {
            "jump_down_at": jump_down_at,
            "jump_up_at": jump_up_at,
            "direction_up_at": direction_up_at,
            "up_requested_at": up_requested_at,
            "up_down_at": up_down_at,
            "jump_hold_sec": jump_hold,
        }
