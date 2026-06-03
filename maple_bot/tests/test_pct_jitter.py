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


def test_jitter_down_never_exceeds_base():
    h = Humanizer(backend=_Backend(), sleep_fn=lambda s: None)
    for _ in range(300):
        v = h.jitter_down(200.0, 0.05)      # 200초면 190~200만(초과 X)
        assert 190.0 <= v <= 200.0 and round(v, 4) == v


def test_hold_jitter_pct_one_sided_down():
    b = _Backend()
    h = Humanizer(backend=b, sleep_fn=lambda s: None)
    for _ in range(50):
        h.perform(Intent(action="key", key="f", base_hold_sec=0.8, hold_jitter_pct=0.05))
    assert all(0.76 <= x <= 0.80 for x in b.holds)   # 0.8 초과 안 함


def test_buff_interval_down_only():
    h = Humanizer(backend=_Backend(), sleep_fn=lambda s: None, rng=random.Random(1))
    bm = BuffManager(h, [Buff(key="f", interval=100)], jitter=0.05)
    bm.tick(now=1000.0)
    assert 95.0 <= bm._iv[0] <= 100.0   # 100 초과 안 함


def test_pet_interval_down_only():
    h = Humanizer(backend=_Backend(), sleep_fn=lambda s: None, rng=random.Random(2))
    p = PetFeeder(h, key="=", interval=600, jitter=0.05)
    p.tick(now=1000.0)
    assert 570.0 <= p._iv <= 600.0      # 600 초과 안 함
