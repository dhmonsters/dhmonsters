# 캐릭터 좌표 표본을 시간순으로 보관하는 스레드 안전 이력 저장소
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import threading


@dataclass(frozen=True)
class CoordinateSample:
    position: tuple[int, int]
    observed_at: float
    scan_duration_sec: float
    sequence: int


class CoordinateHistory:
    def __init__(self, maxlen: int = 10):
        self._samples: deque[CoordinateSample] = deque(maxlen=max(2, int(maxlen)))
        self._lock = threading.Lock()
        self._sequence = 0

    def append(
        self,
        position: tuple[int, int],
        observed_at: float,
        scan_duration_sec: float,
    ) -> CoordinateSample:
        with self._lock:
            self._sequence += 1
            sample = CoordinateSample(
                position=position,
                observed_at=float(observed_at),
                scan_duration_sec=max(0.0, float(scan_duration_sec)),
                sequence=self._sequence,
            )
            self._samples.append(sample)
            return sample

    def latest(self) -> CoordinateSample | None:
        with self._lock:
            return self._samples[-1] if self._samples else None

    def snapshot(self) -> tuple[CoordinateSample, ...]:
        with self._lock:
            return tuple(self._samples)
