# 상위 기능이 키 홀드와 시간 간격의 원래 설정값을 물리 입력 경계에 전달하는지 검증한다.
from types import SimpleNamespace

import pytest

from core.acting.attack_sequence import AttackSequence, AttackSequenceRunner
from core.acting.buff import Buff, BuffManager
from core.acting.charlie import CharlieExchange
from core.acting.combat import Combat, PotionRule
from core.acting.pet import PetFeeder
from core.navigation.rednose3_runner import RedNose3RouteRunner
from core.navigation.world_runner import ActionExecutor
from core.potion_manager import PotionManager
from core.map_navigator import MapNavigator
from core.key_hunter import KeyHunter
from core.navigation.route_state import RouteStepType
from core.navigation.route_state_runner import RouteStateRunner
from core.pattern import ACTION_HOLD


class RecordingBackend:
    def __init__(self):
        self.presses = []

    def press(self, key, hold_sec=0.05):
        self.presses.append((key, hold_sec))

    def press_action(self, key, hold_sec=0.05):
        self.press(key, hold_sec)


def test_combat_passes_raw_holds_and_randomizes_attack_interval_once(monkeypatch):
    backend = RecordingBackend()
    monkeypatch.setattr("core.acting.combat.randomize_interval", lambda value: value * 1.05, raising=False)
    combat = Combat(
        backend,
        hp_rule=PotionRule(enabled=True, key="9", threshold=0.7, cooldown=2.0),
    )

    combat.attack("end", now=10.0, interval=0.4, hold=0.9)
    combat.check_potions(hp_ratio=0.5, mp_ratio=1.0, now=10.0)

    assert backend.presses == [("end", 0.9), ("9", 0.05)]
    assert combat._cur_interval == pytest.approx(0.42)
    assert combat._potion_next_allowed["HP"] == 12.0


def test_buff_and_pet_pass_raw_holds_and_randomize_schedules_once(monkeypatch):
    backend = RecordingBackend()
    sleeps = []
    monkeypatch.setattr("core.acting.buff.randomize_interval", lambda value: value * 1.05, raising=False)
    monkeypatch.setattr("core.acting.pet.randomize_interval", lambda value: value * 1.05, raising=False)

    buffs = BuffManager(backend, [Buff(key="f", interval=100.0, hold_sec=0.8)], gap=2.5)
    buffs.tick(1000.0)
    pet = PetFeeder(backend, key="=", interval=600.0, count=2, gap=0.4, sleep_fn=sleeps.append)
    pet.tick(1000.0)

    assert backend.presses == [("f", 0.8), ("=", 0.05), ("=", 0.05)]
    assert buffs._iv[0] == 105.0
    assert buffs._next_allowed == 1002.625
    assert pet._iv == 630.0
    assert sleeps == [pytest.approx(0.42)]


def test_charlie_passes_raw_holds_and_keeps_fixed_waits(monkeypatch):
    backend = RecordingBackend()
    sleeps = []
    exchange = CharlieExchange(backend, sleep_fn=sleeps.append)

    exchange._npc_talk()
    exchange._direction("down")

    assert backend.presses == [("u", 0.05), ("down", 0.05)]
    assert sleeps == [0.5, 0.1]


def test_attack_sequence_randomizes_key_and_repeat_intervals_once(monkeypatch):
    presses = []
    monkeypatch.setattr("core.acting.attack_sequence.randomize_interval", lambda value: value * 1.05, raising=False)
    runner = AttackSequenceRunner(
        [AttackSequence("연속기", ("a", "b"), (0.1, 0.2), 0.3, 1.0)],
        lambda key, hold: presses.append((key, hold)),
    )

    runner.tick(10.0, True)

    assert presses == [("a", 0.1)]
    assert runner._states[0]["next_run"] == 11.05
    assert runner._states[0]["next_key"] == 10.315


def test_world_action_passes_raw_hold():
    backend = RecordingBackend()
    executor = ActionExecutor(backend, sleep_fn=lambda value: None)
    spec = SimpleNamespace(
        repeat=1,
        action_type="key",
        key="home",
        hold_sec=0.7,
        repeat_interval_sec=0.0,
        wait_after_sec=0.0,
    )

    executor.execute(spec)

    assert backend.presses == [("home", 0.7)]


def test_rednose3_passes_raw_attack_hold_and_keeps_fixed_gap(monkeypatch):
    backend = RecordingBackend()
    sleeps = []
    block_runner = SimpleNamespace(_route_inputs=backend)
    runner = RedNose3RouteRunner(
        block_runner,
        is_active=lambda: True,
        profile={"attack_key": "end", "attack_hold_sec": 0.9, "attack_gap_sec": 0.05},
        sleep_fn=sleeps.append,
    )
    runner._tap_attack(2)

    assert backend.presses == [("end", 0.9), ("end", 0.9)]
    assert sleeps == [0.05]


def test_potion_manager_passes_configured_raw_hold():
    class InputController:
        def __init__(self):
            self.presses = []

        def press_key(self, key, hold_sec=0.05):
            self.presses.append((key, hold_sec))

    detector = SimpleNamespace(hp_ratio=lambda: 0.2, mp_ratio=lambda: 1.0)
    input_controller = InputController()
    manager = PotionManager(input_controller, detector)
    manager.set_config(
        {"enabled": True, "threshold": 70, "cooldown_sec": 0.0, "key": "9", "hold_sec": 0.11},
        {"enabled": False},
    )

    manager.check_and_use()

    assert input_controller.presses == [("9", 0.11)]


def test_map_navigator_passes_fixed_nominal_attack_holds():
    backend = SimpleNamespace(presses=[])
    backend.press_key = lambda key, hold_sec=0.05: backend.presses.append((key, hold_sec))
    navigator = MapNavigator.__new__(MapNavigator)
    navigator._input = backend
    navigator._jump_before_attack = True
    navigator._attack_key = "end"

    navigator._do_attack()

    assert backend.presses == [("space", 0.0533), ("end", 0.0533)]


def test_key_hunter_manual_hold_randomizes_once(monkeypatch):
    events = []
    hunter = KeyHunter.__new__(KeyHunter)
    hunter._input = SimpleNamespace(
        key_down=lambda key: events.append(("down", key)),
        key_up=lambda key: events.append(("up", key)),
    )
    hunter._sleep_with_move = lambda duration: events.append(("sleep", duration))
    hunter._status = lambda message: None
    step = SimpleNamespace(action=ACTION_HOLD, key="ctrl", min_sec=1.0, max_sec=1.0)
    monkeypatch.setattr("core.key_hunter.random.uniform", lambda low, high: 1.0)
    monkeypatch.setattr("core.key_hunter.randomize_hold", lambda value: 0.95)

    hunter._execute(step)

    assert events == [("down", "ctrl"), ("sleep", 0.95), ("up", "ctrl")]


def test_route_state_manual_action_randomizes_hold_once(monkeypatch):
    events = []
    input_owner = SimpleNamespace(
        hold_action=lambda key: events.append(("down", key)),
        release_action=lambda key: events.append(("up", key)),
    )
    runner = RouteStateRunner.__new__(RouteStateRunner)
    runner._input = input_owner
    step = SimpleNamespace(
        type=RouteStepType.ACTION,
        parameters={"skill_key": "home", "hold_sec": 0.1},
    )
    monkeypatch.setattr("core.navigation.route_state_runner.randomize_hold", lambda value: 0.095)
    monkeypatch.setattr("core.navigation.route_state_runner.time.sleep", lambda value: events.append(("sleep", value)))

    assert runner._execute(step, [step])
    assert events == [("down", "home"), ("sleep", 0.095), ("up", "home")]
