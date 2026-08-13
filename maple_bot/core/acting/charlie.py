# 찰리중사 이빨 교환 입력을 입력 백엔드로 직접 전송합니다.
from __future__ import annotations

import time

_TOOTH_PER_ROUTINE = 200
_DOWN_REPEAT = 15


class CharlieExchange:
    def __init__(self, input_backend, npc_key: str = "u", sleep_fn=None):
        self._input = input_backend
        self._npc = npc_key
        self._sleep = sleep_fn or time.sleep

    @staticmethod
    def repeat_count(tooth_amount: int) -> int:
        return tooth_amount // _TOOTH_PER_ROUTINE

    def run(self, tooth_amount: int) -> int:
        count = self.repeat_count(tooth_amount)
        for _ in range(count):
            self.run_one_routine()
        return count

    def run_one_routine(self) -> None:
        self._npc_talk()
        self._npc_talk()
        for _ in range(_DOWN_REPEAT):
            self._direction("down")
        self._npc_talk()
        self._direction("left")
        self._npc_talk()
        self._npc_talk()

    def _npc_talk(self) -> None:
        self._sleep(0.5)
        self._input.press(self._npc, 0.05)

    def _direction(self, key: str) -> None:
        self._sleep(0.1)
        self._input.press(key, 0.05)
