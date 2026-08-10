# 이동과 사다리 입력이 Humanizer 없이 기존 입력 소유자를 통해 즉시 전달되는지 검증한다.
from core.humanize.priority_input_executor import PriorityInputExecutor
from core.navigation.route_input_owner import RouteInputOwner


class FakeBackend:
    def __init__(self):
        self.calls = []

    def key_down(self, key):
        self.calls.append(("down", key))

    def key_up(self, key):
        self.calls.append(("up", key))

    def press(self, key, hold_sec=0.05):
        self.calls.append(("press", key, hold_sec))

    def begin_priority(self):
        self.calls.append(("priority", "begin"))

    def end_priority(self):
        self.calls.append(("priority", "end"))


def test_route_owner_switches_direction_without_humanizer():
    backend = FakeBackend()
    owner = RouteInputOwner(backend)

    owner.hold_direction("right")
    owner.hold_direction("left")
    owner.release_all()

    assert backend.calls == [
        ("down", "right"),
        ("up", "right"),
        ("down", "left"),
        ("up", "left"),
    ]
    assert not hasattr(owner, "_humanizer")


def test_priority_ladder_sequence_is_immediate_and_direct():
    backend = FakeBackend()
    owner = RouteInputOwner(backend)
    sleeps = []
    executor = PriorityInputExecutor(backend, owner, sleep_fn=sleeps.append)

    result = executor.perform_ladder_jump(
        jump_key="alt",
        jump_hold_sec=0.1,
        up_delay_sec=0.3,
        direction="right",
    )

    assert backend.calls == [
        ("priority", "begin"),
        ("down", "right"),
        ("down", "alt"),
        ("up", "alt"),
        ("up", "right"),
        ("down", "up"),
        ("priority", "end"),
    ]
    assert len(sleeps) == 2
    assert 0.095 <= sleeps[0] <= 0.1
    assert 0.185 <= sleeps[1] <= 0.205
    assert result["up_down_at"] >= result["jump_down_at"]
    assert not hasattr(executor, "_humanizer")
