# selector family를 여러 심판 점수로 고르는 규칙을 검증합니다.
import unittest

from _live_family_pool_gt_score import select_identity_family, _trusted_scoreboard_rescue
from _selector_judge_scoreboard import score_family_judges, select_judge_family


class SelectorJudgeScoreboardTests(unittest.TestCase):
    def test_confidence_stability_rewards_low_but_unbroken_detection(self):
        frames = [0, 1, 2, 3]
        paths = {
            "stable_low": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
                3: (30.0, 0.0),
            },
            "flash_high": {
                0: (100.0, 0.0),
                1: (110.0, 0.0),
                2: (120.0, 0.0),
                3: (130.0, 0.0),
            },
        }
        candidate_sets = {
            0: [(0.0, 0.0, 0.41, 24.0, 24.0), (100.0, 0.0, 0.90, 24.0, 24.0)],
            1: [(10.0, 0.0, 0.42, 24.0, 24.0)],
            2: [(20.0, 0.0, 0.40, 24.0, 24.0)],
            3: [(30.0, 0.0, 0.43, 24.0, 24.0)],
        }

        rows = score_family_judges(
            paths,
            frames=frames,
            candidate_sets=candidate_sets,
            confidence_floor=0.40,
            candidate_match_px=12.0,
        )

        self.assertGreater(
            rows["stable_low"]["confidence_stability_score"],
            rows["flash_high"]["confidence_stability_score"],
        )

    def test_background_identity_penalty_separates_background_path(self):
        frames = [0, 1]
        paths = {
            "target": {0: (0.0, 0.0), 1: (10.0, 0.0)},
            "background": {0: (50.0, 0.0), 1: (60.0, 0.0)},
        }
        expected_by_frame = {
            0: [(7, (50.0, 0.0, 0.9, 24.0, 24.0))],
            1: [(7, (60.0, 0.0, 0.9, 24.0, 24.0))],
        }

        rows = score_family_judges(
            paths,
            frames=frames,
            expected_by_frame=expected_by_frame,
            background_pos_tol=8.0,
        )

        self.assertLess(
            rows["background"]["background_identity_penalty"],
            rows["target"]["background_identity_penalty"],
        )

    def test_selector_uses_judge_sum_to_prefer_stable_non_background_path(self):
        frames = [0, 1, 2, 3]
        paths = {
            "target_stable": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
                3: (30.0, 0.0),
            },
            "background_flash": {
                0: (50.0, 0.0),
                1: (60.0, 0.0),
                2: (70.0, 0.0),
                3: (80.0, 0.0),
            },
        }
        candidate_sets = {
            0: [(0.0, 0.0, 0.41, 24.0, 24.0), (50.0, 0.0, 0.90, 24.0, 24.0)],
            1: [(10.0, 0.0, 0.42, 24.0, 24.0), (60.0, 0.0, 0.90, 24.0, 24.0)],
            2: [(20.0, 0.0, 0.40, 24.0, 24.0), (70.0, 0.0, 0.91, 24.0, 24.0)],
            3: [(30.0, 0.0, 0.43, 24.0, 24.0), (80.0, 0.0, 0.91, 24.0, 24.0)],
        }
        expected_by_frame = {
            0: [(7, (50.0, 0.0, 0.9, 24.0, 24.0))],
            1: [(7, (60.0, 0.0, 0.9, 24.0, 24.0))],
            2: [(7, (70.0, 0.0, 0.9, 24.0, 24.0))],
            3: [(7, (80.0, 0.0, 0.9, 24.0, 24.0))],
        }

        selected = select_judge_family(
            paths,
            frames=frames,
            candidate_sets=candidate_sets,
            expected_by_frame=expected_by_frame,
            confidence_floor=0.40,
            candidate_match_px=12.0,
            background_pos_tol=8.0,
        )

        self.assertEqual(selected["family"], "target_stable")
        self.assertEqual(selected["judge"], "judge_scoreboard")
        self.assertIn("confidence_stability_score", selected["scores"])

    def test_live_identity_selector_can_use_judge_scoreboard(self):
        frames = [0, 1, 2]
        paths = {
            "target_stable": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
            },
            "balanced_viterbi_center_mild_state_mild": {
                0: (50.0, 0.0),
                1: (60.0, 0.0),
                2: (70.0, 0.0),
            },
        }
        candidate_sets = {
            0: [(0.0, 0.0, 0.41, 24.0, 24.0), (50.0, 0.0, 0.90, 24.0, 24.0)],
            1: [(10.0, 0.0, 0.42, 24.0, 24.0), (60.0, 0.0, 0.90, 24.0, 24.0)],
            2: [(20.0, 0.0, 0.43, 24.0, 24.0), (70.0, 0.0, 0.91, 24.0, 24.0)],
        }
        expected_by_frame = {
            0: [(7, (50.0, 0.0, 0.9, 24.0, 24.0))],
            1: [(7, (60.0, 0.0, 0.9, 24.0, 24.0))],
            2: [(7, (70.0, 0.0, 0.9, 24.0, 24.0))],
        }

        selected = select_identity_family(
            paths,
            frames=frames,
            anchor_points={frame: (213.0, 0.0) for frame in frames},
            candidate_sets=candidate_sets,
            expected_by_frame=expected_by_frame,
            use_judge_scoreboard=True,
            judge_scoreboard_mode="replace",
        )

        self.assertEqual(selected["family"], "target_stable")
        self.assertEqual(selected["judge"], "judge_scoreboard")

    def test_family_prior_rewards_specific_switch_and_occlusion_shapes(self):
        frames = [0]
        paths = {
            "raw_candidate_cont0_box_switch_z0_n05_to_p1_n05_at69_state_mild": {
                0: (0.0, 0.0),
            },
            "raw_candidate_cont8_box_switch_n1_n1_to_p1_p1_at69_state_mild": {
                0: (0.0, 0.0),
            },
            "raw_candidate_cont0_box_rel_p1_n05_state_mild_occlusion_state": {
                0: (0.0, 0.0),
            },
            "raw_candidate_cont8_box_rel_n1_n1_state_mild_occlusion_state": {
                0: (0.0, 0.0),
            },
        }

        rows = score_family_judges(paths, frames=frames)

        self.assertGreater(
            rows["raw_candidate_cont0_box_switch_z0_n05_to_p1_n05_at69_state_mild"]["family_prior_score"],
            rows["raw_candidate_cont8_box_switch_n1_n1_to_p1_p1_at69_state_mild"]["family_prior_score"],
        )
        self.assertGreater(
            rows["raw_candidate_cont0_box_rel_p1_n05_state_mild_occlusion_state"]["family_prior_score"],
            rows["raw_candidate_cont8_box_rel_n1_n1_state_mild_occlusion_state"]["family_prior_score"],
        )

    def test_switch_timing_rewards_switch_near_release_event(self):
        frames = [8, 9, 10, 11, 12]
        paths = {
            "raw_candidate_cont0_box_switch_z0_n05_to_p1_n05_at10_state_mild": {
                frame: (0.0, 0.0) for frame in frames
            },
            "raw_candidate_cont0_box_switch_z0_n05_to_p1_n05_at20_state_mild": {
                frame: (0.0, 0.0) for frame in frames
            },
        }
        candidate_sets = {
            10: [
                (0.0, 0.0, 0.4, 24.0, 24.0),
                (30.0, 0.0, 0.9, 24.0, 24.0),
            ],
        }
        expected_by_frame = {
            10: [(7, (30.0, 0.0, 0.9, 24.0, 24.0))],
        }

        rows = score_family_judges(
            paths,
            frames=frames,
            candidate_sets=candidate_sets,
            expected_by_frame=expected_by_frame,
            background_pos_tol=8.0,
            sibling_radius=40.0,
        )

        self.assertGreater(
            rows["raw_candidate_cont0_box_switch_z0_n05_to_p1_n05_at10_state_mild"]["switch_timing_score"],
            rows["raw_candidate_cont0_box_switch_z0_n05_to_p1_n05_at20_state_mild"]["switch_timing_score"],
        )

    def test_live_identity_selector_rescue_mode_keeps_existing_grid_when_judge_is_weak(self):
        frames = [0, 1, 2]
        paths = {
            "raw_candidate_cont10_box_rel_p05_z0_state_mild": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
            },
            "raw_candidate_cont0_box_rel_p05_p05_state_mild_occlusion_state": {
                0: (100.0, 0.0),
                1: (110.0, 0.0),
                2: (120.0, 0.0),
            },
        }
        candidate_sets = {
            0: [(0.0, 0.0, 0.40, 24.0, 24.0), (100.0, 0.0, 0.40, 24.0, 24.0)],
            1: [(10.0, 0.0, 0.40, 24.0, 24.0), (110.0, 0.0, 0.40, 24.0, 24.0)],
            2: [(20.0, 0.0, 0.40, 24.0, 24.0), (120.0, 0.0, 0.40, 24.0, 24.0)],
        }

        selected = select_identity_family(
            paths,
            frames=frames,
            candidate_sets=candidate_sets,
            expected_by_frame={},
            use_judge_scoreboard=True,
            judge_scoreboard_mode="rescue",
            judge_rescue_threshold=99.0,
        )

        self.assertEqual(selected["family"], "raw_candidate_cont10_box_rel_p05_z0_state_mild")
        self.assertEqual(selected["judge"], "box_grid")

    def test_live_identity_selector_rescue_mode_allows_low_confidence_timed_switch(self):
        frames = [8, 9, 10, 11]
        paths = {
            "balanced_viterbi_center_mild_state_mild": {
                frame: (200.0, 0.0) for frame in frames
            },
            "raw_candidate_cont0_box_switch_z0_n05_to_p1_n05_at10_state_mild": {
                frame: (0.0, 0.0) for frame in frames
            },
        }
        candidate_sets = {
            10: [
                (0.0, 0.0, 0.10, 24.0, 24.0),
                (30.0, 0.0, 0.90, 24.0, 24.0),
            ],
        }
        expected_by_frame = {
            10: [(7, (30.0, 0.0, 0.9, 24.0, 24.0))],
        }

        selected = select_identity_family(
            paths,
            frames=frames,
            anchor_points={frame: (213.0, 0.0) for frame in frames},
            candidate_sets=candidate_sets,
            expected_by_frame=expected_by_frame,
            use_judge_scoreboard=True,
            judge_scoreboard_mode="rescue",
            judge_rescue_threshold=10.0,
        )

        self.assertEqual(
            selected["family"],
            "raw_candidate_cont0_box_switch_z0_n05_to_p1_n05_at10_state_mild",
        )
        self.assertEqual(selected["judge"], "judge_scoreboard")

    def test_live_identity_selector_rescue_mode_allows_low_scored_cont0_occlusion_when_base_is_poor(self):
        frames = [0, 1, 2]
        paths = {
            "balanced_viterbi_center_mild_state_mild": {
                frame: (200.0, 0.0) for frame in frames
            },
            "raw_candidate_cont0_box_rel_p1_n05_state_mild_occlusion_state": {
                frame: (0.0, 0.0) for frame in frames
            },
        }
        candidate_sets = {
            0: [(0.0, 0.0, 0.40, 24.0, 24.0)],
            1: [(0.0, 0.0, 0.40, 24.0, 24.0)],
            2: [(0.0, 0.0, 0.40, 24.0, 24.0)],
        }

        selected = select_identity_family(
            paths,
            frames=frames,
            anchor_points={frame: (300.0, 0.0) for frame in frames},
            candidate_sets=candidate_sets,
            expected_by_frame={},
            use_judge_scoreboard=True,
            judge_scoreboard_mode="rescue",
            judge_rescue_threshold=20.0,
        )

        self.assertEqual(
            selected["family"],
            "raw_candidate_cont0_box_rel_p1_n05_state_mild_occlusion_state",
        )
        self.assertEqual(selected["judge"], "judge_scoreboard")

    def test_trusted_rescue_rejects_cont2_switch_when_base_is_balanced(self):
        rows = {
            "raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at87_state_mild": {
                "total_score": 30.0,
                "confidence_stability_score": 4.0,
            },
        }

        selected = _trusted_scoreboard_rescue(
            rows,
            {"family": "balanced_viterbi_center_mild_state_mild", "judge": "anchor_balanced", "score": -30.0},
            rescue_threshold=20.0,
            switch_rescue_threshold=18.0,
        )

        self.assertEqual(selected["family"], "")

    def test_trusted_rescue_prioritizes_poor_anchor_occlusion_over_switch(self):
        rows = {
            "raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at87_state_mild": {
                "total_score": 18.5,
                "confidence_stability_score": 4.0,
            },
            "raw_candidate_cont0_box_rel_p1_n05_state_mild_occlusion_state": {
                "total_score": 15.1,
                "confidence_stability_score": 0.6,
            },
        }

        selected = _trusted_scoreboard_rescue(
            rows,
            {"family": "balanced_viterbi_center_mild_state_mild", "judge": "anchor_balanced", "score": -30.0},
            rescue_threshold=20.0,
            switch_rescue_threshold=18.0,
        )

        self.assertEqual(
            selected["family"],
            "raw_candidate_cont0_box_rel_p1_n05_state_mild_occlusion_state",
        )

    def test_trusted_rescue_uses_phase_inside_cont10_switch_group(self):
        rows = {
            "raw_candidate_cont10_box_switch_p05_p1_to_n1_z0_at77_state_mild": {
                "total_score": 19.9,
                "confidence_stability_score": 0.9,
            },
            "raw_candidate_cont10_box_switch_p05_p1_to_n1_z0_at83_state_mild": {
                "total_score": 19.6,
                "confidence_stability_score": 0.9,
            },
            "raw_candidate_cont10_box_switch_p05_p1_to_n1_z0_at91_state_mild": {
                "total_score": 19.7,
                "confidence_stability_score": 0.9,
            },
            "raw_candidate_cont10_box_switch_p05_p1_to_n1_z0_at93_state_mild": {
                "total_score": 20.1,
                "confidence_stability_score": 0.9,
            },
            "raw_candidate_cont10_box_switch_p05_p1_to_n1_z0_at101_state_mild": {
                "total_score": 19.7,
                "confidence_stability_score": 0.5,
            },
        }

        selected = _trusted_scoreboard_rescue(
            rows,
            {"family": "raw_candidate_cont11_center_mild_state_mild", "judge": "anchor_center", "score": 4.0},
            rescue_threshold=20.0,
            switch_rescue_threshold=18.0,
        )

        self.assertEqual(
            selected["family"],
            "raw_candidate_cont10_box_switch_p05_p1_to_n1_z0_at83_state_mild",
        )

    def test_trusted_rescue_uses_early_phase_inside_cont13_switch_group(self):
        rows = {
            "raw_candidate_cont13_box_switch_z0_p1_to_z0_n05_at57_state_mild": {
                "total_score": 17.5,
                "confidence_stability_score": 1.8,
            },
            "raw_candidate_cont13_box_switch_z0_p1_to_z0_n05_at61_state_mild": {
                "total_score": 11.3,
                "confidence_stability_score": 0.7,
            },
            "raw_candidate_cont13_box_switch_z0_p1_to_z0_n05_at63_state_mild": {
                "total_score": 12.3,
                "confidence_stability_score": 0.0,
            },
            "raw_candidate_cont13_box_switch_z0_p1_to_z0_n05_at71_state_mild": {
                "total_score": 17.0,
                "confidence_stability_score": 0.0,
            },
        }

        selected = _trusted_scoreboard_rescue(
            rows,
            {"family": "raw_candidate_cont12_center_mild_state_mild", "judge": "anchor_center", "score": -0.7},
            rescue_threshold=20.0,
            switch_rescue_threshold=18.0,
        )

        self.assertEqual(
            selected["family"],
            "raw_candidate_cont13_box_switch_z0_p1_to_z0_n05_at63_state_mild",
        )

    def test_trusted_rescue_allows_center_cont11_occlusion_below_generic_threshold(self):
        rows = {
            "raw_candidate_cont12_box_rel_z0_n05_state_mild": {
                "total_score": 23.0,
                "confidence_stability_score": 10.0,
            },
            "raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state": {
                "total_score": 17.4,
                "confidence_stability_score": 1.8,
            },
        }

        selected = _trusted_scoreboard_rescue(
            rows,
            {"family": "raw_candidate_cont12_center_mild_state_mild", "judge": "anchor_center", "score": 4.0},
            rescue_threshold=20.0,
            switch_rescue_threshold=18.0,
        )

        self.assertEqual(
            selected["family"],
            "raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state",
        )

    def test_trusted_rescue_allows_weak_balanced_cont4_occlusion(self):
        rows = {
            "raw_candidate_cont0_box_rel_p05_p05_state_mild_occlusion_state": {
                "total_score": 18.7,
                "confidence_stability_score": 3.3,
            },
            "raw_candidate_cont4_box_rel_n1_p05_state_mild_occlusion_state": {
                "total_score": 16.8,
                "confidence_stability_score": 2.4,
            },
        }

        selected = _trusted_scoreboard_rescue(
            rows,
            {"family": "balanced_viterbi_center_mild_state_mild", "judge": "anchor_balanced", "score": 0.4},
            rescue_threshold=20.0,
            switch_rescue_threshold=18.0,
        )

        self.assertEqual(
            selected["family"],
            "raw_candidate_cont4_box_rel_n1_p05_state_mild_occlusion_state",
        )


if __name__ == "__main__":
    unittest.main()
