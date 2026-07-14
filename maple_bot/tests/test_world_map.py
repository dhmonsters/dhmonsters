"""전역 좌표 및 지도 데이터 모델을 검증하는 테스트."""

import math

import pytest

from core.navigation.world_map import (
    ActionSpec,
    NavEdge,
    NavNode,
    WorldPoint,
    calibrate_two_points,
)


def test_two_point_calibration_round_trip():
    cal = calibrate_two_points(
        WorldPoint(100, 50), WorldPoint(500, 250),
        WorldPoint(10, 5), WorldPoint(210, 105),
    )
    assert math.isclose(cal.scale, 2.0)
    assert cal.local_to_world(WorldPoint(10, 5)) == WorldPoint(100, 50)
    assert cal.world_to_local(WorldPoint(500, 250)) == WorldPoint(210, 105)


def test_calibration_rejects_short_or_rotated_pair():
    with pytest.raises(ValueError, match="기준점 거리"):
        calibrate_two_points(
            WorldPoint(1, 1), WorldPoint(2, 2),
            WorldPoint(1, 1), WorldPoint(1.1, 1.1),
        )
    with pytest.raises(ValueError, match="방향"):
        calibrate_two_points(
            WorldPoint(0, 0), WorldPoint(100, 0),
            WorldPoint(0, 0), WorldPoint(0, 100),
        )


def test_action_and_edge_validation():
    action = ActionSpec("up", 0.2, 1, 0.0, 1.0)
    node = NavNode("n1", "action", 20, 30, 4, "포탈", action)
    edge = NavEdge("e1", "n0", "n1", True, "walk")
    assert node.action.key == "up"
    assert edge.traversal == "walk"
    with pytest.raises(ValueError, match="repeat"):
        ActionSpec("up", 0.2, 0, 0.0, 1.0)


def test_waypoint_rejects_action_spec():
    action = ActionSpec("up", 0.2, 1, 0.0, 1.0)
    with pytest.raises(ValueError, match="action 노드"):
        NavNode("n1", "waypoint", 20, 30, action=action)
