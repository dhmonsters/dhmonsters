# 키 반복 사냥 실행기 - 스텝별 랜덤 타이밍으로 패턴 실행
from __future__ import annotations
import random
import time
import logging
from typing import Callable

from core.pattern import KeyPattern, KeyStep, ACTION_HOLD, ACTION_TAP, ACTION_COMBO
from core.input_controller import InputController

logger = logging.getLogger(__name__)

# 탭/연속기 홀드 최소 보장 시간 (스텝 설정값이 이보다 작으면 이 값으로 클램프)
_TAP_HOLD_MIN = 0.02


class KeyHunter:
    def __init__(
        self,
        input_ctrl: InputController,
        on_status: Callable[[str], None] | None = None,
        on_move_tick: Callable[[], None] | None = None,
    ):
        self._input = input_ctrl
        self._on_status = on_status or (lambda msg: None)
        self._on_move_tick = on_move_tick or (lambda: None)
        self._pattern: KeyPattern | None = None
        self._step_index: int = 0

    # ── 외부 제어 ─────────────────────────────────────────────────────
    def set_pattern(self, pattern: KeyPattern) -> None:
        self._pattern = pattern
        self._step_index = 0

    def reset(self) -> None:
        self._step_index = 0

    def has_pattern(self) -> bool:
        return self._pattern is not None and len(self._pattern.steps) > 0

    # ── 이동 유지 sleep ───────────────────────────────────────────────
    def _sleep_with_move(self, duration: float) -> None:
        """duration초 동안 50ms 단위로 on_move_tick을 호출해 이동 방향키를 유지한다."""
        _TICK = 0.05
        end = time.time() + duration
        while True:
            remaining = end - time.time()
            if remaining <= 0:
                break
            time.sleep(min(_TICK, remaining))
            self._on_move_tick()

    # ── 메인 실행 (bot_loop에서 매 틱 호출) ──────────────────────────
    def run_one_step(self) -> None:
        """현재 스텝을 랜덤 타이밍으로 실행하고 다음 스텝으로 전진."""
        if not self.has_pattern():
            return

        step = self._pattern.steps[self._step_index]
        self._execute(step)

        # 스텝 사이 랜덤 딜레이 — 이동 유지하며 대기
        delay = random.uniform(
            self._pattern.between_min,
            self._pattern.between_max,
        )
        self._status(f"이동 대기 {delay:.2f}초")
        self._sleep_with_move(delay)

        self._advance()

    # ── 스텝 실행 ─────────────────────────────────────────────────────
    def _execute(self, step: KeyStep) -> None:

        if step.action == ACTION_HOLD:
            duration = random.uniform(step.min_sec, step.max_sec)
            self._status(f"누름 [{step.key}] {duration:.3f}초")
            # hold 구간에도 방향키 유지 (press_key 내부 sleep 대신 직접 제어)
            self._input.key_down(step.key)
            self._sleep_with_move(duration)
            self._input.key_up(step.key)

        elif step.action == ACTION_TAP:
            repeat = random.randint(step.repeat_min, step.repeat_max)
            self._status(f"탭   [{step.key}] {repeat}회  간격 {step.min_sec}~{step.max_sec}초")
            for i in range(repeat):
                hold = self._tap_hold(step)
                self._input.press_key(step.key, hold_sec=hold)
                if i < repeat - 1:
                    gap = random.uniform(step.min_sec, step.max_sec)
                    self._sleep_with_move(gap)

        elif step.action == ACTION_COMBO:
            keys   = step.combo_keys if step.combo_keys else [step.key]
            repeat = random.randint(step.repeat_min, step.repeat_max)
            self._status(f"연속기 [{' → '.join(keys)}] {repeat}회")
            for r in range(repeat):
                for i, k in enumerate(keys):
                    hold = self._tap_hold_at(step, i)
                    self._input.press_key(k, hold_sec=hold)
                    if i < len(keys) - 1:
                        gap = random.uniform(step.min_sec, step.max_sec)
                        self._sleep_with_move(gap)
                # 연속기 1회 완료 후 다음 반복 전 딜레이 (마지막 반복 제외)
                if r < repeat - 1:
                    gap = random.uniform(step.min_sec, step.max_sec)
                    self._sleep_with_move(gap)

    # ── 홀드 시간 계산 ────────────────────────────────────────────────
    @staticmethod
    def _tap_hold(step: "KeyStep") -> float:
        """스텝 공통 홀드 시간(tap 전용)."""
        lo = max(_TAP_HOLD_MIN, step.tap_hold_base - step.tap_hold_var)
        hi = max(lo, step.tap_hold_base + step.tap_hold_var)
        return random.uniform(lo, hi)

    @staticmethod
    def _tap_hold_at(step: "KeyStep", key_index: int) -> float:
        """combo 키별 홀드 시간. combo_holds에 값이 있으면 개별값, 없으면 공통값 사용."""
        holds = step.combo_holds
        if holds and key_index < len(holds):
            base, var = float(holds[key_index][0]), float(holds[key_index][1])
        else:
            base, var = step.tap_hold_base, step.tap_hold_var
        lo = max(_TAP_HOLD_MIN, base - var)
        hi = max(lo, base + var)
        return random.uniform(lo, hi)

    # ── 스텝 전진 ─────────────────────────────────────────────────────
    def _advance(self) -> None:
        if not self._pattern:
            return
        self._step_index += 1
        if self._step_index >= len(self._pattern.steps):
            if self._pattern.loop:
                self._step_index = 0
                self._status("── 패턴 1사이클 완료, 반복 ──")
            else:
                self._step_index = len(self._pattern.steps) - 1

    def _status(self, msg: str) -> None:
        logger.debug(msg)
        self._on_status(msg)
