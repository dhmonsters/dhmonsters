# 맵 그래프 구성·최단경로·기대층 순수 함수 검증
from core.navigation.map_graph import expected_floor, build_graph, shortest_path


class FakeFloor:
    def __init__(self, name): self.name = name


class FakeJudge:
    """y 밴드 → 층. bands=[(name, ymin, ymax)]."""
    def __init__(self, bands): self.bands = bands
    def floor_at(self, y):
        for name, lo, hi in self.bands:
            if lo <= y <= hi:
                return FakeFloor(name)
        return None


def _judge():
    # 4층(위, y작음) ~ 1층(아래, y큼)
    return FakeJudge([("4층", 0, 49), ("3층", 50, 99), ("2층", 100, 149), ("1층", 150, 199)])


def _floors():
    return [FakeFloor("1층"), FakeFloor("2층"), FakeFloor("3층"), FakeFloor("4층")]


def test_expected_floor_from_pos_and_ladder():
    j = _judge()
    assert expected_floor({"type": "attack", "pos_y": 170}, j) == "1층"
    assert expected_floor({"type": "ladder", "y_bot": 170, "y_top": 120}, j) == "1층"  # 아래층 기준
    assert expected_floor({"type": "attack", "pos_y": -1}, j) is None                  # 미배치
    assert expected_floor({"type": "attack", "pos_y": 999}, j) is None                 # 층 밖


def test_build_graph_bidirectional_ladders():
    j = _judge()
    route = [
        {"type": "ladder", "ladder_x": 40, "y_bot": 170, "y_top": 120},   # 1↔2
        {"type": "ladder", "ladder_x": 60, "y_bot": 120, "y_top": 70},    # 2↔3
        {"type": "ladder", "ladder_x": 80, "y_bot": 70, "y_top": 30},     # 3↔4
        {"type": "attack", "pos_y": 170},                                  # 간선 아님
    ]
    g = build_graph(_floors(), route, j)
    assert {e["to"] for e in g["1층"]} == {"2층"}
    assert {e["to"] for e in g["2층"]} == {"1층", "3층"}
    assert {e["to"] for e in g["4층"]} == {"3층"}
    up = [e for e in g["1층"] if e["to"] == "2층"][0]
    assert up["via"]["type"] == "ladder" and up["via"]["ladder_dir"] == "up"
    down = [e for e in g["2층"] if e["to"] == "1층"][0]
    assert down["via"]["ladder_dir"] == "down"


def test_build_graph_skips_out_of_range_and_selfloop():
    j = _judge()
    route = [
        {"type": "ladder", "ladder_x": 1, "y_bot": 999, "y_top": 120},   # 아래층 None → skip
        {"type": "ladder", "ladder_x": 2, "y_bot": 160, "y_top": 170},   # 둘 다 1층 → 자기루프 skip
    ]
    g = build_graph(_floors(), route, j)
    assert all(len(v) == 0 for v in g.values())


def test_shortest_path():
    j = _judge()
    route = [
        {"type": "ladder", "ladder_x": 40, "y_bot": 170, "y_top": 120},   # 1↔2
        {"type": "ladder", "ladder_x": 60, "y_bot": 120, "y_top": 70},    # 2↔3
        {"type": "ladder", "ladder_x": 80, "y_bot": 70, "y_top": 30},     # 3↔4
    ]
    g = build_graph(_floors(), route, j)
    path = shortest_path(g, "1층", "4층")
    assert [e["ladder_x"] for e in path] == [40, 60, 80]   # 1→2→3→4 사다리 순
    assert all(e["ladder_dir"] == "up" for e in path)
    assert shortest_path(g, "2층", "2층") == []             # 같은 층
    assert shortest_path(g, "1층", "없는층") is None         # 경로 없음
