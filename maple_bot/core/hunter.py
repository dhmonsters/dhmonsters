# 사냥 패턴 실행 state machine - 스텝을 순서대로 실행하고 루프
from __future__ import annotations
import time
import logging
from typing import Callable

from core.pattern import HuntPattern, Step
from core.input_controller import InputController
from core.detector import Detector
from core.screen_reader import ScreenReader

logger = logging.getLogger(__name__)


class Hunter:
    def __init__(
        self,
        input_ctrl: InputController,
        detector: Detector,
        screen_reader: ScreenReader,
        on_status: Callable[[str], None] | None = None,
    ):
        self._input = input_ctrl
        self._detector = detector
        self._screen = screen_reader
        self._on_status = on_status or (lambda msg: None)

        self._pattern: HuntPattern | None = None
        self._step_index: int = 0
        # skill 쿨다운 추적: key → 마지막 사용 시각
        self._skill_last_used: dict[str, float] = {}

    # ── 외부 제어 ─────────────────────────────────────────────────────
    def set_pattern(self, pattern: HuntPattern) -> None:
        self._pattern = pattern
        self._step_index = 0
        self._skill_last_used.clear()

    def reset(self) -> None:
        self._step_index = 0

    def has_pattern(self) -> bool:
        return self._pattern is not None and len(self._pattern.steps) > 0

    # ── 메인 실행 (bot_loop에서 매 틱 호출) ──────────────────────────
    def run_one_step(self, screenshot=None) -> None:
        """현재 스텝을 실행하고 다음 스텝으로 전진."""
        if not self.has_pattern():
            return

        steps = self._pattern.steps
        step = steps[self._step_index]

        if screenshot is None:
            screenshot = self._screen.capture()

        self._execute(step, screenshot)
        self._advance()

    # ── 스텝 실행 ─────────────────────────────────────────────────────
    def _execute(self, step: Step, screenshot) -> None:
        t = step.type
        p = step.params
        self._status(f"스텝: {step.label()}")

        if t == "move":
            self._do_move(p)

        elif t == "jump":
            self._do_jump(p)

        elif t == "rope":
            self._do_rope(p)

        elif t == "attack":
            self._do_attack(p)

        elif t == "attack_if_monster":
            self._do_attack_if_monster(p, screenshot)

        elif t == "skill":
            self._do_skill(p)

        elif t == "wait":
            time.sleep(float(p.get("duration", 0.5)))

        else:
            logger.warning("알 수 없는 스텝 타입: %s", t)

    # ── 스텝별 동작 ───────────────────────────────────────────────────
    def _do_move(self, p: dict) -> None:
        direction = p.get("direction", "right")
        duration = float(p.get("duration", 1.0))
        key = "left" if direction == "left" else "right"
        self._input.press_key(key, hold_sec=duration)

    def _do_jump(self, p: dict) -> None:
        direction = p.get("direction", "none")
        if direction == "up":
            # 위 방향키 + 점프키 동시
            import win32api, win32con
            win32api.keybd_event(win32con.VK_UP, 0, 0, 0)
            self._input.press_key("alt")          # 메이플 기본 점프키 alt
            win32api.keybd_event(win32con.VK_UP, 0, win32con.KEYEVENTF_KEYUP, 0)
        elif direction == "down":
            import win32api, win32con
            win32api.keybd_event(win32con.VK_DOWN, 0, 0, 0)
            self._input.press_key("alt")
            win32api.keybd_event(win32con.VK_DOWN, 0, win32con.KEYEVENTF_KEYUP, 0)
        else:
            self._input.press_key("alt")
        time.sleep(0.4)

    def _do_rope(self, p: dict) -> None:
        direction = p.get("direction", "up")
        duration = float(p.get("duration", 1.0))
        key = "up" if direction == "up" else "down"
        self._input.press_key(key, hold_sec=duration)

    def _do_attack(self, p: dict) -> None:
        key = p.get("key", "ctrl")
        repeat = int(p.get("repeat", 1))
        interval = float(p.get("interval", 0.15))
        for _ in range(repeat):
            self._input.press_key(key)
            time.sleep(interval)

    def _do_attack_if_monster(self, p: dict, screenshot) -> None:
        template = p.get("monster_template", "")
        if not template:
            # 템플릿 미설정이면 무조건 공격
            self._do_attack(p)
            return

        if self._detector.has_monster(screenshot, template):
            self._do_attack(p)
        else:
            self._status("몬스터 미감지 — 공격 스킵")

    def _do_skill(self, p: dict) -> None:
        key = p.get("key", "1")
        cooldown = float(p.get("cooldown", 0))
        now = time.time()
        last = self._skill_last_used.get(key, 0)

        if now - last >= cooldown:
            self._input.press_key(key)
            self._skill_last_used[key] = now
        else:
            remaining = cooldown - (now - last)
            self._status(f"스킬 {key} 쿨다운 {remaining:.1f}초 남음")

    # ── 스텝 전진 ─────────────────────────────────────────────────────
    def _advance(self) -> None:
        if not self._pattern:
            return
        self._step_index += 1
        if self._step_index >= len(self._pattern.steps):
            if self._pattern.loop:
                self._step_index = 0
                self._status("패턴 1사이클 완료 — 반복")
            else:
                self._step_index = len(self._pattern.steps) - 1
                self._status("패턴 완료")

    # ── 내부 유틸 ─────────────────────────────────────────────────────
    def _status(self, msg: str) -> None:
        logger.debug(msg)
        self._on_status(msg)
