# 입력 시간 랜덤 보정이 지정 범위와 정밀도를 지키는지 검증합니다.
import importlib

import pytest


class FixedRng:
    def __init__(self, result: float):
        self.result = result
        self.bounds = None

    def uniform(self, low: float, high: float) -> float:
        self.bounds = (low, high)
        return self.result


def test_randomize_hold_uses_95_to_100_percent_once():
    try:
        timing = importlib.import_module("core.input_timing")
    except ModuleNotFoundError:
        pytest.fail("core.input_timing 모듈이 아직 없습니다")

    rng = FixedRng(0.97321)
    result = timing.randomize_hold(0.3, rng)

    assert rng.bounds == (0.95, 1.0)
    assert result == 0.292


def test_randomize_interval_uses_95_to_105_percent_once():
    timing = importlib.import_module("core.input_timing")
    rng = FixedRng(1.03456)

    result = timing.randomize_interval(0.3, rng)

    assert rng.bounds == (0.95, 1.05)
    assert result == 0.3104
