# 투명도형 퍼즐 배경 데칼 신분 feature를 계산한다.
from __future__ import annotations

import math
from typing import Sequence


Point = tuple[float, float]
Candidate = tuple[float, float, float, float, float]


def background_identity_penalties(background_ids: Sequence[int | None]) -> tuple[float, ...]:
    return tuple(0.0 if bg_id is None else 1.0 for bg_id in background_ids)


def split_recovery_supports(
    candidates: Sequence[Candidate],
    *,
    predicted: Point,
    background_penalties: Sequence[float],
    gate: float = 40.0,
) -> tuple[float, ...]:
    if not candidates:
        return ()
    scores = []
    for index, candidate in enumerate(candidates):
        bg = float(background_penalties[index]) if index < len(background_penalties) else 0.0
        if bg >= 1.0:
            scores.append(0.0)
            continue
        distance = _dist((candidate[0], candidate[1]), predicted)
        if distance > float(gate):
            scores.append(0.0)
            continue
        scores.append(max(0.0, 1.0 - distance / max(float(gate), 1e-6)))
    return _rank_positive(scores)


def _rank_positive(values: Sequence[float]) -> tuple[float, ...]:
    positives = [float(value) for value in values if float(value) > 0.0]
    if not positives:
        return tuple(0.0 for _value in values)
    lo = min(positives)
    hi = max(positives)
    if hi - lo <= 1e-9:
        return tuple(1.0 if float(value) > 0.0 else 0.0 for value in values)
    return tuple(
        0.0 if float(value) <= 0.0 else round((float(value) - lo) / (hi - lo), 6)
        for value in values
    )


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
