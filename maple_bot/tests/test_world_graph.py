# 등록된 전역 이동 간선만 사용하는 최단 경로 탐색을 검증하는 테스트
from core.navigation.world_graph import shortest_edge_path
from core.navigation.world_map import NavEdge


def test_shortest_path_uses_registered_edges_only():
    edges = (
        NavEdge("e1", "a", "b", True, "walk"),
        NavEdge("e2", "b", "c", True, "ladder", {"x": 50}),
    )

    assert [edge.id for edge in shortest_edge_path(edges, "a", "c")] == ["e1", "e2"]
    assert shortest_edge_path(edges, "a", "outside") is None


def test_reverse_ladder_path_flips_direction():
    edge = NavEdge("e1", "low", "high", True, "ladder", {
        "x": 50,
        "y_top": 20,
        "y_bot": 80,
        "direction": "up",
        "exit_side": "left",
        "grab_side": "auto",
        "jump_offset": 8,
    })

    reverse = shortest_edge_path((edge,), "high", "low")[0]

    assert (reverse.from_id, reverse.to_id) == ("high", "low")
    assert reverse.ladder["direction"] == "down"
