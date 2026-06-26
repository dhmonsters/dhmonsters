# live source별 상한 채점 유틸리티를 검증합니다.
import unittest

from _live_source_upper_score import (
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


if __name__ == "__main__":
    unittest.main()
