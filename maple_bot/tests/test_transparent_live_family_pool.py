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

    def test_raw_candidate_families_emit_rank_and_continuity_paths(self):
        pool = TransparentLiveFamilyPool(
            window=4,
            min_frames=2,
            raw_rank_families=2,
            raw_continuity_families=2,
            raw_max_step_px=30.0,
        )
        gray = np.zeros((50, 140), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(0.0, 0.0))
        pool.update(
            1,
            candidates=[
                (10.0, 0.0, 0.9, 12.0, 12.0),
                (100.0, 0.0, 0.8, 12.0, 12.0),
            ],
            gray_frame=gray,
        )
        decision = pool.update(
            2,
            candidates=[
                (98.0, 0.0, 0.95, 12.0, 12.0),
                (12.0, 0.0, 0.7, 12.0, 12.0),
            ],
            gray_frame=gray,
        )

        self.assertEqual(
            decision.points["raw_candidate_rank0_center_mild_state_mild"],
            (98.0, 0.0),
        )
        self.assertEqual(
            decision.points["raw_candidate_rank1_center_mild_state_mild"],
            (12.0, 0.0),
        )
        self.assertEqual(
            decision.points["raw_candidate_cont0_center_mild_state_mild"],
            (12.0, 0.0),
        )
        self.assertEqual(
            decision.points["raw_candidate_cont1_center_mild_state_mild"],
            (98.0, 0.0),
        )

    def test_raw_candidate_box_offset_predicts_inside_merge_box(self):
        pool = TransparentLiveFamilyPool(
            window=5,
            min_frames=2,
            raw_rank_families=0,
            raw_continuity_families=1,
            raw_max_step_px=90.0,
        )
        gray = np.zeros((80, 160), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(0.0, 0.0))
        pool.update(1, candidates=[(10.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        pool.update(2, candidates=[(20.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        decision = pool.update(
            3,
            candidates=[(70.0, 0.0, 0.95, 120.0, 40.0)],
            gray_frame=gray,
        )

        self.assertEqual(
            decision.points["raw_candidate_cont0_box_offset_state_mild"],
            (30.0, 0.0),
        )

    def test_raw_candidate_box_offset_keeps_normal_candidate_center(self):
        pool = TransparentLiveFamilyPool(
            window=5,
            min_frames=2,
            raw_rank_families=0,
            raw_continuity_families=1,
            raw_max_step_px=90.0,
        )
        gray = np.zeros((80, 160), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(0.0, 0.0))
        pool.update(1, candidates=[(10.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        pool.update(2, candidates=[(20.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        decision = pool.update(
            3,
            candidates=[(30.0, 0.0, 0.95, 20.0, 20.0)],
            gray_frame=gray,
        )

        self.assertEqual(
            decision.points["raw_candidate_cont0_box_offset_state_mild"],
            (30.0, 0.0),
        )

    def test_raw_candidate_mht_prefers_smooth_branch_over_far_high_score(self):
        pool = TransparentLiveFamilyPool(
            window=5,
            min_frames=3,
            raw_rank_families=0,
            raw_continuity_families=0,
            enable_raw_mht=True,
        )
        gray = np.zeros((80, 160), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(0.0, 0.0))
        pool.update(
            1,
            candidates=[
                (100.0, 0.0, 0.99, 20.0, 20.0),
                (10.0, 0.0, 0.40, 20.0, 20.0),
            ],
            gray_frame=gray,
        )
        pool.update(
            2,
            candidates=[
                (100.0, 0.0, 0.99, 20.0, 20.0),
                (20.0, 0.0, 0.40, 20.0, 20.0),
            ],
            gray_frame=gray,
        )
        decision = pool.update(
            3,
            candidates=[
                (100.0, 0.0, 0.99, 20.0, 20.0),
                (30.0, 0.0, 0.40, 20.0, 20.0),
            ],
            gray_frame=gray,
        )

        self.assertEqual(
            decision.points["raw_candidate_mht_center_mild_state_mild"],
            (30.0, 0.0),
        )

    def test_raw_candidate_mht_is_disabled_by_default(self):
        pool = TransparentLiveFamilyPool(
            window=5,
            min_frames=3,
            raw_rank_families=0,
            raw_continuity_families=0,
        )
        gray = np.zeros((80, 160), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(0.0, 0.0))
        pool.update(1, candidates=[(10.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        pool.update(2, candidates=[(20.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        decision = pool.update(
            3,
            candidates=[(30.0, 0.0, 0.9, 20.0, 20.0)],
            gray_frame=gray,
        )

        self.assertNotIn("raw_candidate_mht_center_mild_state_mild", decision.points)

    def test_raw_candidate_beam_keeps_smooth_low_score_branch(self):
        pool = TransparentLiveFamilyPool(
            window=5,
            min_frames=3,
            raw_rank_families=0,
            raw_continuity_families=0,
            raw_beam_families=4,
        )
        gray = np.zeros((80, 160), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(0.0, 0.0))
        pool.update(
            1,
            candidates=[
                (100.0, 0.0, 0.99, 20.0, 20.0),
                (10.0, 0.0, 0.40, 20.0, 20.0),
            ],
            gray_frame=gray,
        )
        pool.update(
            2,
            candidates=[
                (100.0, 0.0, 0.99, 20.0, 20.0),
                (20.0, 0.0, 0.40, 20.0, 20.0),
            ],
            gray_frame=gray,
        )
        decision = pool.update(
            3,
            candidates=[
                (100.0, 0.0, 0.99, 20.0, 20.0),
                (30.0, 0.0, 0.40, 20.0, 20.0),
            ],
            gray_frame=gray,
        )

        self.assertIn(
            (30.0, 0.0),
            [
                decision.points[family]
                for family in decision.points
                if family.startswith("raw_candidate_beam")
            ],
        )

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

    def test_expensive_mht_and_phase_families_can_be_disabled(self):
        pool = TransparentLiveFamilyPool(
            window=5,
            min_frames=2,
            enable_bg_mht=False,
            enable_phase_catalog=False,
        )
        gray = np.zeros((80, 120), dtype=np.float32)

        pool.update(0, candidates=[], gray_frame=gray, white_anchor=(0.0, 0.0))
        pool.update(1, candidates=[(20.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray)
        decision = pool.update(
            2,
            candidates=[(10.0, 0.0, 0.95, 100.0, 50.0)],
            gray_frame=gray,
        )

        self.assertNotIn("bg_split_viterbi_center_mild_state_mild", decision.points)
        self.assertNotIn("merge_context_center_mild_state_mild", decision.points)
        self.assertNotIn("phase_catalog_live_center_mild_state_mild", decision.points)

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
        self.assertNotIn("phase_catalog_mht_center_mild_state_mild", decision.points)

    def test_phase_catalog_mht_family_removes_periodic_background_candidate(self):
        pool = TransparentLiveFamilyPool(
            window=6,
            min_frames=2,
            catalog_min_lag=3,
            catalog_max_lag=5,
            enable_phase_mht=True,
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
            decision.points["phase_catalog_mht_center_mild_state_mild"],
            (40.0, 0.0),
        )

    def test_guarded_decal_identity_is_disabled_by_default(self):
        pool = TransparentLiveFamilyPool(
            window=8,
            min_frames=3,
            catalog_min_lag=3,
            catalog_max_lag=3,
        )
        gray = np.zeros((80, 180), dtype=np.float32)

        pool.update(0, candidates=[(100.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray, white_anchor=(0.0, 0.0))
        for frame, bg_x, target_x in (
            (1, 100.0, 10.0),
            (2, 110.0, 20.0),
            (3, 120.0, 30.0),
            (4, 100.0, 40.0),
        ):
            decision = pool.update(
                frame,
                candidates=[
                    (bg_x, 0.0, 0.99, 20.0, 20.0),
                    (target_x, 0.0, 0.20, 20.0, 20.0),
                ],
                gray_frame=gray,
            )

        self.assertNotIn("guarded_decal_identity_center_mild_state_mild", decision.points)

    def test_guarded_decal_identity_avoids_periodic_background_candidate(self):
        pool = TransparentLiveFamilyPool(
            window=8,
            min_frames=3,
            catalog_min_lag=3,
            catalog_max_lag=3,
            enable_guarded_decal_identity=True,
            guarded_decal_min_background_frames=2,
        )
        gray = np.zeros((80, 180), dtype=np.float32)

        pool.update(0, candidates=[(100.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray, white_anchor=(0.0, 0.0))
        for frame, bg_x, target_x in (
            (1, 100.0, 10.0),
            (2, 110.0, 20.0),
            (3, 120.0, 30.0),
            (4, 100.0, 40.0),
            (5, 110.0, 50.0),
        ):
            decision = pool.update(
                frame,
                candidates=[
                    (bg_x, 0.0, 0.99, 20.0, 20.0),
                    (target_x, 0.0, 0.20, 20.0, 20.0),
                ],
                gray_frame=gray,
            )

        family = "guarded_decal_identity_center_mild_state_mild"
        self.assertEqual(decision.points[family], (50.0, 0.0))
        self.assertTrue(decision.debug["guarded_decal_identity"]["accepted"])
        self.assertGreaterEqual(decision.debug["guarded_decal_identity"]["background_frames"], 2)
        self.assertEqual(decision.debug["guarded_decal_identity"]["background_ratio"], 0.0)
        self.assertEqual(decision.debug["guarded_decal_identity"]["selected_point"], [50.0, 0.0])
        self.assertIn("path_score", decision.debug["guarded_decal_identity"])
        self.assertIn("score_margin", decision.debug["guarded_decal_identity"])
        self.assertEqual(
            decision.debug["guarded_decal_identity"]["latest_candidates"][0]["point"],
            [50.0, 0.0],
        )
        self.assertFalse(decision.debug["guarded_decal_identity"]["latest_candidates"][0]["is_background"])

    def test_guarded_consensus_point_prefers_supported_cluster(self):
        pool = TransparentLiveFamilyPool(window=4, min_frames=3)
        point, debug = pool._guarded_consensus_point({
            "guarded_decal_identity_center_mild_state_mild": (500.0, 500.0),
            "raw_candidate_cont4_center_mild_state_mild": (100.0, 100.0),
            "raw_candidate_rank10_center_mild_state_mild": (102.0, 99.0),
            "balanced_viterbi_center_mild_state_mild": (98.0, 103.0),
            "raw_candidate_cont9_center_mild_state_mild": (300.0, 300.0),
        })

        self.assertEqual(point, (100.0, 100.0))
        self.assertGreaterEqual(debug["support_count"], 3)
        self.assertEqual(debug["selected_family"], "raw_candidate_cont4_center_mild_state_mild")

    def test_guarded_consensus_family_is_emitted_when_cluster_has_support(self):
        pool = TransparentLiveFamilyPool(
            window=8,
            min_frames=3,
            catalog_min_lag=3,
            catalog_max_lag=3,
            enable_guarded_decal_identity=True,
            guarded_decal_min_background_frames=2,
        )
        gray = np.zeros((80, 180), dtype=np.float32)

        pool.update(0, candidates=[(100.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray, white_anchor=(0.0, 0.0))
        for frame, bg_x, target_x in (
            (1, 100.0, 10.0),
            (2, 110.0, 20.0),
            (3, 120.0, 30.0),
            (4, 100.0, 40.0),
            (5, 110.0, 50.0),
        ):
            decision = pool.update(
                frame,
                candidates=[
                    (bg_x, 0.0, 0.99, 20.0, 20.0),
                    (target_x, 0.0, 0.20, 20.0, 20.0),
                ],
                gray_frame=gray,
            )

        family = "guarded_decal_identity_consensus_center_mild_state_mild"
        self.assertIn(family, decision.points)
        self.assertEqual(decision.points[family], (50.0, 0.0))
        self.assertTrue(decision.debug["guarded_decal_consensus"]["accepted"])

    def test_guarded_decal_identity_match_distance_can_be_relaxed(self):
        pool = TransparentLiveFamilyPool(
            window=8,
            min_frames=3,
            catalog_min_lag=3,
            catalog_max_lag=3,
            enable_guarded_decal_identity=True,
            guarded_decal_min_background_frames=2,
            guarded_decal_match_distance_px=15.0,
        )
        gray = np.zeros((80, 180), dtype=np.float32)

        pool.update(0, candidates=[(100.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray, white_anchor=(0.0, 0.0))
        for frame, bg_x, target_x in (
            (1, 100.0, 10.0),
            (2, 110.0, 20.0),
            (3, 120.0, 30.0),
            (4, 112.0, 40.0),
            (5, 122.0, 50.0),
        ):
            decision = pool.update(
                frame,
                candidates=[
                    (bg_x, 0.0, 0.99, 20.0, 20.0),
                    (target_x, 0.0, 0.20, 20.0, 20.0),
                ],
                gray_frame=gray,
            )

        family = "guarded_decal_identity_center_mild_state_mild"
        self.assertEqual(decision.points[family], (50.0, 0.0))
        self.assertGreaterEqual(decision.debug["guarded_decal_identity"]["background_frames"], 2)

    def test_guarded_decal_identity_rejects_large_jump_path(self):
        pool = TransparentLiveFamilyPool(
            window=8,
            min_frames=3,
            catalog_min_lag=3,
            catalog_max_lag=3,
            enable_guarded_decal_identity=True,
            guarded_decal_min_background_frames=2,
            guarded_decal_max_step_px=40.0,
        )
        gray = np.zeros((80, 260), dtype=np.float32)

        pool.update(0, candidates=[(100.0, 0.0, 0.9, 20.0, 20.0)], gray_frame=gray, white_anchor=(0.0, 0.0))
        for frame, bg_x, target_x in (
            (1, 100.0, 10.0),
            (2, 110.0, 20.0),
            (3, 120.0, 30.0),
            (4, 100.0, 40.0),
            (5, 110.0, 180.0),
        ):
            decision = pool.update(
                frame,
                candidates=[
                    (bg_x, 0.0, 0.99, 20.0, 20.0),
                    (target_x, 0.0, 0.20, 20.0, 20.0),
                ],
                gray_frame=gray,
            )

        self.assertNotIn("guarded_decal_identity_center_mild_state_mild", decision.points)
        self.assertFalse(decision.debug["guarded_decal_identity"]["accepted"])
        self.assertEqual(decision.debug["guarded_decal_identity"]["reason"], "max_step")

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
