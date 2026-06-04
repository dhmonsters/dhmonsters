# Combat — 게이지 물약(A방식) + 공격. 모든 입력 Humanizer 경유 검증
import pytest
from core.acting.combat import Combat, PotionRule
from core.humanize.intent import Intent


class FakeHumanizer:
    def __init__(self): self.intents = []
    def perform(self, i): self.intents.append(i)
    def jitter_down(self, base, pct=0.05, ndigits=4):
        return round(base * (1 - pct), ndigits)   # 결정적: 항상 −pct (테스트 안정)


def test_potion_used_when_below_threshold():
    """HP 비율이 임계 미만이면 물약 키 입력(A 게이지 방식)."""
    h = FakeHumanizer()
    c = Combat(humanizer=h, hp_rule=PotionRule(enabled=True, key="9", threshold=0.7, cooldown=0))
    c.check_potions(hp_ratio=0.5, mp_ratio=1.0, now=10.0)
    assert any(i.key == "9" for i in h.intents)


def test_potion_not_used_above_threshold():
    h = FakeHumanizer()
    c = Combat(humanizer=h, hp_rule=PotionRule(enabled=True, key="9", threshold=0.7, cooldown=0))
    c.check_potions(hp_ratio=0.9, mp_ratio=1.0, now=10.0)
    assert not any(i.key == "9" for i in h.intents)


def test_potion_respects_cooldown():
    """쿨다운 중엔 재사용 안 함."""
    h = FakeHumanizer()
    c = Combat(humanizer=h, hp_rule=PotionRule(enabled=True, key="9", threshold=0.7, cooldown=3.0))
    c.check_potions(hp_ratio=0.5, mp_ratio=1.0, now=10.0)   # 사용
    n1 = len(h.intents)
    c.check_potions(hp_ratio=0.5, mp_ratio=1.0, now=11.0)   # 쿨다운 중
    assert len(h.intents) == n1
    c.check_potions(hp_ratio=0.5, mp_ratio=1.0, now=14.0)   # 쿨다운 해제
    assert len(h.intents) > n1


def test_attack_count_mode():
    """count 모드: 지정 횟수만큼 공격 키."""
    h = FakeHumanizer()
    c = Combat(humanizer=h)
    c.attack(skill_key="a", mode="count", value=3)
    assert sum(1 for i in h.intents if i.key == "a") == 3


def test_attack_hold_is_configurable():
    """공격키 홀드 시간(hold)이 Intent.base_hold_sec로 전달된다(설정 조정 가능)."""
    h = FakeHumanizer()
    c = Combat(humanizer=h)
    c.attack(skill_key="a", hold=0.25, hold_jitter_pct=0.05)
    atk = [i for i in h.intents if i.key == "a"]
    assert atk and atk[-1].base_hold_sec == 0.25          # 홀드값 전달
    assert atk[-1].hold_jitter_pct == 0.05                # −5% 랜덤 플래그 전달


def test_repress_interval_jittered_down():
    """재누름 간격이 발동 시 −5%로 재추첨(설정값 초과 안 함) → 그만큼 일찍 다음 타격 허용."""
    h = FakeHumanizer()
    c = Combat(humanizer=h)
    c.attack(skill_key="a", now=0.0, interval=0.4)        # 발동 → cur_interval=0.38(−5%)
    n = len(h.intents)
    c.attack(skill_key="a", now=0.39, interval=0.4)       # 0.39 ≥ 0.38 → 발동(0.4면 막혔을 것)
    assert len(h.intents) == n + 1


def test_mp_potion_independent():
    """HP/MP 독립 — MP만 낮으면 MP 물약."""
    h = FakeHumanizer()
    c = Combat(humanizer=h,
               hp_rule=PotionRule(enabled=True, key="9", threshold=0.5, cooldown=0),
               mp_rule=PotionRule(enabled=True, key="0", threshold=0.5, cooldown=0))
    c.check_potions(hp_ratio=0.9, mp_ratio=0.3, now=10.0)
    assert any(i.key == "0" for i in h.intents)
    assert not any(i.key == "9" for i in h.intents)
