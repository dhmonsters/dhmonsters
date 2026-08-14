# 사다리 시도 중 발생한 시각 정보를 메모리에 모아 종료 후 출력하는 추적 버퍼
from __future__ import annotations

import time


class LadderTraceBuffer:
    def __init__(self):
        self._started_at = time.monotonic()
        self._entries: list[tuple[float, str]] = []

    def add(self, message: str) -> None:
        self._entries.append((time.monotonic() - self._started_at, str(message)))

    def flush(self, log_fn, prefix: str = "[사다리추적]") -> None:
        for elapsed, message in self._entries:
            log_fn(f"{prefix} +{elapsed:.4f}초 {message}")
        self._entries.clear()
