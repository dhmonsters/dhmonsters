# 캐시된 16개 GT 후보 row에서 오프라인 전용 selector가 16/16을 재현하는지 검증합니다.
import unittest
from pathlib import Path

from _offline_16gt_solver import (
    DEFAULT_CACHE_PATH,
    prepare_offline_16gt_rows,
    solve_cached_16gt,
)
from _final_candidate_selector import load_feature_rows_cache, summarize_selected_rows


class Offline16GtSolverTests(unittest.TestCase):
    def test_prepare_offline_16gt_rows_adds_conditional_features(self):
        rows = [
            {
                "clip": "a",
                "family": "panel_default_center_mild_lb_free",
                "rank_rough": 0.25,
                "source_panel_default": 1.0,
                "variant_free": 1.0,
                "center_mild": 1.0,
                "success": True,
                "mean": 10.0,
            },
        ]

        prepared, feature_names = prepare_offline_16gt_rows(rows)

        self.assertIn("source_panel_default*rank_rough", prepared[0])
        self.assertIn("source_panel_default*variant_free", prepared[0])
        self.assertIn("source_panel_default*rank_rough", feature_names)
        self.assertNotIn("success", feature_names)
        self.assertNotIn("mean", feature_names)

    def test_prepare_offline_16gt_rows_augments_legacy_signal_features(self):
        rows = [
            {
                "clip": "a",
                "family": "background_like",
                "match": 1.0,
                "run": 1.0,
                "cons_med": 5.0,
                "rank_rough": 0.0,
                "source_panel_default": 1.0,
                "success": False,
                "mean": 90.0,
            },
            {
                "clip": "a",
                "family": "target_divergent",
                "match": 0.0,
                "run": 0.0,
                "cons_med": 50.0,
                "rank_rough": 1.0,
                "source_balanced_viterbi": 1.0,
                "success": True,
                "mean": 10.0,
            },
        ]

        prepared, feature_names = prepare_offline_16gt_rows(rows)
        by_family = {row["family"]: row for row in prepared}

        self.assertEqual(by_family["background_like"]["bg_like"], 1.0)
        self.assertEqual(by_family["target_divergent"]["bg_like"], 0.0)
        self.assertEqual(by_family["background_like"]["divergence"], 5.0)
        self.assertEqual(by_family["target_divergent"]["divergence"], 50.0)
        self.assertEqual(by_family["background_like"]["rank_bg_like"], 1.0)
        self.assertEqual(by_family["target_divergent"]["rank_bg_like"], 0.0)
        self.assertEqual(by_family["background_like"]["rank_high_divergence"], 1.0)
        self.assertEqual(by_family["target_divergent"]["rank_high_divergence"], 0.0)
        self.assertIn("rank_bg_like", feature_names)
        self.assertIn("rank_high_divergence", feature_names)

    def test_solve_cached_16gt_reproduces_sixteen_successes(self):
        cache_path = Path(DEFAULT_CACHE_PATH)
        self.assertTrue(cache_path.exists())

        selected = solve_cached_16gt(cache_path)
        summary = summarize_selected_rows(selected)

        self.assertEqual(summary["success"], 16)
        self.assertEqual(summary["total"], 16)
        self.assertLessEqual(summary["mean"], 40.0)

    def test_cached_16gt_input_contains_sixteen_clips(self):
        rows = load_feature_rows_cache(DEFAULT_CACHE_PATH)

        self.assertEqual(len({row["clip"] for row in rows}), 16)


if __name__ == "__main__":
    unittest.main()
