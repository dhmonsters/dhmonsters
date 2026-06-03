# 공격/물약/버프/펫 동작이 카테고리 로그를 내는지 검증
from core.acting.combat import Combat, PotionRule
from core.acting.buff import BuffManager, Buff
from core.acting.pet import PetFeeder


class _H:
    def perform(self, intent): pass


def test_combat_attack_logs_throttled():
    logs = []
    clk = {"t": 100.0}
    c = Combat(_H(), log_fn=lambda m, cat: logs.append((cat, m)), clock=lambda: clk["t"])
    c.attack("ctrl")                       # 첫 공격 → 로그
    c.attack("ctrl")                       # 같은 1초 내 → 로그 안 함(스로틀)
    assert logs == [("공격", "공격 [ctrl]")]
    clk["t"] += 1.1
    c.attack("ctrl")                       # 1초 경과 → 다시 로그
    assert logs.count(("공격", "공격 [ctrl]")) == 2


def test_combat_potion_logs():
    logs = []
    c = Combat(_H(), hp_rule=PotionRule(enabled=True, key="9", threshold=0.7, cooldown=0),
               log_fn=lambda m, cat: logs.append((cat, m)))
    c.check_potions(hp_ratio=0.5, mp_ratio=1.0, now=1.0)   # HP 50%<70% → 물약
    assert any(cat == "물약" and "9" in m for cat, m in logs)


def test_buff_logs():
    logs = []
    bm = BuffManager(_H(), [Buff(key="F1", interval=10)], log_fn=lambda m: logs.append(m))
    bm.tick(now=100.0)
    assert any("F1" in m for m in logs)


def test_pet_logs():
    logs = []
    p = PetFeeder(_H(), key="L", interval=10, log_fn=lambda m: logs.append(m), label="줍기")
    p.tick(now=100.0)
    assert any("줍기" in m and "L" in m for m in logs)
