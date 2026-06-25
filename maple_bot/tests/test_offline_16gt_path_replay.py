# 16GT baseline이 고른 family 이름을 실제 path로 재생하는 유틸을 검증합니다.
import unittest

from _offline_16gt_path_replay import (
    score_selected_family_paths,
    selected_family_by_clip,
    summarize_path_scores,
)


class Offline16GtPathReplayTests(unittest.TestCase):
    def test_selected_family_by_clip_extracts_family_names(self):
        selected = {
            "clip_a": {"family": "family_a"},
            "clip_b": {"family": "family_b"},
        }

        self.assertEqual(
            selected_family_by_clip(selected),
            {"clip_a": "family_a", "clip_b": "family_b"},
        )

    def test_score_selected_family_paths_uses_loader_and_gt_provider(self):
        selected = {
            "clip_a": "good_family",
            "clip_b": "bad_family",
        }

        def load_paths(name):
            return {
                "good_family": {0: (0.0, 0.0), 1: (10.0, 0.0)},
                "bad_family": {0: (100.0, 0.0), 1: (100.0, 0.0)},
            }

        def load_gt(_name):
            return {0: (0.0, 0.0), 1: (10.0, 0.0)}

        rows = score_selected_family_paths(
            selected,
            load_paths=load_paths,
            load_gt=load_gt,
        )
        by_name = {row["name"]: row for row in rows}

        self.assertTrue(by_name["clip_a"]["success"])
        self.assertFalse(by_name["clip_b"]["success"])
        self.assertEqual(by_name["clip_a"]["family"], "good_family")
        self.assertEqual(summarize_path_scores(rows)["success"], 1)

    def test_score_selected_family_paths_marks_missing_family_as_failure(self):
        rows = score_selected_family_paths(
            {"clip_a": "missing"},
            load_paths=lambda _name: {"other": {0: (0.0, 0.0)}},
            load_gt=lambda _name: {0: (0.0, 0.0)},
        )

        self.assertFalse(rows[0]["success"])
        self.assertEqual(rows[0]["failure"], "missing_family")


if __name__ == "__main__":
    unittest.main()
