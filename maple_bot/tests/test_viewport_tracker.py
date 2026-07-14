# 미니맵 뷰포트의 전역 위치 추적과 무기한 추정을 검증하는 테스트
import numpy as np

from core.navigation.viewport_tracker import ViewportTracker
from core.navigation.world_map import Calibration, WorldPoint


def test_confirmed_match_sets_world_origin():
    matches = iter([(WorldPoint(100, 40), 0.92, (0.0, 0.0, 1.0))])
    tracker = ViewportTracker(
        np.zeros((300, 600), dtype=np.uint8),
        Calibration(2.0, 0.0, 0.0),
        match_fn=lambda *_: next(matches),
    )

    result = tracker.update(
        np.zeros((50, 100, 3), dtype=np.uint8), WorldPoint(20, 10)
    )

    assert result.state == "confirmed"
    assert tracker.character_world(WorldPoint(20, 10)) == WorldPoint(140, 60)
    assert tracker.viewport_size == (200.0, 100.0)


def test_failed_global_match_uses_frame_shift_without_timeout():
    matches = iter([
        (WorldPoint(100, 40), 0.92, (0.0, 0.0, 1.0)),
        (WorldPoint(0, 0), 0.10, (-3.0, 0.0, 0.8)),
        (WorldPoint(0, 0), 0.10, (0.0, 0.0, 0.0)),
    ])
    tracker = ViewportTracker(
        np.zeros((300, 600), dtype=np.uint8),
        Calibration(2.0, 0.0, 0.0),
        match_fn=lambda *_: next(matches),
    )
    frame = np.zeros((50, 100, 3), dtype=np.uint8)

    tracker.update(frame, WorldPoint(20, 10))
    assert tracker.update(frame, WorldPoint(20, 10)).origin == WorldPoint(106, 40)
    result = tracker.update(frame, WorldPoint(20, 10))

    assert result.origin == WorldPoint(112, 40)
    assert result.state == "estimated"


def test_confirmed_recovery_limits_origin_correction():
    matches = iter([
        (WorldPoint(0, 0), 0.92, (0.0, 0.0, 1.0)),
        (WorldPoint(100, 0), 0.92, (0.0, 0.0, 1.0)),
    ])
    tracker = ViewportTracker(
        np.zeros((300, 600), dtype=np.uint8),
        Calibration(1.0, 0.0, 0.0),
        match_fn=lambda *_: next(matches),
    )
    frame = np.zeros((50, 100, 3), dtype=np.uint8)

    tracker.update(frame, WorldPoint(0, 0))
    result = tracker.update(frame, WorldPoint(0, 0))

    assert result.origin == WorldPoint(12, 0)
    assert result.state == "confirmed"
