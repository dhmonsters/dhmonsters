# guarded parameter sweep 리포트 요약을 검증합니다.
import unittest

from _guarded_sweep_report import summarize_sweep_item, write_markdown_report


class GuardedSweepReportTests(unittest.TestCase):
    def test_summarize_sweep_item_counts_reasons_and_errors(self):
        config = {
            "min_bg": 2,
            "match_px": 16.0,
            "shape_pct": 12.0,
            "max_step": 180.0,
        }
        results = [
            {
                "name": "a",
                "guarded_emitted_frames": 3,
                "guarded_selected_frames": 2,
                "guarded_reason_counts": {"background_signal": 4},
                "guarded_emitted": {"n": 2, "mean": 30.0, "success": True},
                "selected": {"n": 2, "mean": 35.0, "success": True},
            },
            {
                "name": "b",
                "guarded_emitted_frames": 0,
                "guarded_selected_frames": 0,
                "guarded_reason_counts": {"max_step": 2},
                "guarded_emitted": {"n": 0, "mean": float("nan"), "success": False},
                "selected": {"n": 2, "mean": 80.0, "success": False},
            },
        ]

        summary = summarize_sweep_item(config, results)

        self.assertEqual(summary["min_bg"], 2)
        self.assertEqual(summary["match_px"], 16.0)
        self.assertEqual(summary["max_step"], 180.0)
        self.assertEqual(summary["emitted_frames"], 3)
        self.assertEqual(summary["selected_frames"], 2)
        self.assertEqual(summary["guarded_success"], 1)
        self.assertEqual(summary["selected_success"], 1)
        self.assertEqual(summary["reason_counts"], {"background_signal": 4, "max_step": 2})
        self.assertEqual(summary["guarded_mean"], 30.0)
        self.assertEqual(summary["selected_mean"], 57.5)

    def test_write_markdown_report_includes_sweep_columns(self):
        text = write_markdown_report([
            {
                "min_bg": 2,
                "match_px": 16.0,
                "shape_pct": 12.0,
                "max_step": 180.0,
                "clips": 2,
                "guarded_success": 1,
                "selected_success": 1,
                "emitted_frames": 3,
                "selected_frames": 2,
                "guarded_mean": 30.0,
                "selected_mean": 57.5,
                "reason_counts": {"background_signal": 4, "max_step": 2},
            }
        ])

        self.assertIn("| min_bg | match_px | shape_pct | max_step |", text)
        self.assertIn("background_signal=4, max_step=2", text)
        self.assertIn("57.5", text)


if __name__ == "__main__":
    unittest.main()
