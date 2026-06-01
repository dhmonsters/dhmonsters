# Patrol — 구역 내 좌우 왕복 순찰 방향 결정. A map_navigator._update_direction/_pick_target 재현
# 경계에 딱 붙지 않고 랜덤 마진 안쪽에서 전환 → 사람같은 왕복(매번 다른 반환점)
from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class PatrolZone:
    """순찰 구역 — 미니맵 X 좌우 경계."""
    left_x: int
    right_x: int


class Patrol:
    """구역 내 좌우 왕복. 현재 X를 받아 다음 이동 방향을 결정한다."""

    def __init__(self, zone: PatrolZone, start_dir: str = "right",
                 margin: int = 0, rng_seed: int | None = None):
        self._z = zone
        self._dir = start_dir
        self._margin = max(0, margin)
        self._rng = random.Random(rng_seed)
        self._right_target = self._pick_right()
        self._left_target = self._pick_left()

    def _pick_right(self) -> int:
        """우측 전환 목표: (right_x - margin) ~ right_x 랜덤."""
        lo = max(self._z.left_x + 1, self._z.right_x - self._margin)
        return self._rng.randint(lo, self._z.right_x) if lo < self._z.right_x else self._z.right_x

    def _pick_left(self) -> int:
        """좌측 전환 목표: left_x ~ (left_x + margin) 랜덤."""
        hi = min(self._z.right_x - 1, self._z.left_x + self._margin)
        return self._rng.randint(self._z.left_x, hi) if self._z.left_x < hi else self._z.left_x

    def next_direction(self, x: int) -> str:
        """현재 X 기준 이동 방향. 경계(목표) 도달 시 전환하고 다음 목표 재추첨."""
        if self._dir == "right" and x >= self._right_target:
            self._dir = "left"
            self._left_target = self._pick_left()
        elif self._dir == "left" and x <= self._left_target:
            self._dir = "right"
            self._right_target = self._pick_right()
        return self._dir

    def target_x(self) -> int:
        """현재 방향의 목표 X (BlockRunner move 블록용)."""
        return self._right_target if self._dir == "right" else self._left_target

    @property
    def direction(self) -> str:
        return self._dir
