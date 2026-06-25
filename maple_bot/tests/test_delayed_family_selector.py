# delayed family selector의 구간 기반 전환 규칙을 검증합니다.
import unittest

from _delayed_family_selector_score import (
    background_frame_costs,
    delayed_select_path,
    family_mode_prior,
    merge_frame_costs,
    path_roughness_cost,
)


class DelayedFamilySelectorTests(unittest.TestCase):
    def test_state_offset_family_gets_prior_over_raw_center_variant(self):
        self.assertLess(
            family_mode_prior("balanced_viterbi_center_mild_offset_aggressive"),
            family_mode_prior("balanced_viterbi_center_mild_state_aggressive"),
        )
        self.assertLess(
            family_mode_prior("balanced_viterbi_center_mild_state_aggressive"),
            family_mode_prior("balanced_viterbi_center_mild"),
        )

    def test_path_roughness_penalizes_future_jump(self):
        smooth = {
            0: (0.0, 0.0),
            1: (10.0, 0.0),
            2: (20.0, 0.0),
            3: (30.0, 0.0),
        }
        jumpy = {
            0: (0.0, 0.0),
            1: (10.0, 0.0),
            2: (100.0, 0.0),
            3: (30.0, 0.0),
        }

        self.assertLess(
            path_roughness_cost(smooth, [0, 1, 2, 3]),
            path_roughness_cost(jumpy, [0, 1, 2, 3]),
        )

    def test_delayed_selector_switches_to_future_consistent_corrected_family(self):
        frames = [0, 1, 2, 3, 4]
        paths = {
            "consensus_center": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (100.0, 0.0),
                3: (110.0, 0.0),
                4: (120.0, 0.0),
            },
            "corrected_offset_aggressive": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
                3: (30.0, 0.0),
                4: (40.0, 0.0),
            },
        }
        frame_costs = {
            frame: {
                "consensus_center": 0.0,
                "corrected_offset_aggressive": 12.0,
            }
            for frame in frames
        }

        selected_path, selected_families = delayed_select_path(
            paths,
            frames,
            frame_costs,
            lookahead=3,
            switch_penalty=1.0,
        )

        self.assertEqual(selected_families[-3:], [
            "corrected_offset_aggressive",
            "corrected_offset_aggressive",
            "corrected_offset_aggressive",
        ])
        self.assertEqual(selected_path[4], (40.0, 0.0))

    def test_background_cost_penalizes_family_that_matches_repeated_decal(self):
        frames = [0, 1, 2]
        paths = {
            "decal_family": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
            },
            "target_family": {
                0: (0.0, 20.0),
                1: (10.0, 20.0),
                2: (20.0, 20.0),
            },
        }
        expected_background = {
            0: [(0.0, 0.0, 20.0, 20.0, 0.9)],
            1: [(10.0, 0.0, 20.0, 20.0, 0.9)],
            2: [(20.0, 0.0, 20.0, 20.0, 0.9)],
        }

        costs = background_frame_costs(
            paths,
            frames,
            expected_background,
            match_penalty=30.0,
            miss_bonus=-5.0,
        )

        self.assertGreater(costs[1]["decal_family"], costs[1]["target_family"])

        selected_path, selected_families = delayed_select_path(
            paths,
            frames,
            costs,
            local_weight=1.0,
            roughness_weight=0.0,
            prior_weight=0.0,
            switch_penalty=0.0,
        )

        self.assertEqual(selected_families, [
            "target_family",
            "target_family",
            "target_family",
        ])
        self.assertEqual(selected_path[2], (20.0, 20.0))

    def test_merge_frame_costs_adds_weighted_background_penalty(self):
        base = {0: {"a": 2.0, "b": 2.0}}
        background = {0: {"a": 10.0, "b": -2.0}}

        merged = merge_frame_costs(base, background, background_weight=0.5)

        self.assertEqual(merged[0]["a"], 7.0)
        self.assertEqual(merged[0]["b"], 1.0)


if __name__ == "__main__":
    unittest.main()
