# 왕복 끝점 랜덤마진(소수점4자리, 구간 이탈 없음) + 도착 시 방향키 해제 검증
import random

from core.navigation.block import Block
from core.navigation.block_runner import BlockRunner


class _H:
    """_sweep_targets/_exec_move에 필요한 최소 humanizer 더블."""
    def __init__(self):
        self.releases = 0
        self._held = None
    def rand_in(self, lo, hi, ndigits=4):
        if hi <= lo:
            return round(float(lo), ndigits)
        return round(random.uniform(lo, hi), ndigits)
    def hold_dir(self, key, risk_profile=None): self._held = key
    def release_dir(self):
        if self._held is not None:
            self.releases += 1; self._held = None
    def jitter_sec(self, base, spread=None): return base


def test_sweep_margin_random_within_range_4decimals():
    r = BlockRunner(humanizer=_H(), pos_fn=lambda: (0, 0))
    for _ in range(100):
        end_t, start_t = r._sweep_targets(1, 10, 1)   # 구간[1,10], 마진1
        assert 9 <= end_t <= 10        # 끝쪽 턴 ∈ [end-margin, end]
        assert 1 <= start_t <= 2       # 시작쪽 턴 ∈ [start, start+margin]
        assert 1 <= start_t <= 10 and 1 <= end_t <= 10   # 구간 이탈 없음
        assert round(end_t, 4) == end_t and round(start_t, 4) == start_t


def test_sweep_margin_zero_is_exact_endpoints():
    r = BlockRunner(humanizer=_H(), pos_fn=lambda: (0, 0))
    assert r._sweep_targets(1, 10, 0) == (10.0, 1.0)   # 마진0 → 정확 끝점(기존 동작)


def test_exec_move_releases_dir_on_arrival():
    h = _H()
    # 위치가 목표(=50)에 이미 도달 → 즉시 도착 → 방향키 해제
    r = BlockRunner(humanizer=h, pos_fn=lambda: (50, 0), sleep_fn=lambda s: None)
    h._held = "right"
    ok = r.run_block(Block(type="move", target_x=50, move_type="walk"), max_steps=5)
    assert ok is True
    assert h.releases >= 1 and h._held is None   # 도착 시 정지(키 떼짐)
