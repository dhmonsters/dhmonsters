# 주기 펫먹이 입력을 입력 백엔드로 직접 전송합니다.
from __future__ import annotations

import time

class PetFeeder:
    def __init__(self, input_backend, key: str = "", interval: float = 600.0,
                 log_fn=None, label: str = "펫먹이", count: int = 1, gap: float = 0.4,
                 jitter: float = 0.05, sleep_fn=None):
        self._input = input_backend
        self._key = key
        self._interval = interval
        self._last = -1e9
        self._iv = None
        self._log = log_fn or (lambda msg: None)
        self._label = label
        self._count = max(1, int(count))
        self._gap = gap
        self._jit = jitter
        self._sleep = sleep_fn or time.sleep

    def tick(self, now: float) -> None:
        if not self._key:
            return
        interval = self._iv if self._iv is not None else self._interval
        if now - self._last < interval:
            return
        for index in range(self._count):
            self._input.press(self._key, 0.05)
            if index < self._count - 1:
                self._sleep(self._gap)
        self._last = now
        self._iv = self._interval
        suffix = f" {self._count}회" if self._count > 1 else ""
        self._log(f"{self._label}{suffix} [{self._key}]")
