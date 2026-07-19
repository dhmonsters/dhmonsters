# 투명도형의 위치와 박스 형태를 함께 잇는 시간축 후보 가족을 검증합니다.
import unittest

from core.vision.transparent_kinematic_shape import (
    TransparentKinematicBeamTracker,
    TransparentKinematicShapeTracker,
)


class TransparentKinematicShapeTrackerTest(unittest.TestCase):
    def test_prefers_shape_consistent_candidate_over_closer_shape_mismatch(self) -> None:
        tracker = TransparentKinematicShapeTracker()
        tracker.update(
            [(100.0, 100.0, 0.99, 20.0, 20.0)],
            white_anchor=(100.0, 100.0),
        )

        point = tracker.update([
            (110.0, 100.0, 0.20, 20.0, 20.0),
            (102.0, 100.0, 0.99, 60.0, 10.0),
        ])

        self.assertEqual(point, (110.0, 100.0))
        self.assertEqual(tracker.last_debug["reason"], "shape_motion_cost")

    def test_visible_anchor_updates_motion_before_target_fades(self) -> None:
        tracker = TransparentKinematicShapeTracker(velocity_alpha=0.5)
        tracker.update(
            [(100.0, 100.0, 0.99, 20.0, 20.0)],
            white_anchor=(100.0, 100.0),
        )
        tracker.update(
            [(110.0, 100.0, 0.99, 20.0, 20.0)],
            white_anchor=(110.0, 100.0),
        )

        point = tracker.update([
            (115.0, 100.0, 0.20, 20.0, 20.0),
            (109.0, 100.0, 0.99, 20.0, 20.0),
        ])

        self.assertEqual(point, (115.0, 100.0))

    def test_reset_forgets_previous_identity(self) -> None:
        tracker = TransparentKinematicShapeTracker()
        tracker.update(
            [(100.0, 100.0, 0.99, 20.0, 20.0)],
            white_anchor=(100.0, 100.0),
        )

        tracker.reset()

        self.assertIsNone(tracker.last_point)
        self.assertEqual(tracker.velocity, (0.0, 0.0))


class TransparentKinematicBeamTrackerTest(unittest.TestCase):
    def test_visible_anchor_updates_velocity_without_discarding_history(self) -> None:
        tracker = TransparentKinematicBeamTracker(velocity_alpha=0.5)
        tracker.update([(0.0, 0.0, 0.99, 20.0, 20.0)], white_anchor=(0.0, 0.0))

        tracker.update([(10.0, 0.0, 0.99, 20.0, 20.0)], white_anchor=(10.0, 0.0))

        self.assertEqual(tracker.last_debug["velocity"], (5.0, 0.0))

    def test_keeps_alternative_paths_instead_of_committing_one_candidate(self) -> None:
        tracker = TransparentKinematicBeamTracker(width=4, branch=3)
        tracker.update([(0.0, 0.0, 0.99, 20.0, 20.0)], white_anchor=(0.0, 0.0))

        tracker.update([
            (10.0, 0.0, 0.20, 20.0, 20.0),
            (0.0, 10.0, 0.90, 20.0, 20.0),
            (-10.0, 0.0, 0.50, 20.0, 20.0),
        ])

        self.assertGreaterEqual(len(tracker.hypothesis_points), 3)
        self.assertIn((10.0, 0.0), tracker.hypothesis_points)
        self.assertIn((0.0, 10.0), tracker.hypothesis_points)

    def test_reset_forgets_all_pending_paths(self) -> None:
        tracker = TransparentKinematicBeamTracker()
        tracker.update([(0.0, 0.0, 0.99, 20.0, 20.0)], white_anchor=(0.0, 0.0))

        tracker.reset()

        self.assertEqual(tracker.hypothesis_points, ())


if __name__ == "__main__":
    unittest.main()
