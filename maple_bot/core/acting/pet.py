# PetFeeder — 주기마다 펫 먹이 키 입력. Humanizer 경유 (BuffManager와 동일 패턴)
from __future__ import annotations

from core.humanize.intent import Intent


class PetFeeder:
    """주기 펫 먹이. key 없으면 비활성."""

    def __init__(self, humanizer, key: str = "", interval: float = 600.0,
                 log_fn=None, label: str = "펫 먹이", count: int = 1, gap: float = 0.4,
                 jitter: float = 0.05):
        self._h = humanizer
        self._key = key
        self._interval = interval
        self._last = -1e9
        self._iv = None                    # 이번 주기(±5% 적용). None이면 기본 interval
        self._log = log_fn or (lambda msg: None)
        self._label = label
        self._count = max(1, int(count))   # 펫 마리수만큼 나눠 누름
        self._gap = gap                    # 펫 사이 텀(빠르게 연타하면 다 안 먹음)
        self._jit = jitter                 # 간격·홀드 ±비율 랜덤(소수점4자리)

    def _jp(self, base: float) -> float:
        f = getattr(self._h, "jitter_pct", None)
        return f(base, self._jit) if f else base

    def tick(self, now: float) -> None:
        if not self._key:
            return
        iv = self._iv if self._iv is not None else self._interval
        if now - self._last >= iv:
            for n in range(self._count):
                self._h.perform(Intent(action="key", key=self._key, base_hold_sec=0.05,
                                       hold_jitter_pct=self._jit))   # 누르는 시간 ±5%
                if n < self._count - 1:
                    self._h.sleep_jittered(self._jp(self._gap))   # 마리 사이 텀(±5%)
            self._last = now
            self._iv = self._jp(self._interval)   # 다음 먹이 간격 ±5%
            self._log(f"{self._label}{('×' + str(self._count)) if self._count > 1 else ''} [{self._key}]")
