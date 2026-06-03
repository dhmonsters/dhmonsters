# PetFeeder — 주기마다 펫 먹이 키 입력. Humanizer 경유 (BuffManager와 동일 패턴)
from __future__ import annotations

from core.humanize.intent import Intent


class PetFeeder:
    """주기 펫 먹이. key 없으면 비활성."""

    def __init__(self, humanizer, key: str = "", interval: float = 600.0,
                 log_fn=None, label: str = "펫 먹이", count: int = 1, gap: float = 0.4):
        self._h = humanizer
        self._key = key
        self._interval = interval
        self._last = -1e9
        self._log = log_fn or (lambda msg: None)
        self._label = label
        self._count = max(1, int(count))   # 펫 마리수만큼 나눠 누름
        self._gap = gap                    # 펫 사이 텀(빠르게 연타하면 다 안 먹음)

    def tick(self, now: float) -> None:
        if not self._key:
            return
        if now - self._last >= self._interval:
            for n in range(self._count):
                self._h.perform(Intent(action="key", key=self._key, base_hold_sec=0.05))
                if n < self._count - 1:
                    self._h.sleep_jittered(self._gap)   # 마리 사이 텀
            self._last = now
            self._log(f"{self._label}{('×' + str(self._count)) if self._count > 1 else ''} [{self._key}]")
