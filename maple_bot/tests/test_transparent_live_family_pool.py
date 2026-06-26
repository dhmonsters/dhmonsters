# 투명 퍼즐 live family pool의 sliding Viterbi 후보 생성을 검증합니다.
import unittest

import numpy as np

from core.vision.transparent_live_family_pool import TransparentLiveFamilyPool


class TransparentLiveFamilyPoolTests(unittest.TestCase):
    def test_emits_named_viterbi_families_after_enough_frames(self):
        pool = TransparentLiveFamilyPool(window=4, min_frames=3)
        gray = np.zeros((40, 40), dtype=np.float32)

        pool.update(
            0,
            candidates=[],
            gray_frame=gray,
            white_anchor=(5.0, 10.0),
        )
        first = pool.update(
            1,
            candidates=[(8.0, 10.0, 0.9, 12.0, 12.0), (30.0, 30.0, 0.9, 12.0, 12.0)],
            gray_frame=gray,
        )
        self.assertEqual(first.points, {})

        pool.update(
            2,
            candidates=[(11.0, 10.0, 0.9, 12.0, 12.0), (28.0, 30.0, 0.9, 12.0, 12.0)],
            gray_frame=gray,
        )
        decision = pool.update(
            3,
            candidates=[(14.0, 10.0, 0.9, 12.0, 12.0), (26.0, 30.0, 0.9, 12.0, 12.0)],
            gray_frame=gray,
        )

        self.assertIn("balanced_viterbi_center_mild_state_mild", decision.points)
        self.assertIn("strict_transition_viterbi_center_mild_state_mild", decision.points)
        self.assertEqual(decision.points["strict_transition_viterbi_center_mild_state_mild"], (14.0, 10.0))

    def test_strict_family_prefers_smooth_path_over_far_score_spike(self):
        pool = TransparentLiveFamilyPool(window=4, min_frames=3)
        gray = np.zeros((50, 50), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(5.0, 5.0))
        pool.update(
            1,
            candidates=[(8.0, 5.0, 0.8, 12.0, 12.0), (35.0, 35.0, 0.99, 12.0, 12.0)],
            gray_frame=gray,
        )
        pool.update(
            2,
            candidates=[(11.0, 5.0, 0.8, 12.0, 12.0), (36.0, 35.0, 0.99, 12.0, 12.0)],
            gray_frame=gray,
        )
        decision = pool.update(
            3,
            candidates=[(14.0, 5.0, 0.8, 12.0, 12.0), (37.0, 35.0, 0.99, 12.0, 12.0)],
            gray_frame=gray,
        )

        self.assertEqual(decision.points["strict_transition_viterbi_center_mild_state_mild"], (14.0, 5.0))

    def test_balanced_family_can_follow_motion_anomaly_over_background_motion(self):
        pool = TransparentLiveFamilyPool(window=4, min_frames=3)
        gray = np.zeros((50, 50), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(5.0, 5.0))
        pool.update(
            1,
            candidates=[
                (8.0, 5.0, 0.8, 12.0, 12.0),
                (20.0, 20.0, 0.8, 12.0, 12.0),
                (30.0, 10.0, 0.8, 12.0, 12.0),
                (35.0, 30.0, 0.8, 12.0, 12.0),
            ],
            gray_frame=gray,
        )
        pool.update(
            2,
            candidates=[
                (9.0, 5.0, 0.8, 12.0, 12.0),
                (16.0, 5.0, 0.8, 12.0, 12.0),
                (31.0, 10.0, 0.8, 12.0, 12.0),
                (36.0, 30.0, 0.8, 12.0, 12.0),
            ],
            gray_frame=gray,
        )
        decision = pool.update(
            3,
            candidates=[
                (10.0, 5.0, 0.8, 12.0, 12.0),
                (24.0, 5.0, 0.8, 12.0, 12.0),
                (32.0, 10.0, 0.8, 12.0, 12.0),
                (37.0, 30.0, 0.8, 12.0, 12.0),
            ],
            gray_frame=gray,
        )

        self.assertEqual(decision.points["balanced_viterbi_center_mild_state_mild"], (24.0, 5.0))

    def test_bg_split_family_keeps_hidden_target_center_through_merge(self):
        pool = TransparentLiveFamilyPool(window=5, min_frames=2)
        gray = np.zeros((80, 120), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(0.0, 0.0))
        pool.update(
            1,
            candidates=[(20.0, 0.0, 0.9, 20.0, 20.0)],
            gray_frame=gray,
        )
        merged = pool.update(
            2,
            candidates=[(10.0, 0.0, 0.95, 100.0, 50.0)],
            gray_frame=gray,
        )
        split = pool.update(
            3,
            candidates=[
                (60.0, 0.0, 0.7, 20.0, 20.0),
                (10.0, 0.0, 0.95, 20.0, 20.0),
            ],
            gray_frame=gray,
        )

        family = "bg_split_viterbi_center_mild_state_mild"
        self.assertIn(family, merged.points)
        self.assertEqual(merged.points[family], (40.0, 0.0))
        self.assertEqual(split.points[family], (60.0, 0.0))

    def test_merge_context_family_aliases_bg_split_path_for_selector_source_feature(self):
        pool = TransparentLiveFamilyPool(window=5, min_frames=2)
        gray = np.zeros((80, 120), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(0.0, 0.0))
        pool.update(
            1,
            candidates=[(20.0, 0.0, 0.9, 20.0, 20.0)],
            gray_frame=gray,
        )
        decision = pool.update(
            2,
            candidates=[(10.0, 0.0, 0.95, 100.0, 50.0)],
            gray_frame=gray,
        )

        split_family = "bg_split_viterbi_center_mild_state_mild"
        merge_family = "merge_context_center_mild_state_mild"
        self.assertIn(split_family, decision.points)
        self.assertIn(merge_family, decision.points)
        self.assertEqual(decision.points[merge_family], decision.points[split_family])

    def test_state_coast_family_predicts_through_wrong_merge_center(self):
        pool = TransparentLiveFamilyPool(window=5, min_frames=3)
        gray = np.zeros((80, 140), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(0.0, 0.0))
        pool.update(1, candidates=[(10.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        pool.update(2, candidates=[(20.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        decision = pool.update(
            3,
            candidates=[(70.0, 0.0, 0.95, 120.0, 40.0)],
            gray_frame=gray,
        )

        self.assertEqual(
            decision.points["balanced_viterbi_center_mild_state_coast"],
            (30.0, 0.0),
        )
        self.assertEqual(
            decision.points["balanced_viterbi_center_mild_offset_coast"],
            (30.0, 0.0),
        )

    def test_state_coast_family_keeps_normal_current_detection(self):
        pool = TransparentLiveFamilyPool(window=5, min_frames=3)
        gray = np.zeros((80, 140), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(0.0, 0.0))
        pool.update(1, candidates=[(10.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        pool.update(2, candidates=[(20.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        decision = pool.update(
            3,
            candidates=[(30.0, 0.0, 0.95, 20.0, 20.0)],
            gray_frame=gray,
        )

        self.assertEqual(
            decision.points["balanced_viterbi_center_mild_state_coast"],
            (30.0, 0.0),
        )
        self.assertEqual(
            decision.points["balanced_viterbi_center_mild_offset_coast"],
            (30.0, 0.0),
        )

    def test_phase_catalog_live_family_removes_periodic_background_candidate(self):
        pool = TransparentLiveFamilyPool(
            window=6,
            min_frames=2,
            catalog_min_lag=3,
            catalog_max_lag=5,
        )
        gray = np.zeros((80, 140), dtype=np.float32)

        pool.update(
            0,
            candidates=[(50.0, 0.0, 0.9, 20.0, 20.0)],
            gray_frame=gray,
            white_anchor=(100.0, 0.0),
        )
        pool.update(1, candidates=[(60.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        pool.update(2, candidates=[(70.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        pool.update(3, candidates=[(80.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        pool.update(4, candidates=[(50.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        decision = pool.update(
            5,
            candidates=[
                (60.0, 0.0, 0.95, 20.0, 20.0),
                (40.0, 0.0, 0.80, 20.0, 20.0),
            ],
            gray_frame=gray,
        )

        self.assertEqual(
            decision.points["phase_catalog_live_center_mild_state_mild"],
            (40.0, 0.0),
        )

    def test_reset_clears_history(self):
        pool = TransparentLiveFamilyPool(window=3, min_frames=2)
        gray = np.zeros((20, 20), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(1.0, 1.0))
        pool.update(1, candidates=[(2.0, 1.0, 0.9, 8.0, 8.0)], gray_frame=gray)
        pool.reset()
        decision = pool.update(2, candidates=[(3.0, 1.0, 0.9, 8.0, 8.0)], gray_frame=gray)

        self.assertEqual(decision.points, {})


if __name__ == "__main__":
    unittest.main()
