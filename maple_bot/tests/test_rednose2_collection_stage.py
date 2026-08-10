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
