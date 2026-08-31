# 공격과 HP·MP 물약의 입력 조건과 간격을 검증합니다.
import pytest

from core.acting.combat import Combat, PotionRule


class RecordingBackend:
    def __init__(self):
        self.presses = []

    def press(self, key, hold_sec=0.05):
        self.presses.append((key, hold_sec))


def test_potion_used_only_below_threshold():
    backend = RecordingBackend()
    combat = Combat(backend, hp_rule=PotionRule(enabled=True, key="9", threshold=0.7, cooldown=0))

    combat.check_potions(0.9, 1.0, 9.0)
    combat.check_potions(0.5, 1.0, 10.0)

    assert backend.presses == [("9", 0.05)]


def test_attack_count_and_hold_are_forwarded_to_backend():
    backend = RecordingBackend()
    combat = Combat(backend)

    combat.attack("a", mode="count", value=3, hold=0.25)

    assert backend.presses == [("a", 0.25)] * 3


def test_attack_interval_is_randomized_once(monkeypatch):
    backend = RecordingBackend()
    monkeypatch.setattr("core.acting.combat.randomize_interval", lambda value: value * 0.95)
    combat = Combat(backend)

    combat.attack("a", now=0.0, interval=0.4)
    combat.attack("a", now=0.37, interval=0.4)
    combat.attack("a", now=0.38, interval=0.4)

    assert len(backend.presses) == 2
    assert combat._cur_interval == pytest.approx(0.38)


def test_secondary_potion_fires_after_failed_recovery():
    backend = RecordingBackend()
    rule = PotionRule(
        enabled=True,
        key="9",
        secondary_key="8",
        threshold=0.7,
        cooldown=4.0,
        verify_delay=0.2,
        min_recovery=0.01,
    )
    combat = Combat(backend, hp_rule=rule)

    combat.check_potions(0.50, 1.0, 10.0)
    combat.check_potions(0.505, 1.0, 10.19)
    combat.check_potions(0.505, 1.0, 10.2)

    assert backend.presses == [("9", 0.05), ("8", 0.05)]


def test_hp_and_mp_potions_are_independent():
    backend = RecordingBackend()
    combat = Combat(
        backend,
        hp_rule=PotionRule(enabled=True, key="9", threshold=0.5, cooldown=0),
        mp_rule=PotionRule(enabled=True, key="0", threshold=0.5, cooldown=0),
    )

    combat.check_potions(0.9, 0.3, 10.0)

    assert backend.presses == [("0", 0.05)]
