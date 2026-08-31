# 키 입력과 실행 간격의 시간 랜덤 보정을 제공합니다.
from __future__ import annotations

import random


def randomize_hold(value: float, rng: random.Random | None = None) -> float:
    """기준값을 넘지 않는 95~100% 값을 소수점 넷째 자리까지 반환합니다."""
    value = max(0.0, float(value))
    source = rng or random
    return round(value * source.uniform(0.95, 1.0), 4)


def randomize_interval(value: float, rng: random.Random | None = None) -> float:
    """기준값의 95~105%를 소수점 넷째 자리까지 반환합니다."""
    value = max(0.0, float(value))
    source = rng or random
    return round(value * source.uniform(0.95, 1.05), 4)
