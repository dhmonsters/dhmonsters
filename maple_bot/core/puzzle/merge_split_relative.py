# 병합된 투명도형의 배경 상대 좌표와 분리 신분을 복원합니다.
from __future__ import annotations

from dataclasses import dataclass
from math import hypot


Point = tuple[float, float]


@dataclass(frozen=True)
class RelativeCoordinate:
    u: float
    v: float


def relative_coordinate(
    point: Point,
    anchor_a: Point,
    anchor_b: Point,
) -> RelativeCoordinate | None:
    dx = anchor_b[0] - anchor_a[0]
    dy = anchor_b[1] - anchor_a[1]
    length = hypot(dx, dy)
    if length <= 1e-6:
        return None

    px = point[0] - anchor_a[0]
    py = point[1] - anchor_a[1]
    denominator = length * length
    return RelativeCoordinate(
        u=(px * dx + py * dy) / denominator,
        v=(dx * py - dy * px) / denominator,
    )
