# GT 없이 family 후보를 선택하는 selector를 검증합니다.
import tempfile
import unittest
from pathlib import Path

from _final_candidate_selector import LinearSelectorModel
from _final_candidate_selector import summarize_selected_rows
from _final_candidate_selector import load_feature_rows_cache
from _gt_free_family_selector import (
    select_cached_rows_without_gt,
    fit_gt_free_selector,
    load_gt_free_selector_model,
    save_gt_free_selector_model,
    select_gt_free_family_rows,
)
from _offline_16gt_solver import DEFAULT_CACHE_PATH


class GtFreeFamilySelectorTests(unittest.TestCase):
    def test_selector_ignores_runtime_success_and_mean_labels(self):
        train_rows = [
            {
                "clip": "train_a",
                "family": "panel_default_center_mild_state_mild",
                "rank_rough": 0.0,
                "rank_cons_med": 0.0,
                "source_panel_default": 1.0,
                "source_balanced_viterbi": 0.0,
                "center_mild": 1.0,
                "state_mild": 1.0,
                "success": True,
                "mean": 12.0,
            },
            {
                "clip": "train_a",
                "family": "balanced_viterbi_center_mild_state_mild_lb_free",
                "rank_rough": 1.0,
                "rank_cons_med": 1.0,
                "source_panel_default": 0.0,
                "source_balanced_viterbi": 1.0,
                "center_mild": 1.0,
                "state_mild": 1.0,
                "variant_free": 1.0,
                "success": False,
                "mean": 90.0,
            },
            {
                "clip": "train_b",
                "family": "panel_default_center_mild_state_mild",
                "rank_rough": 0.0,
                "rank_cons_med": 0.0,
                "source_panel_default": 1.0,
                "source_balanced_viterbi": 0.0,
                "center_mild": 1.0,
                "state_mild": 1.0,
                "success": True,
                "mean": 14.0,
            },
            {
                "clip": "train_b",
                "family": "balanced_viterbi_center_mild_state_mild_lb_free",
                "rank_rough": 1.0,
                "rank_cons_med": 1.0,
                "source_panel_default": 0.0,
                "source_balanced_viterbi": 1.0,
                "center_mild": 1.0,
                "state_mild": 1.0,
                "variant_free": 1.0,
                "success": False,
                "mean": 95.0,
            },
        ]
        runtime_rows = [
            {
                "clip": "live_a",
                "family": "balanced_viterbi_center_mild_state_mild_lb_free",
                "rank_rough": 1.0,
                "rank_cons_med": 1.0,
                "source_panel_default": 0.0,
                "source_balanced_viterbi": 1.0,
                "center_mild": 1.0,
                "state_mild": 1.0,
                "variant_free": 1.0,
                "success": True,
                "mean": 1.0,
            },
            {
                "clip": "live_a",
                "family": "panel_default_center_mild_state_mild",
                "rank_rough": 0.0,
                "rank_cons_med": 0.0,
                "source_panel_default": 1.0,
                "source_balanced_viterbi": 0.0,
                "center_mild": 1.0,
                "state_mild": 1.0,
                "success": False,
                "mean": 999.0,
            },
        ]

        selector = fit_gt_free_selector(train_rows)
        selected = select_gt_free_family_rows(runtime_rows, selector)

        self.assertEqual(
            selected["live_a"]["family"],
            "panel_default_center_mild_state_mild",
        )
        self.assertNotIn("success", selector.feature_names)
        self.assertNotIn("mean", selector.feature_names)

    def test_cached_selector_reproduces_training_clips_without_gt_at_selection_time(self):
        rows = [
            {
                "clip": "a",
                "family": "bad",
                "rank_rough": 1.0,
                "rank_cons_med": 1.0,
                "source_panel_default": 0.0,
                "source_balanced_viterbi": 1.0,
                "success": False,
                "mean": 90.0,
            },
            {
                "clip": "a",
                "family": "good",
                "rank_rough": 0.0,
                "rank_cons_med": 0.0,
                "source_panel_default": 1.0,
                "source_balanced_viterbi": 0.0,
                "success": True,
                "mean": 10.0,
            },
        ]

        selector = fit_gt_free_selector(rows)
        runtime_rows = [
            {key: value for key, value in row.items() if key not in {"success", "mean"}}
            for row in rows
        ]
        selected = select_gt_free_family_rows(runtime_rows, selector)

        self.assertEqual(selected["a"]["family"], "good")
        self.assertEqual(summarize_selected_rows({"a": {**selected["a"], "success": True, "mean": 10.0}})["success"], 1)

    def test_cached_16gt_selector_scores_sixteen_without_runtime_gt_labels(self):
        rows = load_feature_rows_cache(DEFAULT_CACHE_PATH)
        selected = select_cached_rows_without_gt(DEFAULT_CACHE_PATH)
        score_by_key = {
            (row["clip"], row["family"]): row
            for row in rows
        }
        rescored = {
            clip: score_by_key[(clip, row["family"])]
            for clip, row in selected.items()
        }
        summary = summarize_selected_rows(rescored)

        self.assertEqual(summary["success"], 16)
        self.assertEqual(summary["total"], 16)
        self.assertLessEqual(summary["mean"], 40.0)

    def test_selector_model_round_trips_json(self):
        model = LinearSelectorModel(
            feature_names=("rank_rough", "source_panel_default"),
            weights=(1.5, -2.0),
            mean=(0.2, 0.5),
            scale=(0.4, 1.0),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "selector_model.json"

            save_gt_free_selector_model(path, model)
            loaded = load_gt_free_selector_model(path)

        self.assertEqual(loaded, model)


if __name__ == "__main__":
    unittest.main()
