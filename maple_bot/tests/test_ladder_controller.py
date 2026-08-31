# 상태 기반 사다리 컨트롤러의 접근, 점프, 잡기 확인 흐름을 검증
from types import SimpleNamespace

from core.navigation.ladder_controller import LadderController, LadderControllerConfig


class FakeInput:
    def __init__(self):
        self.direction = None
        self.held = set()
        self.jumps = 0

    def hold_direction(self, direction):
        self.direction = direction

    def release_direction(self):
        self.direction = None

    def hold_action(self, key):
        self.held.add(key)

    def release_action(self, key):
        self.held.discard(key)

    def key_down(self, key):
        self.held.add(key)
        if key == "alt":
            self.jumps += 1

    def key_up(self, key):
        self.held.discard(key)

    def begin_priority(self):
        pass

    def end_priority(self):
        pass


def test_jump_grab_uses_two_new_aligned_rising_samples():
    inputs = FakeInput()
    samples = iter([
        ((54, 69), 1.0),
        ((59, 66), 2.0),
        ((60, 63), 3.0),
    ])
    latest = [((60, 63), 3.0)]

    def sample():
        try:
            latest[0] = next(samples)
        except StopIteration:
            pass
        return latest[0]

    finished = []
    controller = LadderController(
        input_backend=inputs,
        direction_owner=inputs,
        position_sample_fn=sample,
        position_fn=lambda: latest[0][0],
        finish_climb_fn=lambda ladder_x, y_top, max_steps, direction: finished.append(direction) or True,
        ladder_motion_fn=lambda active: None,
        stop_fn=lambda: False,
        sleep_fn=lambda seconds: None,
        log_fn=lambda message: None,
        jump_key="alt",
        config=LadderControllerConfig(launch_distance=6.0),
    )
    block = SimpleNamespace(ladder_x=60, y_top=46, y_bot=68)

    assert controller.run(block, max_steps=20) is True
    assert inputs.jumps == 1
    assert finished == ["right"]
