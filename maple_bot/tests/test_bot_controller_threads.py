# 통합 봇 컨트롤러의 작업 스레드 생성과 반복 대기를 검증한다.
from types import SimpleNamespace
from copy import deepcopy

import run_integrated
from core.config_manager import DEFAULT_CONFIG


class _FakeThread:
    created = []

    def __init__(self, target, daemon, name):
        self.target = target
        self.daemon = daemon
        self.name = name
        self.started = False
        self.created.append(self)

    def start(self):
        self.started = True

    def is_alive(self):
        return self.started


class _FloorRunner:
    def __init__(self):
        self.started = False

    def start(self):
        self.started = True


class _Runtime:
    def __init__(self, floor_runner=None):
        self._cfg = SimpleNamespace(game_window_title="game", minimap_region=None, char_rgb=None)
        self.floor_hunt_runner = floor_runner
        self.started_scanners = False
        self.running = False

    def set_running(self, flag):
        self.running = flag

    def start_scanners(self):
        self.started_scanners = True

    def _resolve_region(self, region):
        return (0, 0, 172, 103)


def _controller(runtime):
    controller = object.__new__(run_integrated.BotController)
    controller._rt = runtime
    controller._log = lambda *args: None
    controller._thread = None
    controller._movement_thread = None
    controller._attack_thread = None
    controller._support_thread = None
    controller._pickup_thread = None
    controller._stop = run_integrated.threading.Event()
    return controller


def test_dedicated_floor_runner_does_not_create_duplicate_movement_thread(monkeypatch):
    _FakeThread.created = []
    monkeypatch.setattr(run_integrated.threading, "Thread", _FakeThread)
    runner = _FloorRunner()
    controller = _controller(_Runtime(runner))

    controller.start()

    assert runner.started is True
    assert controller._movement_thread is None
    assert "BotMovementLoop" not in [thread.name for thread in _FakeThread.created]


def test_generic_movement_loop_waits_30ms_after_normal_tick():
    class StopProbe:
        def __init__(self):
            self.done = False
            self.waits = []

        def is_set(self):
            return self.done

        def wait(self, seconds):
            self.waits.append(seconds)
            self.done = True

    calls = []
    controller = object.__new__(run_integrated.BotController)
    controller._rt = SimpleNamespace(
        movement_tick=lambda: calls.append("tick"),
        block_runner=SimpleNamespace(
            _route_inputs=SimpleNamespace(release_direction=lambda: None),
        ),
    )
    controller._log = lambda *args: None
    controller._stop = StopProbe()

    controller._movement_loop()

    assert calls == ["tick"]
    assert controller._stop.waits == [0.03]


def test_start_request_while_running_delegates_to_safe_resume():
    resumed = []
    controller = _controller(SimpleNamespace(
        resume_lie_safety_if_clear=lambda: resumed.append(True) or True,
    ))
    controller._thread = SimpleNamespace(is_alive=lambda: True)

    controller.start()

    assert resumed == [True]


