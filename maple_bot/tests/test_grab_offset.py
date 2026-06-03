# 밧줄 점프 접근거리 ±10% 랜덤(소수점4자리) 검증
import random

from core.navigation.block_runner import BlockRunner


class _H:
    def rand_in(self, lo, hi, ndigits=4):
        if hi <= lo:
            return round(float(lo), ndigits)
        return round(random.uniform(lo, hi), ndigits)


def test_grab_offset_within_10pct_4decimals():
    r = BlockRunner(humanizer=_H(), pos_fn=lambda: (0, 0))
    for _ in range(100):
        o = r._grab_offset(5)            # 기준 5px
        assert 4.5 <= o <= 5.5           # ±10%
        assert round(o, 4) == o          # 소수점 4자리
    for _ in range(100):
        o = r._grab_offset(8)
        assert 7.2 <= o <= 8.8


def test_grab_offset_zero_is_zero():
    r = BlockRunner(humanizer=_H(), pos_fn=lambda: (0, 0))
    assert r._grab_offset(0) == 0.0      # 0이면 사다리 X에서 점프
