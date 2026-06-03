# 버프/펫 ±5% 소수점4자리 랜덤(간격·홀드) 검증
import random

from core.humanize.humanizer import Humanizer
from core.humanize.intent import Intent
from core.acting.buff import BuffManager, Buff
from core.acting.pet import PetFeeder


class _Backend:
    def __init__(self): self.holds = []
    def key_down(self, k): pass
    def key_up(self, k): pass
    def press(self, k, hold): self.holds.append(hold)


def test_jitter_pct_within_5pct_4decimals():
    h = Humanizer(backend=_Backend(), sleep_fn=lambda s: None)
    for _ in range(200):
        v = h.jitter_pct(100.0, 0.05)
        assert 95.0 <= v <= 105.0 and round(v, 4) == v


def test_hold_jitter_pct_tight():
    b = _Backend()
    h = Humanizer(backend=b, sleep_fn=lambda s: None)
    for _ in range(50):
        h.perform(Intent(action="key", key="f", base_hold_sec=0.8, hold_jitter_pct=0.05))
    assert all(0.76 <= x <= 0.84 for x in b.holds)   # 0.8 ±5%


def test_buff_interval_randomized_per_cycle():
    h = Humanizer(backend=_Backend(), sleep_fn=lambda s: None, rng=random.Random(1))
    bm = BuffManager(h, [Buff(key="f", interval=100)], jitter=0.05)
    bm.tick(now=1000.0)                 # 발동 → 다음 주기 ±5% 저장
    assert 95.0 <= bm._iv[0] <= 105.0   # 100 ±5%


def test_pet_interval_randomized():
    h = Humanizer(backend=_Backend(), sleep_fn=lambda s: None, rng=random.Random(2))
    p = PetFeeder(h, key="=", interval=600, jitter=0.05)
    p.tick(now=1000.0)
    assert 570.0 <= p._iv <= 630.0      # 600 ±5%
