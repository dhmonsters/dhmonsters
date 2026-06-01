# SharedState — 스레드 안전 공유 상태. 스캐너(쓰기) ↔ 행동/동선(읽기) 사이 위치 폐루프 매개
from __future__ import annotations

import threading
import time


class SharedState:
    """캐릭터 위치/HP/MP 등 모듈 간 공유되는 런타임 상태.

    CharScanner 가 위치를 갱신하고 BlockRunner 가 읽는다(도면 5-4 위치 폐루프).
    모든 접근은 락으로 보호 — 찢어진 읽기 방지.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._pos: tuple[int, int] | None = None
        self._pos_ts: float = 0.0
        self._hp: float = 1.0
        self._mp: float = 1.0

    # ── 위치 ──────────────────────────────────────────────────────────
    def set_position(self, x: int, y: int, now: float | None = None) -> None:
        with self._lock:
            self._pos = (x, y)
            self._pos_ts = now if now is not None else time.time()

    def get_position(self) -> tuple[int, int] | None:
        with self._lock:
            return self._pos

    def position_age(self, now: float | None = None) -> float:
        """마지막 위치 갱신 이후 경과 시간(초). 위치 없으면 무한대."""
        with self._lock:
            if self._pos is None:
                return float("inf")
            return (now if now is not None else time.time()) - self._pos_ts

    # ── HP/MP ─────────────────────────────────────────────────────────
    def set_hp_ratio(self, r: float) -> None:
        with self._lock:
            self._hp = r

    def set_mp_ratio(self, r: float) -> None:
        with self._lock:
            self._mp = r

    def get_hp_ratio(self) -> float:
        with self._lock:
            return self._hp

    def get_mp_ratio(self) -> float:
        with self._lock:
            return self._mp
