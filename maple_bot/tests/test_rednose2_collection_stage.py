# 빨코2 회수 루틴이 실패한 현재 단계를 보존하는지 검증한다.
from core.navigation.rednose2_runner import RedNose2RouteRunner


class FakeBlockRunner:
    _route_inputs = object()


def test_platform1415_failure_keeps_platform1415_as_next_collection_stage():
    runner = RedNose2RouteRunner(
        FakeBlockRunner(),
        get_blocks=lambda: [],
        is_active=lambda: True,
        sleep_fn=lambda _seconds: None,
    )
    runner._collection_stage = "platform1415"
    runner._is_upper_floor_v5 = lambda _position: True
    runner._enter_platform1415 = lambda: False
    runner._release_attack_key = lambda: None
    runner._release_owned_inputs = lambda: None

    result = runner._run_rednose_new_v5_collection()

    assert result is False
    assert runner._collection_stage == "platform1415"


def test_pending_collection_stage_resumes_before_general_floor2_hunt():
    runner = RedNose2RouteRunner(
        FakeBlockRunner(),
        get_blocks=lambda: [],
        is_active=lambda: True,
        sleep_fn=lambda _seconds: None,
    )
    runner._collection_stage = "stair7_return"
    calls = []
    runner._run_rednose_new_v5_collection = lambda: calls.append("collection") or True
    runner._run_floor2_hunt_once = lambda: calls.append("hunt") or True

    assert runner._run_rednose_new_v5_once() is True
    assert calls == ["collection"]


def test_platform24_off_floor_failure_continues_collection_after_stair7_return():
    runner = RedNose2RouteRunner(
        FakeBlockRunner(),
        get_blocks=lambda: [],
        is_active=lambda: True,
        sleep_fn=lambda _seconds: None,
    )
    upper_floor_checks = iter((True, False))
    events = []
    runner._is_upper_floor_v5 = lambda _position: next(upper_floor_checks, True)
    runner._enter_platform24 = lambda: False
    runner._return_floor2_from_stair7 = lambda: events.append("stair7") or True
    runner._move_floor2_right_edge = lambda: events.append("right_edge") or True
    runner._enter_platform1415 = lambda: events.append("platform1415") or True
    runner._enter_platform16 = lambda: True
    runner._enter_platform27 = lambda: True
    runner._finish_platform27_and_return_floor2 = lambda: True
    runner._release_attack_key = lambda: None
    runner._release_owned_inputs = lambda: None

    assert runner._run_rednose_new_v5_collection() is True
    assert events == ["stair7", "right_edge", "platform1415"]


def test_floor2_hunt_and_collection_edge_use_their_distinct_right_targets():
    runner = RedNose2RouteRunner(
        FakeBlockRunner(),
        get_blocks=lambda: [],
        is_active=lambda: True,
        profile={
            "floor2_right_x": 118,
            "floor2_right_safe_x": 126,
            "base_minimap_width": 172,
            "base_minimap_height": 103,
            "minimap_width": 172,
            "minimap_height": 103,
        },
        sleep_fn=lambda _seconds: None,
    )
    runner._next_collection_at = float("inf")
    runner._is_upper_floor_v5 = lambda _position: True
    runner._current_pos = lambda: (80, 62)
    targets = []
    runner._move_to_target_v5 = lambda target_x, **_kwargs: targets.append(target_x) or True

    assert runner._run_floor2_hunt_once() is True
    assert runner._move_floor2_right_edge() is True
    assert targets == [118.0, 126.0]


def _collection_runner(position, stage):
    runner = RedNose2RouteRunner(
        FakeBlockRunner(),
        get_blocks=lambda: [],
        is_active=lambda: True,
        profile={
            "base_minimap_width": 172,
            "base_minimap_height": 103,
            "minimap_width": 172,
            "minimap_height": 103,
            "floor1_y_min": 72,
            "floor1_y_max": 82,
            "floor2_y_min": 61,
            "floor2_y_max": 63,
            "platform16_y_min": 47,
            "platform16_y_max": 48,
            "platform27_y_min": 50,
            "platform27_y_max": 50,
        },
        sleep_fn=lambda _seconds: None,
    )
    runner._collection_stage = stage
    runner._current_pos = lambda: position
    runner._release_attack_key = lambda: None
    runner._release_owned_inputs = lambda: None
    return runner


def test_platform16_failure_keeps_platform16_as_next_collection_stage():
    runner = _collection_runner((95, 54), "platform16")
    runner._enter_platform16 = lambda: False

    assert runner._run_rednose_new_v5_collection() is False
    assert runner._collection_stage == "platform16"


def test_platform27_failure_keeps_platform27_as_next_collection_stage():
    runner = _collection_runner((95, 47), "platform27")
    runner._enter_platform27 = lambda: False

    assert runner._run_rednose_new_v5_collection() is False
    assert runner._collection_stage == "platform27"


def test_platform16_position_skips_platform1415_and_platform16_actions():
    runner = _collection_runner((95, 47), "platform1415")
    calls = []
    runner._enter_platform1415 = lambda: calls.append("1415") or True
    runner._enter_platform16 = lambda: calls.append("16") or True
    runner._enter_platform27 = lambda: calls.append("27") or True
    runner._finish_platform27_and_return_floor2 = lambda: calls.append("return") or True

    assert runner._run_rednose_new_v5_collection() is True
    assert calls == ["27", "return"]


def test_platform27_position_finishes_collection_without_previous_platform_actions():
    runner = _collection_runner((91, 50), "platform1415")
    calls = []
    runner._enter_platform1415 = lambda: calls.append("1415") or True
    runner._enter_platform16 = lambda: calls.append("16") or True
    runner._enter_platform27 = lambda: calls.append("27") or True
    runner._finish_platform27_and_return_floor2 = lambda: calls.append("return") or True

    assert runner._run_rednose_new_v5_collection() is True
    assert calls == ["return"]


def test_platform1415_does_not_start_x_movement_from_floor1():
    runner = _collection_runner((95, 76), "platform1415")
    moves = []
    runner._move_to_target_v5 = lambda *_args, **_kwargs: moves.append(True) or True

    assert runner._enter_platform1415() is False
    assert moves == []
