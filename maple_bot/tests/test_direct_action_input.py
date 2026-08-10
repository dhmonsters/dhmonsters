# Humanizer 없이 행동 기능이 입력 백엔드를 직접 사용하는지 검증합니다.
from core.acting.buff import Buff, BuffManager
from core.acting.charlie import CharlieExchange
from core.acting.combat import Combat
from core.acting.pet import PetFeeder


class RecordingBackend:
    def __init__(self):
        self.presses = []

    def press(self, key, hold_sec=0.05):
        self.presses.append((key, hold_sec))


def test_combat_uses_backend_without_humanizer():
    backend = RecordingBackend()
    combat = Combat(input_backend=backend)

    combat.attack("end", hold=0.9)

    assert backend.presses[0][0] == "end"
    assert 0.855 <= backend.presses[0][1] <= 0.9
    assert not hasattr(combat, "_h")


def test_buff_manager_uses_backend_without_humanizer(monkeypatch):
    backend = RecordingBackend()
    monkeypatch.setattr("core.acting.buff.plus_minus_5", lambda value: value)
    manager = BuffManager(input_backend=backend, buffs=[Buff(key="f", interval=200, hold_sec=0.8)])

    manager.tick(100.0)

    assert backend.presses == [("f", 0.8)]
    assert not hasattr(manager, "_h")


def test_pet_feeder_uses_backend_and_only_feature_gap(monkeypatch):
    backend = RecordingBackend()
    sleeps = []
    monkeypatch.setattr("core.acting.pet.plus_minus_5", lambda value: value)
    feeder = PetFeeder(
        input_backend=backend,
        key="=",
        interval=600,
        count=3,
        gap=0.4,
        sleep_fn=sleeps.append,
    )

    feeder.tick(1000.0)

    assert backend.presses == [("=", 0.05)] * 3
    assert sleeps == [0.4, 0.4]
    assert not hasattr(feeder, "_h")


def test_charlie_exchange_uses_backend_without_humanizer(monkeypatch):
    backend = RecordingBackend()
    sleeps = []
    monkeypatch.setattr("core.acting.charlie.plus_minus_5", lambda value: value)
    exchange = CharlieExchange(input_backend=backend, npc_key="u", sleep_fn=sleeps.append)

    exchange.run_one_routine()

    keys = [key for key, _ in backend.presses]
    assert keys.count("down") == 15
    assert keys.count("left") == 1
    assert keys.count("u") >= 4
    assert not hasattr(exchange, "_h")
