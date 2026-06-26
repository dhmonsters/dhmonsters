# source gap partition 진단 로직을 검증합니다.
import unittest

from _source_gap_partition import (
    classify_clip,
    parse_source_upper_markdown,
    raw_candidate_oracles,
    score_point_path,
)


class SourceGapPartitionTests(unittest.TestCase):
    def test_score_point_path_requires_coverage(self):
        gt = {0: (0.0, 0.0), 1: (10.0, 0.0)}
        path = {0: (0.0, 0.0)}

        score = score_point_path(path, gt, [0, 1], min_coverage=0.9)

        self.assertEqual(score["n"], 1)
        self.assertAlmostEqual(score["coverage"], 0.5)
        self.assertFalse(score["success"])

    def test_raw_candidate_oracles_distinguish_center_from_box(self):
        rows = [
            {"cands": [[50.0, 0.0, 0.9, 120.0, 30.0]]},
            {"cands": [[60.0, 0.0, 0.9, 120.0, 30.0]]},
        ]
        gt = {0: (0.0, 0.0), 1: (10.0, 0.0)}

        result = raw_candidate_oracles(rows, gt, [0, 1], success_px=40.0)

        self.assertFalse(result["raw_center"]["success"])
        self.assertTrue(result["raw_box"]["success"])

    def test_classify_clip_prefers_source_then_center_then_box(self):
        source = {"success": True, "mean": 12.0, "coverage": 1.0}
        center = {"success": True, "mean": 8.0, "coverage": 1.0}
        box = {"success": True, "mean": 0.0, "coverage": 1.0}

        self.assertEqual(
            classify_clip(source, center, box),
            "source_upper_solved",
        )

        source["success"] = False
        self.assertEqual(
            classify_clip(source, center, box),
            "raw_center_family_missing",
        )

        center["success"] = False
        self.assertEqual(
            classify_clip(source, center, box),
            "offset_or_merge_center_reconstruction",
        )

        box["success"] = False
        self.assertEqual(
            classify_clip(source, center, box),
            "detection_gap_or_visual_reconstruction",
        )

    def test_parse_source_upper_markdown_uses_success_cells_first(self):
        text = "\n".join([
            "| clip | GT | balanced_viterbi | phase_catalog |",
            "|---|---:|---:|---:|",
            "| `clip_a` | 12 | 55.0 | 12.5 OK |",
            "| `clip_b` | 10 | 45.0 | 60.0 |",
        ])

        parsed = parse_source_upper_markdown(text)

        self.assertTrue(parsed["clip_a"]["success"])
        self.assertEqual(parsed["clip_a"]["source"], "phase_catalog")
        self.assertAlmostEqual(parsed["clip_a"]["mean"], 12.5)
        self.assertFalse(parsed["clip_b"]["success"])
        self.assertEqual(parsed["clip_b"]["source"], "balanced_viterbi")
        self.assertAlmostEqual(parsed["clip_b"]["mean"], 45.0)


if __name__ == "__main__":
    unittest.main()
