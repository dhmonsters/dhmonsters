# 동선 실행기가 사용하는 최신 캐릭터 좌표를 스레드 안전하게 공유한다.
from __future__ import annotations

import threading
import time

from core.navigation.route_state import PositionSample


class LatestPositionStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sample: PositionSample | None = None
        self._sequence = 0

    def publish(self, x: int, y: int, captured_at: float | None = None) -> PositionSample:
        with self._lock:
            self._sequence += 1
            self._sample = PositionSample(
                x=int(x), y=int(y), sequence=self._sequence,
                captured_at=time.monotonic() if captured_at is None else float(captured_at),
            )
            return self._sample

    def latest(self, max_age_sec: float | None = None,
               now: float | None = None) -> PositionSample | None:
        with self._lock:
            sample = self._sample
        if sample is None:
            return None
        if max_age_sec is not None:
            current = time.monotonic() if now is None else float(now)
            if current - sample.captured_at > max(0.0, float(max_age_sec)):
                return None
        return sample
