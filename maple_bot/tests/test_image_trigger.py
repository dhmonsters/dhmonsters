# 사냥 영역 ROI의 템플릿 검출과 액션 쿨다운을 검증하는 테스트
import numpy as np

from core.navigation.image_trigger import ImageTrigger, ImageTriggerSpec
from core.navigation.world_map import ActionSpec


class FakeActionExecutor:
    def __init__(self):
        self.specs = []

    def execute(self, spec):
        self.specs.append(spec)


def test_trigger_searches_only_hunt_roi_and_executes_action():
    actions = FakeActionExecutor()
    seen_shapes = []

    def match_fn(search, template):
        seen_shapes.append(search.shape)
        return 0.91, (2, 3)

    trigger = ImageTrigger(
        actions,
        template_loader=lambda _: np.ones((2, 2, 3), dtype=np.uint8),
        match_fn=match_fn,
        clock_fn=lambda: 10.0,
    )
    spec = ImageTriggerSpec(
        "target.png", 0.8, 0.1, 2.0, ActionSpec("space", 0.1, 1, 0.0, 0.0)
    )

    result = trigger.check(np.zeros((30, 40, 3), dtype=np.uint8), (5, 6, 10, 8), spec)

    assert seen_shapes == [(8, 10, 3)]
    assert result.executed is True
    assert result.location == (7, 9)
    assert actions.specs == [spec.action]


def test_trigger_respects_threshold_check_interval_and_cooldown():
    actions = FakeActionExecutor()
    now = [10.0]
    scores = iter([(0.7, (0, 0)), (0.9, (1, 1)), (0.9, (1, 1))])
    trigger = ImageTrigger(
        actions,
        template_loader=lambda _: np.ones((2, 2, 3), dtype=np.uint8),
        match_fn=lambda *_: next(scores),
        clock_fn=lambda: now[0],
    )
    spec = ImageTriggerSpec(
        "target.png", 0.8, 0.5, 2.0, ActionSpec("space", 0.1, 1, 0.0, 0.0)
    )
    frame = np.zeros((20, 20, 3), dtype=np.uint8)

    assert trigger.check(frame, (0, 0, 10, 10), spec).matched is False
    now[0] = 10.1
    assert trigger.check(frame, (0, 0, 10, 10), spec).checked is False
    now[0] = 10.6
    assert trigger.check(frame, (0, 0, 10, 10), spec).executed is True
    now[0] = 11.2
    assert trigger.check(frame, (0, 0, 10, 10), spec).executed is False
    assert len(actions.specs) == 1


def test_trigger_clips_hunt_roi_to_screen_bounds():
    actions = FakeActionExecutor()
    seen_shapes = []

    def match_fn(search, template):
        seen_shapes.append(search.shape)
        return 0.9, (1, 1)

    trigger = ImageTrigger(
        actions,
        template_loader=lambda _: np.ones((2, 2, 3), dtype=np.uint8),
        match_fn=match_fn,
        clock_fn=lambda: 1.0,
    )
    spec = ImageTriggerSpec(
        "target.png", 0.8, 0.0, 0.0, ActionSpec("space", 0.1, 1, 0.0, 0.0)
    )

    result = trigger.check(
        np.zeros((10, 10, 3), dtype=np.uint8), (-3, -2, 8, 7), spec
    )

    assert seen_shapes == [(5, 5, 3)]
    assert result.executed is True


def test_invalid_roi_and_template_failure_never_execute_action():
    actions = FakeActionExecutor()
    spec = ImageTriggerSpec(
        "missing.png", 0.8, 0.0, 0.0, ActionSpec("space", 0.1, 1, 0.0, 0.0)
    )
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    invalid_roi_trigger = ImageTrigger(actions, clock_fn=lambda: 1.0)

    import pytest

    with pytest.raises(ValueError, match="사냥 영역"):
        invalid_roi_trigger.check(frame, (5, 5, -1, 3), spec)
    assert actions.specs == []

    load_failure_trigger = ImageTrigger(
        actions,
        template_loader=lambda _: (_ for _ in ()).throw(ValueError("load failed")),
        clock_fn=lambda: 2.0,
    )
    with pytest.raises(ValueError, match="load failed"):
        load_failure_trigger.check(frame, (0, 0, 5, 5), spec)
    assert actions.specs == []
