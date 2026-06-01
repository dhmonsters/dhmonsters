# FloorJudge — Y좌표로 층 판별 + 도착확인 폐루프 (A "2초 무조건 등반" 문제 해결)
import pytest
from core.navigation.floor_judge import FloorJudge, Floor


FLOORS = [
    Floor(name="1층", y_min=115, y_max=136),
    Floor(name="2층", y_min=66, y_max=83),
]


def test_judge_floor_by_y():
    fj = FloorJudge(FLOORS)
    assert fj.floor_at(y=125).name == "1층"
    assert fj.floor_at(y=75).name == "2층"


def test_judge_returns_none_between_floors():
    """층 사이(밧줄 중간)는 None — 아직 도착 안 함."""
    fj = FloorJudge(FLOORS)
    assert fj.floor_at(y=100) is None


def test_is_arrived_true_when_in_target_zone():
    fj = FloorJudge(FLOORS)
    # 2층(66~83) 목표, 현재 y=75 → 도착
    assert fj.is_arrived(target_floor=FLOORS[1], y=75) is True


def test_is_arrived_false_when_not_yet():
    fj = FloorJudge(FLOORS)
    # 2층 목표인데 아직 밧줄 중간(y=100) → 미도착 (A의 오판정 방지)
    assert fj.is_arrived(target_floor=FLOORS[1], y=100) is False


def test_is_arrived_tolerance():
    """경계 ±tol 허용 (착지 직후 미세 흔들림)."""
    fj = FloorJudge(FLOORS, tolerance=3)
    assert fj.is_arrived(target_floor=FLOORS[1], y=85) is True   # 83+2 허용
    assert fj.is_arrived(target_floor=FLOORS[1], y=90) is False  # 너무 벗어남


def test_fall_detection():
    """현재 층이 출발 층보다 아래(낙사)면 감지."""
    fj = FloorJudge(FLOORS)
    # 2층(목표) 가려다 1층(y=125)에 있음 → 목표 아님
    assert fj.is_arrived(target_floor=FLOORS[1], y=125) is False
    assert fj.floor_at(125).name == "1층"
