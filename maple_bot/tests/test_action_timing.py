# 공격 쿨다운(스킬 딜레이)·펫 마리수만큼 나눠 누르기 검증
from core.acting.combat import Combat
from core.acting.pet import PetFeeder


class _H:
    def __init__(self): self.presses = 0; self.sleeps = []
    def perform(self, intent): self.presses += 1
    def sleep_jittered(self, base, spread=None): self.sleeps.append(base)


def test_attack_interval_gates_spam():
    h = _H()
    c = Combat(h)
    c.attack("ctrl", now=0.0, interval=0.4)     # 발동
    c.attack("ctrl", now=0.2, interval=0.4)     # 0.4s 전 → 무시
    c.attack("ctrl", now=0.45, interval=0.4)    # 경과 → 발동
    assert h.presses == 2                       # 도배 방지(2회만)


def test_attack_no_interval_always_fires():
    h = _H()
    c = Combat(h)
    c.attack("ctrl"); c.attack("ctrl")          # interval=0 → 매번 발동(기존)
    assert h.presses == 2


def test_pet_presses_per_count_with_gap():
    h = _H()
    p = PetFeeder(h, key="=", interval=10, count=3, gap=0.4)
    p.tick(now=100.0)
    assert h.presses == 3            # 3마리 → 3번 누름
    assert h.sleeps == [0.4, 0.4]    # 사이 텀 2번(누름 사이)
