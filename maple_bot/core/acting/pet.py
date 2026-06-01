# PetFeeder — 주기마다 펫 먹이 키 입력. Humanizer 경유 (BuffManager와 동일 패턴)
from __future__ import annotations

from core.humanize.intent import Intent


class PetFeeder:
    """주기 펫 먹이. key 없으면 비활성."""

    def __init__(self, humanizer, key: str = "", interval: float = 600.0):
        self._h = humanizer
        self._key = key
        self._interval = interval
        self._last = -1e9

    def tick(self, now: float) -> None:
        if not self._key:
            return
        if now - self._last >= self._interval:
            self._h.perform(Intent(action="key", key=self._key, base_hold_sec=0.05))
            self._last = now
