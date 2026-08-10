# FloorJudge — 미니맵 Y좌표로 현재 층 판별 + 도착확인 폐루프
# A의 "CLIMB_DURATION 2초 무조건 등반 → 미도착인데 도착판정" 문제를 Y 기반 폐루프로 해결
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Floor:
    """층 정의 — 미니맵 Y 범위."""
    name: str
    y_min: int
    y_max: int


class FloorJudge:
    """Y좌표로 층을 판별하고, 목표 층 도착 여부를 확인한다."""

    def __init__(self, floors: list[Floor], tolerance: int = 3):
        self._floors = floors
        self._tol = tolerance

    def floor_at(self, y: int) -> Floor | None:
        """현재 Y가 속한 층. 층 사이(밧줄 중간)면 None."""
        # 층이 하나만 설정된 맵은 다층 판정이 필요 없으므로 해당 층을 사용한다.
        if len(self._floors) == 1:
            return self._floors[0]
        for f in self._floors:
            if f.y_min <= y <= f.y_max:
                return f
        return None

    def is_arrived(self, target_floor: Floor, y: int) -> bool:
        """목표 층 범위(±tolerance) 안에 실제로 들어왔는지.

        타이머가 아니라 Y 위치로 판정 → 밧줄 중간에서 도착 오판정 안 함.
        """
        return (target_floor.y_min - self._tol) <= y <= (target_floor.y_max + self._tol)
