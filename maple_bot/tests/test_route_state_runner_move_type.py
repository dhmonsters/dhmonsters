# 사용자 지정 이동 단계의 걷기와 텔레포트 입력 방식을 검증한다.
from types import SimpleNamespace

from core.navigation.route_state import RouteStep
from core.navigation.route_state_runner import RouteStateRunner


class SequencePositionStore:
    def __init__(self, xs):
        self.samples = [
            None if x is None else SimpleNamespace(x=x, y=40)
            for x in xs
        ]

    def latest(self, max_age_sec):
        return self.samples.pop(0)


class AdvancingClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += 3.0


class RecordingInputOwner:
    def __init__(self):
        self.events = []

    def hold_direction(self, direction):
        self.events.append(("direction", direction))

    def release_direction(self):
        self.events.append(("release_direction",))

    def press_action(self, key, hold_sec):
        self.events.append(("press", key, hold_sec))

    def release_all(self):
        self.events.append(("release_all",))


def make_move_step(move_type):
    return RouteStep.from_dict({
        "id": f"{move_type}_move",
        "step_type": "move",
        "parameters": {
            "start_x": 10,
            "end_x": 100,
            "move_type": move_type,
            "mode": "pass",
        },
        "completion": {
            "type": "x_reached",
            "target_x": 100,
            "tolerance": 1,
        },
        "failure": {"timeout_sec": 2.0},
    })


def run_move(move_type):
    inputs = RecordingInputOwner()
    runner = RouteStateRunner(
        get_steps=lambda: [],
        is_active=lambda: True,
        position_store=SequencePositionStore([10, 100]),
        input_owner=inputs,
        block_runner=SimpleNamespace(teleport_key="x"),
        idle_sleep=0.01,
    )
    step = make_move_step(move_type)

    assert runner._execute_move(step, [step]) is True
    return inputs.events


def test_teleport_move_presses_configured_teleport_key(monkeypatch):
    monkeypatch.setattr("core.navigation.route_state_runner.time.sleep", lambda _seconds: None)

    events = run_move("teleport")

    assert ("direction", "right") in events
    assert ("press", "x", 0.05) in events


def test_walk_move_does_not_press_teleport_key(monkeypatch):
    monkeypatch.setattr("core.navigation.route_state_runner.time.sleep", lambda _seconds: None)

    events = run_move("walk")

    assert not any(event[0] == "press" for event in events)


def test_move_timeout_excludes_temporary_position_detection_gap(monkeypatch):
    clock = AdvancingClock()
    inputs = RecordingInputOwner()
    positions = SequencePositionStore([None, None, None, 10, 20, 100])
    runner = RouteStateRunner(
        get_steps=lambda: [],
        is_active=lambda: True,
        position_store=positions,
        input_owner=inputs,
        idle_sleep=0.01,
    )
    step = RouteStep.from_dict({
        "id": "walk_after_detection_gap",
        "step_type": "move",
        "parameters": {
            "start_x": 10,
            "end_x": 100,
            "move_type": "walk",
            "mode": "pass",
        },
        "completion": {
            "type": "x_reached",
            "target_x": 100,
            "tolerance": 1,
        },
        "failure": {"timeout_sec": 10.0},
    })
    monkeypatch.setattr(
        "core.navigation.route_state_runner.time.monotonic",
        clock.monotonic,
    )
    monkeypatch.setattr(
        "core.navigation.route_state_runner.time.sleep",
        clock.sleep,
    )

    assert runner._execute_move(step, [step]) is True
    assert inputs.events.count(("direction", "right")) == 2


def test_infinite_move_block_runs_right_then_left(monkeypatch):
    inputs = RecordingInputOwner()
    runner = RouteStateRunner(
        get_steps=lambda: [],
        is_active=lambda: True,
        position_store=SequencePositionStore([10, 100, 100, 10]),
        input_owner=inputs,
        idle_sleep=0.01,
    )
    step = RouteStep.from_dict({
        "id": "left_right_sweep",
        "step_type": "move",
        "parameters": {
            "start_x": 10,
            "end_x": 100,
            "move_type": "walk",
            "mode": "infinite",
            "sweeps": 1,
        },
        "completion": {
            "type": "repeat_count",
            "tolerance": 1,
            "repeat_count": 1,
        },
        "failure": {"timeout_sec": 10.0},
    })
    monkeypatch.setattr("core.navigation.route_state_runner.time.sleep", lambda _seconds: None)

    assert runner._execute_move(step, [step]) is True
    assert ("direction", "right") in inputs.events
    assert ("direction", "left") in inputs.events


def test_move_block_does_not_stop_only_because_elapsed_time_exceeds_failure_timeout(monkeypatch):
    clock = AdvancingClock()
    inputs = RecordingInputOwner()
    runner = RouteStateRunner(
        get_steps=lambda: [],
        is_active=lambda: True,
        position_store=SequencePositionStore([10, 20, 30, 100]),
        input_owner=inputs,
        idle_sleep=0.01,
    )
    step = RouteStep.from_dict({
        "id": "slow_but_progressing_move",
        "step_type": "move",
        "parameters": {
            "start_x": 10,
            "end_x": 100,
            "move_type": "walk",
            "mode": "pass",
        },
        "completion": {
            "type": "x_reached",
            "target_x": 100,
            "tolerance": 1,
        },
        "failure": {"timeout_sec": 2.0},
    })
    monkeypatch.setattr("core.navigation.route_state_runner.time.monotonic", clock.monotonic)
    monkeypatch.setattr("core.navigation.route_state_runner.time.sleep", clock.sleep)

    assert runner._execute_move(step, [step]) is True
    assert clock.now > step.failure.timeout_sec
    assert ("direction", "right") in inputs.events
