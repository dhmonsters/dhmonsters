# BuffManager — 주기 버프 자동 사용(일반/토글). 모션캔슬 대기 포함. Humanizer 경유
from __future__ import annotations

from dataclasses import dataclass

from core.humanize.intent import Intent


@dataclass
class Buff:
    """버프 1개 설정."""
    key: str = ""
    interval: float = 60.0     # 재사용 주기(초)
    hold_sec: float = 0.8      # A: 버프는 길게 눌러 캔슬 방지


class BuffManager:
    """주기마다 버프 키를 사용한다.

    A 방식: hold 0.8s로 길게 + 다음 버프와의 모션 캔슬 방지.
    각 버프는 interval 에 ±지터(Humanizer 위임)로 비주기성 확보.
    """

    def __init__(self, humanizer, buffs: list[Buff]):
        self._h = humanizer
        self._buffs = buffs
        self._last: dict[int, float] = {}   # buff index → 마지막 사용 시각

    def tick(self, now: float) -> None:
        """주기 경과한 버프를 사용."""
        for i, b in enumerate(self._buffs):
            if not b.key:
                continue   # 키 미설정 = 비활성
            last = self._last.get(i, -1e9)
            if now - last >= b.interval:
                self._h.perform(Intent(action="key", key=b.key, base_hold_sec=b.hold_sec))
                self._last[i] = now
