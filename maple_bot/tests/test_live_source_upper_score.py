# live source별 상한 채점 유틸리티를 검증합니다.
import unittest

from _live_source_upper_score import (
    augment_with_local_box,
    best_by_source_group,
    build_record_source_paths,
    local_box_candidate_sets_from_rows,
    source_group_for_family,
)


class LiveSourceUpperScoreTests(unittest.TestCase):
    def test_local_box_candidate_sets_convert_record_candidate_order(self):
        rows = [
            {"cands": [[10.0, 20.0, 0.9, 30.0, 40.0]]},
        ]

        candidate_sets = local_box_candidate_sets_from_rows(rows)

        self.assertEqual(candidate_sets[0][0], (10.0, 20.0, 30.0, 40.0, 0.9))

    def test_build_record_source_paths_extracts_track_and_engine(self):
        rows = [
            {
                "track": [1.0, 2.0],
                "engine": {"track": [3.0, 4.0]},
                "cands": [[1.0, 2.0, 0.9, 20.0, 20.0]],
            },
            {
                "track": [5.0, 6.0],
                "engine": {"track": [7.0, 8.0]},
                "cands": [[5.0, 6.0, 0.9, 20.0, 20.0]],
            },
        ]

        paths = build_record_source_paths(rows, include_live=False)

        self.assertEqual(
            paths["panel_default_center_mild_state_mild"],
            {0: (1.0, 2.0), 1: (5.0, 6.0)},
        )
        self.assertEqual(
            paths["phase_catalog_center_mild_state_mild"],
            {0: (3.0, 4.0), 1: (7.0, 8.0)},
        )

    def test_source_group_for_family_keeps_local_box_under_base_source(self):
        self.assertEqual(
            source_group_for_family("balanced_viterbi_center_mild_state_mild_lb_free"),
            "balanced_viterbi",
        )
        self.assertEqual(
            source_group_for_family("phase_catalog_center_mild_state_mild_lb_smooth"),
            "phase_catalog",
        )

    def test_source_group_for_family_groups_raw_candidate_variants(self):
        self.assertEqual(
            source_group_for_family("raw_candidate_rank0_center_mild_state_mild"),
            "raw_candidate",
        )
        self.assertEqual(
            source_group_for_family("raw_candidate_cont0_box_offset_state_mild_lb_free"),
            "raw_candidate",
        )
        self.assertEqual(
            source_group_for_family("raw_candidate_cont0_center_mild_state_mild_lb_smooth"),
            "raw_candidate",
        )

    def test_best_by_source_group_requires_minimum_coverage_for_success(self):
        paths = {
            "raw_candidate_cont0_center_mild_state_mild": {
                0: (0.0, 0.0),
            },
            "raw_candidate_cont1_center_mild_state_mild": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
            },
        }
        gt = {
            0: (0.0, 0.0),
            1: (10.0, 0.0),
        }

        best = best_by_source_group(paths, gt, [0, 1], min_coverage=0.9)

        self.assertTrue(best["raw_candidate"]["success"])
        self.assertEqual(best["raw_candidate"]["family"], "raw_candidate_cont1_center_mild_state_mild")
        self.assertAlmostEqual(best["raw_candidate"]["coverage"], 1.0)

    def test_augment_with_local_box_can_limit_augmented_family_count(self):
        paths = {
            "a": {0: (0.0, 0.0)},
            "b": {0: (10.0, 0.0)},
        }
        candidate_sets = {
            0: [(0.0, 0.0, 20.0, 20.0, 0.9)],
        }

        augmented = augment_with_local_box(
            paths,
            candidate_sets,
            [0],
            max_local_box_families=1,
        )

        self.assertIn("a_lb_smooth", augmented)
        self.assertNotIn("b_lb_smooth", augmented)


if __name__ == "__main__":
    unittest.main()