def test_f1_refreshes_attack_and_pickup_before_resuming_running_bot():
    from core.runtime import BotRuntime

    data = deepcopy(DEFAULT_CONFIG)
    data["attack"]["key"] = "end"
    data["attack"]["sequences"] = [{
        "enabled": True,
        "name": "새 연속기",
        "keys": ["end", "x"],
        "key_hold_sec": [0.8, 0.2],
        "key_interval_sec": 0.4,
        "repeat_interval_sec": 1.5,
    }]
    data["pickup_timer"]["always_enabled"] = True
    data["pickup_timer"]["pickup_key"] = "z"
    data["pickup_timer"]["interval_sec"] = 2

    attacks = []
    pickup_inputs = []
    released = []
    runtime = SimpleNamespace(
        _cfg=SimpleNamespace(
            attack_key="old",
            attack_sequences=[],
            pickup_key="v",
            pickup_interval=60.0,
            pickup_always=False,
        ),
        combat=SimpleNamespace(
            attack=lambda key, mode, hold: attacks.append((key, mode, hold)),
        ),
        input_backend=SimpleNamespace(
            key_down=lambda key: pickup_inputs.append(("down", key)),
            key_up=lambda key: pickup_inputs.append(("up", key)),
        ),
        orchestrator=SimpleNamespace(mode="hunting"),
        _junk_selling=False,
        _ladder_motion_active=False,
        _anti_mob_busy=False,
        _bot_running=True,
        _pickup_held_key=None,
        _pickup_always_last=-1e9,
        _pickup_always_interval=2.0,
    )
    runtime.release_pickup_key = lambda: released.append(runtime._cfg.pickup_key)
    runtime.reload_combat_support = lambda _fresh: None
    resumed = []
    controller = SimpleNamespace(
        is_running=lambda: True,
        start=lambda: resumed.append(True),
    )
    shell = SimpleNamespace(append_log=lambda *_args: None)
    config = SimpleNamespace(_data=data)

    run_integrated._start_with_fresh_config(controller, runtime, config, shell)
    runtime.attack_sequence_runner.tick(0.0, allowed=True)
    BotRuntime.pickup_tick(runtime, now=0.0)

    assert released == ["v"]
    assert runtime._cfg.attack_key == "end"
    assert runtime._cfg.pickup_key == "z"
    assert runtime._cfg.pickup_interval == 2.0
    assert runtime._cfg.pickup_always is True
    assert attacks == [("end", "duration", 0.8)]
    assert pickup_inputs == [("down", "z")]
    assert resumed == [True]


def test_f1_refreshes_potions_buffs_and_pet_before_resuming_running_bot():
    data = deepcopy(DEFAULT_CONFIG)
    data["recovery"]["hp_potion"].update({"enabled": True, "key": "home", "threshold": 71})
    data["recovery"]["mp_potion"].update({"enabled": True, "key": "delete", "threshold": 43})
    data["recovery"].setdefault("pet_food", {}).update(
        {"enabled": True, "key": "9", "interval_min": 7}
    )
    data["attack"]["normal_buffs"] = [{
        "enabled": True,
        "key": "8",
        "interval_sec": 90,
        "hold_sec": 0.4,
    }]

    refreshed = []
    runtime = SimpleNamespace(
        _cfg=SimpleNamespace(
            attack_key="old",
            attack_sequences=[],
            pickup_key="",
            pickup_interval=60.0,
            pickup_always=False,
        ),
        combat=SimpleNamespace(attack=lambda *_args, **_kwargs: None),
        release_pickup_key=lambda: None,
        reload_combat_support=lambda fresh: refreshed.append(fresh),
    )
    controller = SimpleNamespace(is_running=lambda: True, start=lambda: None)
    shell = SimpleNamespace(append_log=lambda *_args: None)

    run_integrated._start_with_fresh_config(
        controller,
        runtime,
        SimpleNamespace(_data=data),
        shell,
    )

    assert len(refreshed) == 1
    fresh = refreshed[0]
    assert fresh.hp_rule.key == "home"
    assert fresh.mp_rule.key == "delete"
    assert fresh.buffs[0].key == "8"
    assert fresh.pet_key == "9"
    assert fresh.pet_interval == 420.0


def test_runtime_rebuilds_combat_support_objects_from_fresh_config():
    from core.config_adapter import to_runtime_config
    from core.runtime import BotRuntime

    data = deepcopy(DEFAULT_CONFIG)
    data["recovery"]["hp_potion"].update({"enabled": True, "key": "home"})
    data["recovery"]["mp_potion"].update({"enabled": True, "key": "delete"})
    data["recovery"].setdefault("pet_food", {}).update(
        {"enabled": True, "key": "9", "interval_min": 7, "pet_count": 2}
    )
    data["attack"]["normal_buffs"] = [{
        "enabled": True,
        "key": "8",
        "interval_sec": 90,
        "hold_sec": 0.4,
    }]
    fresh = to_runtime_config(data)
    runtime = BotRuntime.__new__(BotRuntime)
    runtime._cfg = SimpleNamespace()
    runtime.input_backend = SimpleNamespace()
    runtime.log = lambda *_args: None

    runtime.reload_combat_support(fresh)

    assert runtime.combat._hp.key == "home"
    assert runtime.combat._mp.key == "delete"
    assert runtime.buffs._buffs[0].key == "8"
    assert runtime.pet._key == "9"
    assert runtime.pet._interval == 420.0
    assert runtime.pet._count == 2
