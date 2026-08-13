# 빨코2 텔포 공격의 총 공격 홀드와 완료 후 반복 간격을 검증한다.
from types import SimpleNamespace

import pytest

from core.navigation.rednose2_runner import RedNose2RouteRunner


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def perf_counter(self):
        return self.now

    def sleep(self, duration):
        self.sleeps.append(duration)
        self.now += duration


class RecordingRouteInputs:
    def __init__(self, clock):
        self.clock = clock
        self.direction = None
        self.presses = []
        self.action_events = []

    def hold_direction(self, direction):
        self.direction = direction

    def release_direction(self):
        self.direction = None

    def hold_action(self, key):
        self.action_events.append(("down", key, self.clock.now))

    def release_action(self, key):
        self.action_events.append(("up", key, self.clock.now))

    def press_action(self, key, hold_sec=0.05):
        self.presses.append((key, hold_sec, self.clock.now))
        self.clock.sleep(hold_sec)


def make_runner(clock, route_inputs, profile=None):
    block_runner = SimpleNamespace(
        _route_inputs=route_inputs,
        release_inputs=lambda: None,
        _stop=lambda: False,
    )
    return RedNose2RouteRunner(
        block_runner,
        get_blocks=lambda: [],
        is_active=lambda: True,
        profile={
            "attack_key": "end",
            "teleport_key": "x",
            "attack_hold_sec": 0.9,
            "teleport_hold_sec": 0.3,
            "attack_to_teleport_sec": 0.5,
            "teleport_step_px": 13.0,
            "arrival_tolerance": 3,
            "max_step_sec": 20.0,
            **(profile or {}),
        },
        sleep_fn=clock.sleep,
    )


def test_teleport_attack_uses_randomized_total_attack_hold_once(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    monkeypatch.setattr("core.navigation.rednose2_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr("core.navigation.rednose2_runner.down_5", lambda value: round(value * 0.95, 4))

    runner._teleport_attack("right")

    assert route_inputs.presses == [("x", 0.3, 0.5)]
    assert route_inputs.action_events == [("down", "end", 0.0), ("up", "end", 0.855)]
    assert clock.now == pytest.approx(0.855)


def test_next_teleport_interval_starts_after_action_completion(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    position = [0.0, 62.0]
    action_windows = []

    def current_pos():
        return tuple(position)

    def fresh_sample():
        position[0] += 13.0
        return tuple(position), clock.now

    original_attack = runner._teleport_attack

    def record_attack(direction):
        started = clock.now
        original_attack(direction)
        action_windows.append((started, clock.now))

    monkeypatch.setattr("core.navigation.rednose2_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr("core.navigation.rednose2_runner.time.perf_counter", clock.perf_counter)
    monkeypatch.setattr("core.navigation.rednose2_runner.down_5", lambda value: round(value * 0.95, 4))
    monkeypatch.setattr(runner, "_current_pos", current_pos)
    monkeypatch.setattr(runner, "_fresh_sample", fresh_sample)
    monkeypatch.setattr(runner, "_teleport_attack", record_attack)

    assert runner._move_to_target_v5(40.0, attack=True, interval_sec=0.72)

    assert len(action_windows) >= 2
    for previous, following in zip(action_windows, action_windows[1:]):
        assert following[0] - previous[1] >= 0.72
