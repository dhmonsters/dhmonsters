# consensus rescue 신뢰 게이트 분석 리포트의 특징 추출을 검증합니다.
from pathlib import Path
import contextlib
import io
import tempfile
import unittest
from unittest.mock import patch

from _consensus_rescue_gate_report import (
    analyze_clip,
    consensus_gate_feature_rows,
    consensus_gate_passes,
    evaluate_gate_rows,
    gate_sweep_rows,
    main,
    markdown_report,
    summarize_consensus_gate_rows,
)


class ConsensusRescueGateReportTests(unittest.TestCase):
    def test_feature_rows_label_consensus_better_without_using_gt_features(self):
        rows = [
            {
                "track": [0.0, 0.0],
                "selector_shadow": {
                    "available": True,
                    "rank_center": 0.8,
                    "rank_rough": 0.2,
                    "merge_context": {"frames": 1},
                    "consensus_rescue_allowed": True,
                    "consensus_rescue_point": [10.0, 0.0],
                },
                "live_family": {
                    "debug": {
                        "guarded_decal_consensus": {
                            "accepted": True,
                            "reason": "accepted",
                            "support_count": 4,
                            "support_weight": 4.5,
                            "avg_dist": 7.25,
                            "background_expected": True,
                        }
                    }
                },
            },
            {
                "track": [30.0, 0.0],
                "selector_shadow": {
                    "available": True,
                    "rank_center": 0.9,
                    "rank_rough": 0.3,
                    "merge_context": {"frames": 0},
                    "consensus_rescue_allowed": True,
                    "consensus_rescue_point": [15.0, 0.0],
                },
                "live_family": {
                    "debug": {
                        "guarded_decal_consensus": {
                            "accepted": True,
                            "reason": "accepted",
                            "support_count": 3,
                            "support_weight": 3.0,
                            "avg_dist": 9.0,
                            "background_expected": False,
                        }
                    }
                },
            },
        ]
        gt = {0: (12.0, 0.0), 1: (30.0, 0.0)}

        feature_rows = consensus_gate_feature_rows(rows, gt)

        self.assertEqual(len(feature_rows), 2)
        self.assertEqual(feature_rows[0]["frame"], 0)
        self.assertTrue(feature_rows[0]["consensus_better"])
        self.assertAlmostEqual(feature_rows[0]["track_error"], 12.0)
        self.assertAlmostEqual(feature_rows[0]["consensus_error"], 2.0)
        self.assertAlmostEqual(feature_rows[0]["error_delta"], 10.0)
        self.assertAlmostEqual(feature_rows[0]["primary_consensus_dist"], 10.0)
        self.assertAlmostEqual(feature_rows[0]["support_weight"], 4.5)
        self.assertAlmostEqual(feature_rows[0]["avg_dist"], 7.25)
        self.assertEqual(feature_rows[0]["support_count"], 4)
        self.assertEqual(feature_rows[0]["merge_frames"], 1)
        self.assertTrue(feature_rows[0]["accepted"])
        self.assertTrue(feature_rows[0]["background_expected"])
        self.assertAlmostEqual(feature_rows[1]["consensus_step"], 5.0)
        self.assertAlmostEqual(feature_rows[1]["track_step"], 30.0)
        self.assertFalse(feature_rows[1]["consensus_better"])

    def test_feature_rows_use_frame_offset_for_sliced_replay_windows(self):
        rows = [
            {
                "track": [0.0, 0.0],
                "selector_shadow": {
                    "available": True,
                    "consensus_rescue_allowed": True,
                    "consensus_rescue_point": [10.0, 0.0],
                },
            }
        ]
        gt = {50: (12.0, 0.0)}

        feature_rows = consensus_gate_feature_rows(rows, gt, frame_offset=50)

        self.assertEqual(feature_rows[0]["frame"], 50)
        self.assertAlmostEqual(feature_rows[0]["consensus_error"], 2.0)

    def test_summary_splits_good_and_bad_consensus_rows(self):
        feature_rows = [
            {
                "consensus_better": True,
                "error_delta": 10.0,
                "support_weight": 4.0,
                "avg_dist": 8.0,
                "primary_consensus_dist": 60.0,
            },
            {
                "consensus_better": False,
                "error_delta": -5.0,
                "support_weight": 2.0,
                "avg_dist": 20.0,
                "primary_consensus_dist": 15.0,
            },
        ]

        summary = summarize_consensus_gate_rows(feature_rows)

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["better"]["count"], 1)
        self.assertEqual(summary["worse"]["count"], 1)
        self.assertAlmostEqual(summary["better"]["support_weight_mean"], 4.0)
        self.assertAlmostEqual(summary["worse"]["avg_dist_mean"], 20.0)
        self.assertAlmostEqual(summary["better"]["primary_consensus_dist_mean"], 60.0)

    def test_consensus_gate_passes_only_strong_gt_free_rows(self):
        strong = {
            "accepted": True,
            "support_weight": 4.0,
            "avg_dist": 8.0,
            "primary_consensus_dist": 65.0,
            "consensus_step": 12.0,
        }

        self.assertTrue(consensus_gate_passes(strong))
        self.assertFalse(consensus_gate_passes({**strong, "support_weight": 2.0}))
        self.assertFalse(consensus_gate_passes({**strong, "avg_dist": 26.0}))
        self.assertFalse(consensus_gate_passes({**strong, "primary_consensus_dist": 20.0}))
        self.assertFalse(consensus_gate_passes({**strong, "consensus_step": 95.0}))
        self.assertFalse(consensus_gate_passes({**strong, "accepted": False}))

    def test_evaluate_gate_rows_counts_better_and_worse_passes(self):
        feature_rows = [
            {
                "consensus_better": True,
                "error_delta": 10.0,
                "accepted": True,
                "support_weight": 4.0,
                "avg_dist": 8.0,
                "primary_consensus_dist": 65.0,
                "consensus_step": 12.0,
            },
            {
                "consensus_better": False,
                "error_delta": -5.0,
                "accepted": True,
                "support_weight": 4.0,
                "avg_dist": 8.0,
                "primary_consensus_dist": 70.0,
                "consensus_step": 14.0,
            },
            {
                "consensus_better": True,
                "error_delta": 20.0,
                "accepted": True,
                "support_weight": 2.0,
                "avg_dist": 8.0,
                "primary_consensus_dist": 70.0,
                "consensus_step": 14.0,
            },
        ]

        result = evaluate_gate_rows(feature_rows)

        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["better_passed"], 1)
        self.assertEqual(result["worse_passed"], 1)
        self.assertAlmostEqual(result["mean_error_delta"], 2.5)

    def test_gate_sweep_rows_preserves_config_and_metrics(self):
        feature_rows = [
            {
                "consensus_better": True,
                "error_delta": 10.0,
                "accepted": True,
                "support_weight": 4.0,
                "avg_dist": 8.0,
                "primary_consensus_dist": 65.0,
                "consensus_step": 12.0,
            }
        ]

        sweep = gate_sweep_rows(feature_rows, configs=[{"min_support_weight": 3.5}])

        self.assertEqual(len(sweep), 1)
        self.assertEqual(sweep[0]["config"]["min_support_weight"], 3.5)
        self.assertEqual(sweep[0]["passed"], 1)
        self.assertEqual(sweep[0]["better_passed"], 1)

    def test_markdown_report_includes_summary_and_gate_table(self):
        feature_rows = [
            {
                "frame": 10,
                "consensus_better": True,
                "error_delta": 10.0,
                "track_error": 12.0,
                "consensus_error": 2.0,
                "accepted": True,
                "support_weight": 4.0,
                "avg_dist": 8.0,
                "primary_consensus_dist": 65.0,
                "consensus_step": 12.0,
            }
        ]

        text = markdown_report("sample", feature_rows)

        self.assertIn("# consensus rescue gate report", text)
        self.assertIn("sample", text)
        self.assertIn("better", text)
        self.assertIn("min_support", text)

    def test_analyze_clip_forwards_no_local_box_for_fast_gate_reports(self):
        captured = {}

        def fake_backfill(rows, **kwargs):
            captured.update(kwargs)
            return list(rows)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record_dir = root / "_record_debug"
            record_dir.mkdir()
            (record_dir / "sample.jsonl").write_text("{}\n", encoding="utf-8")
            with patch("_selector_shadow_gt_replay_score._load_jsonl", return_value=[]):
                with patch("_selector_shadow_gt_replay_score._new_runtime", return_value=object()):
                    with patch("_selector_shadow_gt_replay_score.backfill_selector_shadow_rows", fake_backfill):
                        with patch("_selector_shadow_gt_replay_score.load_red_gt", return_value={}):
                            analyze_clip("sample", root=root, include_local_box=False)

        self.assertFalse(captured["include_local_box"])

    def test_main_keeps_report_available_when_python_write_is_denied(self):
        with patch("_consensus_rescue_gate_report.analyze_clip", return_value=([], "report text\n")):
            with patch("pathlib.Path.write_text", side_effect=PermissionError("denied")):
                with contextlib.redirect_stdout(io.StringIO()):
                    result = main(["sample", "--out", "03_output/blocked.md"])

        self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
