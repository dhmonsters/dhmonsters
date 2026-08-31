# 주기 버프 입력을 입력 백엔드로 직접 전송합니다.
from __future__ import annotations

from dataclasses import dataclass

from core.input_timing import randomize_interval

@dataclass
class Buff:
    key: str = ""
    interval: float = 60.0
    hold_sec: float = 0.8


class BuffManager:
    def __init__(self, input_backend, buffs: list[Buff], log_fn=None, gap: float = 2.5,
                 jitter: float = 0.05):
        self._input = input_backend
        self._buffs = buffs
        self._last: dict[int, float] = {}
        self._iv: dict[int, float] = {}
        self._log = log_fn or (lambda msg: None)
        self._gap = gap
        self._jit = jitter
        self._next_allowed = -1e9

    def tick(self, now: float) -> None:
        if now < self._next_allowed:
            return
        for index, buff in enumerate(self._buffs):
            if not buff.key:
                continue
            last = self._last.get(index, -1e9)
            interval = self._iv.get(index, buff.interval)
            if now - last >= interval:
                self._input.press(buff.key, buff.hold_sec)
                self._last[index] = now
                self._iv[index] = randomize_interval(buff.interval)
                self._next_allowed = now + randomize_interval(self._gap)
                self._log(f"버프 [{buff.key}]")
                return
