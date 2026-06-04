# 사냥영역 몹 밀집도로 '멈춰 사냥(DWELL) ↔ 이동(MOVING)'을 결정하는 상태기계 — 시간당 처치 최적화
from __future__ import annotations


class HuntDirector:
    """몹 개수로 체류/이동 결정. 히스테리시스(진입≥stay, 이탈≤leave) + 최대 체류 타임아웃.

    1마리뿐인 자리에서 멈춰 시간을 낭비하지 않도록, 밀집(≥stay)일 때만 멈춰 처치하고
    개수가 leave 이하로 줄거나 max_dwell_sec를 넘으면 다시 이동한다."""

    def __init__(self, stay_threshold: int = 3, leave_threshold: int = 1,
                 max_dwell_sec: float = 8.0):
        self._stay = max(1, int(stay_threshold))
        self._leave = max(0, int(leave_threshold))
        self._max_dwell = max(0.0, float(max_dwell_sec))
        self._dwelling = False
        self._dwell_start = 0.0

    def update(self, count: int, now: float) -> bool:
        """현재 몹 개수로 상태 갱신 후 '지금 DWELL(멈춰 사냥)인가' 반환."""
        if self._dwelling:
            if count <= self._leave or (now - self._dwell_start) >= self._max_dwell:
                self._dwelling = False
        else:
            if count >= self._stay:
                self._dwelling = True
                self._dwell_start = now
        return self._dwelling

    def is_dwelling(self) -> bool:
        return self._dwelling
