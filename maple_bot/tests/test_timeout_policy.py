# 사다리·방지몹·빨코3 확인 제한 시간이 실제 대기 동작에 적용되는지 검증한다.
from __future__ import annotations

import threading
from types import SimpleNamespace

import numpy as np


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += float(seconds)


class RecordingBackend:
    def __init__(self, clock=None):
        self.clock = clock
        self.events = []

    def begin_priority(self):
        pass

    def end_priority(self):
        pass

    def key_down(self, key):
        self.events.append(("down", key, None if self.clock is None else self.clock.now))

    def key_up(self, key):
        self.events.append(("up", key, None if self.clock is None else self.clock.now))


class DirectionOwner:
    def __init__(self):
        self.direction = None

    def hold_direction(self, direction):
        self.direction = direction

    def release_direction(self):
        self.direction = None


def test_ladder_grab_verification_stops_within_point_one_second(monkeypatch):
    from core.navigation import ladder_controller as module
    from core.navigation.ladder_controller import LadderController, LadderControllerConfig

    clock = FakeClock()
    monkeypatch.setattr(module.time, "monotonic", clock.monotonic)
    backend = RecordingBackend(clock)
    directions = DirectionOwner()
    controller = LadderController(
        input_backend=backend,
        direction_owner=directions,
        position_sample_fn=lambda: ((60, 68), 1.0),
        position_fn=lambda: (60, 68),
        finish_climb_fn=lambda *_args: False,
        ladder_motion_fn=lambda _active: None,
        stop_fn=lambda: False,
        sleep_fn=clock.sleep,
        log_fn=lambda _message: None,
        jump_key="alt",
        config=LadderControllerConfig(),
    )

    assert controller._jump_attempt(60, 46, 20) is False

    up_started = next(at for action, key, at in backend.events if action == "down" and key == "up")
    assert clock.now - up_started <= 0.13


def test_block_runner_applies_point_one_second_ladder_verification(monkeypatch):
    from core.navigation import ladder_controller as module
    from core.navigation.block_runner import BlockRunner

    clock = FakeClock()
    monkeypatch.setattr(module.time, "monotonic", clock.monotonic)
    backend = RecordingBackend(clock)
    runner = BlockRunner(
        backend,
        pos_fn=lambda: (60, 68),
        position_sample_fn=lambda: ((60, 68), 1.0),
        sleep_fn=clock.sleep,
    )

    assert runner._ladder_controller._jump_attempt(60, 46, 20) is False

    up_started = next(at for action, key, at in backend.events if action == "down" and key == "up")
    assert clock.now - up_started <= 0.13


def test_rednose3_platform_confirmation_stops_within_point_one_second(monkeypatch):
    from core.navigation import rednose3_runner as module
    from core.navigation.rednose3_runner import RedNose3RouteRunner

    clock = FakeClock()
    monkeypatch.setattr(module.time, "monotonic", clock.monotonic)

    class BlockRunner:
        def _stop(self):
            return False

        def _get_pos(self):
            return (999, 999)

        def refresh_position(self):
            return (self._get_pos(), clock.now)

    runner = RedNose3RouteRunner(
        BlockRunner(),
        is_active=lambda: True,
        profile={
            "platforms": {"1": {"x_min": 0, "x_max": 10, "y_min": 0, "y_max": 10}}
        },
        sleep_fn=clock.sleep,
    )

    assert runner._wait_platform(1) is False
    assert clock.now <= 0.13


def test_runtime_rednose3_profile_applies_point_one_second_confirmation(monkeypatch):
    from core import config_adapter
    from core.navigation import rednose3_runner as module
    from core.navigation.rednose3_runner import RedNose3RouteRunner

    clock = FakeClock()
    monkeypatch.setattr(module.time, "monotonic", clock.monotonic)

    class BlockRunner:
        def _stop(self):
            return False

        def _get_pos(self):
            return (999, 999)

        def refresh_position(self):
            return (self._get_pos(), clock.now)

    profile = config_adapter._rednose3_profile({"minimap": {}}, {})
    runner = RedNose3RouteRunner(
        BlockRunner(),
        is_active=lambda: True,
        profile=profile,
        sleep_fn=clock.sleep,
    )

    assert runner._wait_platform(1) is False
    assert clock.now <= 0.13


def test_anti_mob_image2_search_releases_left_within_one_second(monkeypatch):
    import cv2
    from core import runtime as module
    from core.runtime import BotRuntime

    clock = FakeClock()
    monkeypatch.setattr(module.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(module.time, "sleep", clock.sleep)
    monkeypatch.setattr(
        module.monster_vision,
        "load_template",
        lambda path: np.ones((1, 1, 3), dtype=np.uint8)
        if "image1_" in str(path)
        else np.zeros((1, 1, 3), dtype=np.uint8),
    )
    monkeypatch.setattr(
        cv2,
        "matchTemplate",
        lambda _scene, candidate, _method: np.array([[float(candidate[0, 0, 0])]], dtype=np.float32),
    )

    backend = RecordingBackend(clock)
    runtime = BotRuntime.__new__(BotRuntime)
    runtime._cfg = SimpleNamespace(
        anti_mob_profile={
            "enabled": True,
            "profile": "beginner_training",
            "threshold": 0.5,
            "cooldown_sec": 60.0,
        },
        hunt_area_region={"left": 0, "top": 0, "width": 2, "height": 2},
    )
    runtime._anti_mob_busy = False
    runtime._anti_mob_moving = False
    runtime._anti_mob_failed = False
    runtime._anti_mob_last = -1e9
    runtime._anti_mob_last_diag = -1e9
    runtime._bot_running = True
    runtime._movement_lock = threading.Lock()
    runtime.input_backend = backend
    runtime.telegram = SimpleNamespace(send=lambda _message: None)
    runtime.log = lambda _message, _category: None
    runtime._release_runtime_inputs = lambda: None
    runtime._resolve_region = lambda region: region
    runtime._capture = lambda _region: np.zeros((2, 2, 3), dtype=np.uint8)

    runtime._check_anti_mob_profile()

    left_down = next(at for action, key, at in backend.events if action == "down" and key == "left")
    left_up = next(at for action, key, at in backend.events if action == "up" and key == "left")
    assert left_up - left_down <= 1.05
