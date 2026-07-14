# 미니맵 로컬 위치를 전역 지도 위치와 추적 상태로 갱신하는 스캐너 테스트
import numpy as np

from core.navigation.world_map import WorldPoint
from core.sensing.world_position_scanner import WorldPositionScanner


class FakeTracker:
    def __init__(self):
        self.result = None
        self.viewport_size = (80.0, 40.0)

    def update(self, frame, local):
        self.result = type("R", (), {
            "state": "confirmed",
            "origin": WorldPoint(100, 40),
        })()
        return self.result

    def character_world(self, local):
        return WorldPoint(local.x + 100, local.y + 40)


def test_scan_once_updates_world_position():
    scanner = WorldPositionScanner(
        capture_fn=lambda region: np.zeros((20, 40, 3), dtype=np.uint8),
        region_fn=lambda: {"left": 0, "top": 0, "width": 40, "height": 20},
        local_position_fn=lambda: (10, 5),
        tracker=FakeTracker(),
        interval_sec=0.01,
    )

    scanner.scan_once()

    assert scanner.position() == (110, 45)
    assert scanner.state() == "confirmed"
    assert scanner.viewport() == ((100, 40), (80.0, 40.0))


def test_scan_once_without_local_position_keeps_unavailable():
    scanner = WorldPositionScanner(
        capture_fn=lambda region: None,
        region_fn=lambda: {},
        local_position_fn=lambda: None,
        tracker=FakeTracker(),
    )

    assert scanner.scan_once() is None
    assert scanner.position() is None
    assert scanner.state() == "unavailable"


def test_local_position_loss_downgrades_confirmed_to_estimated():
    positions = iter([(10, 5), None])
    scanner = WorldPositionScanner(
        capture_fn=lambda region: np.zeros((20, 40, 3), dtype=np.uint8),
        region_fn=lambda: {},
        local_position_fn=lambda: next(positions),
        tracker=FakeTracker(),
    )

    assert scanner.scan_once() == (110, 45)
    assert scanner.scan_once() is None
    assert scanner.position() == (110, 45)
    assert scanner.state() == "estimated"
