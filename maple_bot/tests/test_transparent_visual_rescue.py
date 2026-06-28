# 투명 퍼즐 live visual rescue 후보 생성기를 검증합니다.
import unittest

import numpy as np

from core.vision.transparent_visual_rescue import (
    TransparentVisualRescueTracker,
    VisualBeamTracker,
    visual_box_points_for_candidates,
    visual_rank_scores_for_candidates,
)


class TransparentVisualRescueTests(unittest.TestCase):
    def test_visual_rank_scores_prefer_center_residual(self):
        diff = np.zeros((60, 60), dtype=np.float32)
        diff[18:23, 18:23] = 100.0
        diff[42:47, 42:47] = 20.0

        scores = visual_rank_scores_for_candidates(
            diff,
            [[20, 20, 0.4, 16, 16], [44, 44, 0.9, 16, 16]],
            inner_radius=4,
            outer_radius=10,
        )

        self.assertGreater(scores[0], scores[1])
        self.assertAlmostEqual(scores[0], 10.0)

    def test_visual_box_points_can_pick_residual_inside_candidate_box(self):
        diff = np.zeros((80, 80), dtype=np.float32)
        diff[28:33, 18:23] = 120.0

        points = visual_box_points_for_candidates(
            diff,
            [[40, 40, 0.6, 48, 48]],
            inner_radius=4,
        )

        self.assertEqual(len(points), 1)
        self.assertLess(points[0][0], 40.0)
        self.assertLess(points[0][1], 40.0)

    def test_visual_beam_uses_visual_score_to_choose_branch(self):
        beam = VisualBeamTracker(
            keep=8,
            branch=2,
            rescue_prediction_gate=50.0,
            track_prediction_gate=35.0,
            continuity_weight=6.0,
            track_weight=1.0,
            detection_weight=0.0,
            visual_weight=1.5,
        )

        beam.update([[0, 0, 0.9], [90, 0, 0.95]], track_point=(0, 0))
        beam.update([[10, 0, 0.9], [90, 0, 0.95]], track_point=(10, 0))
        first = beam.update(
            [[20, 0, 0.4], [15, 0, 0.95]],
            visual_scores=[10.0, 0.0],
            track_point=None,
        )
        second = beam.update(
            [[30, 0, 0.4], [18, 0, 0.95]],
            visual_scores=[10.0, 0.0],
            track_point=None,
        )

        self.assertEqual(first.point, (20.0, 0.0))
        self.assertEqual(second.point, (30.0, 0.0))
        self.assertEqual(second.source, "visual_beam")

    def test_tracker_returns_visual_point_after_periodic_diff_is_available(self):
        tracker = TransparentVisualRescueTracker(period_hint=3)
        base = np.zeros((60, 60), dtype=np.uint8)
        target = base.copy()
        target[18:23, 18:23] = 180
        decoy = base.copy()
        decoy[42:47, 42:47] = 40

        tracker.update(base, [[10, 10, 0.9, 12, 12]], white_anchor=(30, 30))
        tracker.update(base, [[11, 10, 0.9, 12, 12]], white_anchor=(30, 30))
        tracker.update(base, [[12, 10, 0.9, 12, 12]], white_anchor=None)
        decision = tracker.update(
            np.maximum(target, decoy),
            [[20, 20, 0.4, 16, 16], [44, 44, 0.9, 16, 16]],
            white_anchor=None,
            track_point=(44, 44),
        )

        self.assertEqual(decision.point, (20.0, 20.0))
        self.assertTrue(decision.available)


if __name__ == "__main__":
    unittest.main()
