# 입력 시간값에 명시적인 5% 랜덤을 한 번만 적용하는 계산 모듈
from __future__ import annotations

import random


def plus_minus_5(value: float, rng: random.Random | None = None) -> float:
    """기준값의 95~105%를 소수점 넷째 자리까지 반환한다."""
    value = max(0.0, float(value))
    source = rng or random
    return round(value * source.uniform(0.95, 1.05), 4)


def down_5(value: float, rng: random.Random | None = None) -> float:
    """기준값을 넘지 않는 95~100% 값을 소수점 넷째 자리까지 반환한다."""
    value = max(0.0, float(value))
    source = rng or random
    return round(value * source.uniform(0.95, 1.0), 4)
