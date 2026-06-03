# tests/test_floor_extract.py
# move 블록 pos_y 클러스터링 → 층 밴드 생성 검증
from core.navigation.floor_extract import floors_from_route


def test_clusters_move_blocks_into_floors():
    route = [
        {"type": "move", "pos_x": 10, "pos_y": 100, "start_x": 10, "end_x": 50},
        {"type": "move", "pos_x": 20, "pos_y": 103, "start_x": 20, "end_x": 60},  # 100과 같은 층
        {"type": "ladder", "ladder_x": 30, "y_top": 50, "y_bot": 100},
        {"type": "move", "pos_x": 15, "pos_y": 50, "start_x": 15, "end_x": 55},   # 위층
    ]
    floors = floors_from_route(route, band=12)
    assert len(floors) == 2
    # 정렬: Y 작은(위층)이 먼저인지 여부 무관 — 두 밴드가 100대/50대로 분리
    bands = sorted((f.y_min, f.y_max) for f in floors)
    assert bands[0][0] <= 50 <= bands[0][1]
    assert bands[1][0] <= 100 <= bands[1][1]


def test_ignores_unplaced_and_non_move():
    route = [
        {"type": "move", "pos_x": -1, "pos_y": -1, "start_x": 0, "end_x": 0},  # 미배치
        {"type": "attack", "skill_key": "a"},
    ]
    assert floors_from_route(route) == []


def test_names_are_unique():
    route = [
        {"type": "move", "pos_x": 1, "pos_y": 40, "start_x": 1, "end_x": 5},
        {"type": "move", "pos_x": 1, "pos_y": 120, "start_x": 1, "end_x": 5},
    ]
    names = [f.name for f in floors_from_route(route)]
    assert len(names) == len(set(names))
