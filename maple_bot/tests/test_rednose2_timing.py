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


def test_platform1415_move_continues_until_position_enters_allowed_range(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    position = [97.0, 62.0]
    held_directions = []

    def hold_direction(direction):
        held_directions.append(direction)
        route_inputs.direction = direction
        position[0] = 96.0

    monkeypatch.setattr("core.navigation.rednose2_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr("core.navigation.rednose2_runner.time.perf_counter", clock.perf_counter)
    monkeypatch.setattr(route_inputs, "hold_direction", hold_direction)
    monkeypatch.setattr(runner, "_current_pos", lambda: tuple(position))

    assert runner._move_to_target_v5(
        95.0,
        attack=False,
        arrival_range=(94.0, 96.0),
    )
    assert held_directions == ["left"]


@pytest.mark.parametrize(
    ("move_index", "start_x", "expected_direction"),
    [(0, 119.0, "right"), (1, 60.0, "left")],
)
def test_floor2_end_move_allows_teleport_inside_default_stop_distance(
    monkeypatch,
    move_index,
    start_x,
    expected_direction,
):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(
        clock,
        route_inputs,
        {"floor2_left_x": 55, "floor2_right_x": 124},
    )
    runner._main_move_index = move_index
    runner._next_collection_at = float("inf")
    position = [start_x, 62.0]
    teleports = []

    def teleport(direction):
        teleports.append(direction)
        position[0] += 13.0 if direction == "right" else -13.0

    monkeypatch.setattr("core.navigation.rednose2_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr("core.navigation.rednose2_runner.time.perf_counter", clock.perf_counter)
    monkeypatch.setattr(runner, "_current_pos", lambda: tuple(position))
    monkeypatch.setattr(runner, "_fresh_sample", lambda: (tuple(position), clock.now))
    monkeypatch.setattr(runner, "_teleport_attack", teleport)

    assert runner._run_floor2_hunt_once() is True
    assert teleports == [expected_direction]


def test_floor2_collection_right_edge_allows_teleport_inside_default_stop_distance(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs, {"floor2_right_safe_x": 126})
    position = [120.0, 62.0]
    teleports = []

    def teleport(direction):
        teleports.append(direction)
        position[0] += 13.0

    monkeypatch.setattr("core.navigation.rednose2_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr("core.navigation.rednose2_runner.time.perf_counter", clock.perf_counter)
    monkeypatch.setattr(runner, "_current_pos", lambda: tuple(position))
    monkeypatch.setattr(runner, "_fresh_sample", lambda: (tuple(position), clock.now))
    monkeypatch.setattr(runner, "_teleport_attack", teleport)

    assert runner._move_floor2_right_edge() is True
    assert teleports == ["right"]


def test_platform27_manual_attack_hold_uses_half_second_default(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    monkeypatch.setattr("core.navigation.rednose2_runner.down_5", lambda value: round(value * 0.95, 4))
    monkeypatch.setattr(runner, "_teleport_once", lambda direction: None)
    monkeypatch.setattr(runner, "_wait_floor", lambda predicate, timeout: True)

    assert runner._finish_platform27_and_return_floor2()

    assert route_inputs.action_events == [("down", "end", 0.0), ("up", "end", 0.475)]


def test_platform27_return_stops_after_five_down_teleports(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    directions = []

    monkeypatch.setattr("core.navigation.rednose2_runner.down_5", lambda value: round(value * 0.95, 4))
    monkeypatch.setattr(runner, "_teleport_once", directions.append)
    monkeypatch.setattr(runner, "_wait_floor", lambda _predicate, _timeout: False)
    monkeypatch.setattr(runner, "_is_lower_floor_v5", lambda _position: False)

    assert runner._finish_platform27_and_return_floor2() is False
    assert directions == ["left", "down", "down", "down", "down", "down"]


def test_auto_sell_starts_immediately_when_already_on_shop_entry_floor(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    monkeypatch.setattr(runner, "_current_pos", lambda: (130.0, 49.0))
    monkeypatch.setattr(runner, "_fresh_pos", lambda: (130.0, 49.0))
    monkeypatch.setattr(
        runner,
        "_move_to_target_v5",
        lambda *_args, **_kwargs: pytest.fail("상점 진입층에서는 이동하면 안 됩니다."),
    )
    monkeypatch.setattr(
        runner,
        "_teleport_once",
        lambda *_args, **_kwargs: pytest.fail("상점 진입층에서는 텔포하면 안 됩니다."),
    )

    assert runner.prepare_auto_sell_from_floor2() is True


def test_auto_sell_recovers_floor1_before_alignment(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    position = [41.0, 75.0]
    events = []
    monkeypatch.setattr(runner, "_current_pos", lambda: tuple(position))
    monkeypatch.setattr(runner, "_fresh_pos", lambda: tuple(position))

    def recover(*, active_fn=None):
        events.append(("recover", active_fn is not None))
        position[:] = [129.0, 62.0]
        return True

    monkeypatch.setattr(runner, "_return_floor2_from_stair7", recover)

    def teleport(direction):
        events.append(("teleport", direction))
        if direction == "up":
            position[:] = [129.0, 49.0]

    monkeypatch.setattr(runner, "_teleport_once", teleport)

    assert runner.prepare_auto_sell_from_floor2() is True
    assert events == [("recover", True), ("teleport", "up")]


def test_auto_sell_drops_from_upper_collection_platform_to_floor2(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    position = [95.0, 54.0]
    events = []
    monkeypatch.setattr(runner, "_current_pos", lambda: tuple(position))
    monkeypatch.setattr(runner, "_fresh_pos", lambda: tuple(position))

    def teleport(direction):
        events.append(direction)
        if direction == "down":
            position[:] = [95.0, 62.0]
        elif direction == "up":
            position[:] = [129.0, 49.0]

    monkeypatch.setattr(runner, "_teleport_once", teleport)
    monkeypatch.setattr(runner, "_move_to_target_v5", lambda *_args, **_kwargs: position.__setitem__(0, 129.0) or True)

    assert runner.prepare_auto_sell_from_floor2() is True
    assert events == ["down", "up"]


def test_auto_sell_does_not_mistake_platform16_for_shop_entry(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    position = [95.0, 49.0]
    events = []
    monkeypatch.setattr(runner, "_current_pos", lambda: tuple(position))
    monkeypatch.setattr(runner, "_fresh_pos", lambda: tuple(position))

    def teleport(direction):
        events.append(direction)
        if direction == "down":
            position[:] = [95.0, 62.0]
        elif direction == "up":
            position[:] = [129.0, 49.0]

    monkeypatch.setattr(runner, "_teleport_once", teleport)
    monkeypatch.setattr(runner, "_move_to_target_v5", lambda *_args, **_kwargs: position.__setitem__(0, 129.0) or True)

    assert runner.prepare_auto_sell_from_floor2() is True
    assert events == ["down", "up"]


def test_platform24_uses_three_attempts_and_strict_point_tolerances(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    waits = []
    teleports = []

    monkeypatch.setattr(runner, "_is_upper_floor_v5", lambda _position: True)
    monkeypatch.setattr(runner, "_move_to_target_v5", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(runner, "_teleport_once", teleports.append)

    def wait_point(prefix, fallback_x, fallback_y, **kwargs):
        waits.append((prefix, fallback_x, fallback_y, kwargs))
        return False

    monkeypatch.setattr(runner, "_wait_point", wait_point)

    assert runner._enter_platform24() is False
    assert teleports == ["left", "left", "left"]
    assert waits == [
        ("platform24", 30, 61, {"timeout_sec": 0.45, "x_tolerance": 2, "y_tolerance": 1}),
    ] * 3


def test_platform24_drop_rejects_y_outside_one_pixel_tolerance_and_tries_three_times(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs, {"floor1_y_min": 75, "floor1_y_max": 77})
    teleports = []

    monkeypatch.setattr("core.navigation.rednose2_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr(runner, "_current_pos", lambda: (30.0, 73.0))
    monkeypatch.setattr(runner, "_teleport_once", teleports.append)

    assert runner._drop_from_platform24_to_floor1() is False
    assert teleports == ["down", "down", "down"]


def test_collection_teleports_right_twice_after_confirmed_platform24_drop(monkeypatch):
    clock = FakeClock()
    runner = make_runner(clock, RecordingRouteInputs(clock))
    runner._collection_stage = "floor1_drop"
    teleports = []
    events = []

    monkeypatch.setattr(runner, "_is_upper_floor_v5", lambda _position: True)
    monkeypatch.setattr(runner, "_drop_from_platform24_to_floor1", lambda: events.append("drop") or True)
    monkeypatch.setattr(runner, "_teleport_once", teleports.append)
    monkeypatch.setattr(runner, "_return_floor2_from_stair7", lambda: events.append("stair7") or True)
    monkeypatch.setattr(runner, "_move_floor2_right_edge", lambda: True)
    monkeypatch.setattr(runner, "_enter_platform1415", lambda: True)
    monkeypatch.setattr(runner, "_enter_platform16", lambda: True)
    monkeypatch.setattr(runner, "_enter_platform27", lambda: True)
    monkeypatch.setattr(runner, "_finish_platform27_and_return_floor2", lambda: True)

    assert runner._run_rednose_new_v5_collection() is True
    assert events == ["drop", "stair7"]
    assert teleports == ["right", "right"]


@pytest.mark.parametrize(
    ("y", "expected"),
    [(63.0, False), (64.0, True), (70.0, True), (74.0, True), (75.0, False)],
)
def test_stair7_intermediate_y_uses_open_range_between_floor2_and_floor1(y, expected):
    clock = FakeClock()
    runner = make_runner(
        clock,
        RecordingRouteInputs(clock),
        {"floor2_y_max": 63, "floor1_y_min": 75},
    )
    runner._current_pos = lambda: (41.0, y)

    assert runner._is_stair7_return_y() is expected


def test_platform1415_retries_three_times_with_point_six_second_attacks(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    teleports = []

    monkeypatch.setattr(runner, "_current_pos", lambda: (95.0, 62.0))
    monkeypatch.setattr(runner, "_teleport_once", teleports.append)
    monkeypatch.setattr(runner, "_wait_y_range", lambda *_args, **_kwargs: False)

    assert runner._enter_platform1415() is False
    assert teleports == ["up", "up", "up"]
    assert route_inputs.presses == [("end", 0.6, 0.0), ("end", 0.6, 0.6)]


def test_platform16_attacks_then_teleports_three_times_and_uses_simple_bypass(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    teleports = []

    monkeypatch.setattr("core.navigation.rednose2_runner.down_5", lambda value: round(value * 0.95, 4))
    monkeypatch.setattr(
        runner,
        "_move_to_target_v5",
        lambda *_args, **_kwargs: pytest.fail("16번 진입에서는 X 재정렬 이동을 하면 안 됩니다."),
    )
    monkeypatch.setattr(runner, "_teleport_once", teleports.append)
    monkeypatch.setattr(runner, "_wait_y_range", lambda *_args, **_kwargs: False)

    assert runner._enter_platform16() is True
    assert teleports == ["up", "up", "up", "up", "left"]
    assert [event for event in route_inputs.action_events if event[0] == "down"] == [
        ("down", "end", 0.0),
        ("down", "end", 0.475),
        ("down", "end", 0.95),
    ]
    assert clock.now == pytest.approx(1.425)


def test_platform1415_attack_hold_uses_saved_duration_before_platform16_teleport(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs, {"platform1415_attack_hold_sec": 0.8})

    monkeypatch.setattr("core.navigation.rednose2_runner.down_5", lambda value: value)
    monkeypatch.setattr(runner, "_teleport_once", lambda _direction: None)
    monkeypatch.setattr(runner, "_wait_y_range", lambda *_args, **_kwargs: True)

    assert runner._enter_platform16() is True
    assert route_inputs.action_events[-2:] == [("down", "end", 0.0), ("up", "end", 0.8)]


def test_platform27_uses_three_attempts_and_attacks_after_arrival(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs)
    waits = iter((False, False, True))
    teleports = []

    monkeypatch.setattr("core.navigation.rednose2_runner.down_5", lambda value: round(value * 0.95, 4))
    monkeypatch.setattr(runner, "_move_to_target_v5", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(runner, "_teleport_once", teleports.append)
    monkeypatch.setattr(runner, "_wait_y_range", lambda *_args, **_kwargs: next(waits))

    assert runner._enter_platform27() is True
    assert teleports == ["left", "left", "left"]
    assert [event for event in route_inputs.action_events if event[0] == "down"] == [
        ("down", "end", 0.0),
    ]
    assert clock.now == pytest.approx(0.475)


def test_platform27_entry_attack_hold_uses_saved_duration(monkeypatch):
    clock = FakeClock()
    route_inputs = RecordingRouteInputs(clock)
    runner = make_runner(clock, route_inputs, {"platform27_entry_attack_hold_sec": 0.7})

    monkeypatch.setattr("core.navigation.rednose2_runner.down_5", lambda value: value)
    monkeypatch.setattr(runner, "_move_to_target_v5", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(runner, "_teleport_once", lambda _direction: None)
    monkeypatch.setattr(runner, "_wait_y_range", lambda *_args, **_kwargs: True)

    assert runner._enter_platform27() is True
    assert route_inputs.action_events[-2:] == [("down", "end", 0.0), ("up", "end", 0.7)]


def test_collection_completion_randomizes_next_floor2_direction(monkeypatch):
    clock = FakeClock()
    runner = make_runner(clock, RecordingRouteInputs(clock))

    monkeypatch.setattr("core.navigation.rednose2_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr("core.navigation.rednose2_runner.random.choice", lambda values: values[1])
    monkeypatch.setattr(runner, "_is_upper_floor_v5", lambda _position: True)
    for method_name in (
        "_enter_platform24",
        "_drop_from_platform24_to_floor1",
        "_return_floor2_from_stair7",
        "_move_floor2_right_edge",
        "_enter_platform1415",
        "_enter_platform16",
        "_enter_platform27",
        "_finish_platform27_and_return_floor2",
    ):
        monkeypatch.setattr(runner, method_name, lambda: True)

    assert runner._run_rednose_new_v5_collection() is True
    assert runner._main_move_index == 1
