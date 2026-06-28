# 저장된 모델로 투명 퍼즐 family를 선택하는 런타임 어댑터를 검증합니다.
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _final_candidate_selector import LinearSelectorModel
from _final_candidate_selector import load_feature_rows_cache, summarize_selected_rows
from _gt_free_family_selector import load_gt_free_selector_model, save_gt_free_selector_model
from _offline_16gt_solver import DEFAULT_CACHE_PATH
from core.vision.transparent_family_selector_runtime import (
    DEFAULT_MODEL_PATH,
    TransparentFamilySelectorRuntime,
    strip_gt_score_labels,
)


class TransparentFamilySelectorRuntimeTests(unittest.TestCase):
    def test_strip_gt_score_labels_removes_offline_score_columns(self):
        row = {
            "clip": "live",
            "family": "target",
            "rank_rough": 0.0,
            "success": False,
            "mean": 999.0,
            "max": 1000.0,
            "coverage": 0.0,
        }

        stripped = strip_gt_score_labels(row)

        self.assertEqual(stripped["family"], "target")
        self.assertNotIn("success", stripped)
        self.assertNotIn("mean", stripped)
        self.assertNotIn("max", stripped)
        self.assertNotIn("coverage", stripped)

    def test_runtime_selects_with_saved_model_without_using_gt_labels(self):
        model = LinearSelectorModel(
            feature_names=("rank_rough",),
            weights=(-1.0,),
            mean=(0.0,),
            scale=(1.0,),
        )
        rows = [
            {
                "clip": "live",
                "family": "bad",
                "rank_rough": 1.0,
                "success": True,
                "mean": 1.0,
            },
            {
                "clip": "live",
                "family": "good",
                "rank_rough": 0.0,
                "success": False,
                "mean": 999.0,
            },
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.json"
            save_gt_free_selector_model(path, model)
            runtime = TransparentFamilySelectorRuntime(path)

            selected = runtime.select(rows)

        self.assertTrue(runtime.available)
        self.assertEqual(selected["live"]["family"], "good")
        self.assertNotIn("success", selected["live"])
        self.assertNotIn("mean", selected["live"])

    def test_runtime_missing_model_is_unavailable_and_returns_empty_selection(self):
        runtime = TransparentFamilySelectorRuntime(Path("missing_model.json"))

        self.assertFalse(runtime.available)
        self.assertEqual(runtime.select([{"clip": "live", "family": "a"}]), {})

    def test_default_model_file_is_available_for_planet_solver_runtime(self):
        runtime = TransparentFamilySelectorRuntime(DEFAULT_MODEL_PATH)

        self.assertTrue(DEFAULT_MODEL_PATH.exists())
        self.assertTrue(runtime.available)
        self.assertEqual(runtime.load_error, "")

    def test_default_model_contains_refreshed_selector_signal_features(self):
        model = load_gt_free_selector_model(DEFAULT_MODEL_PATH)

        self.assertIn("rank_bg_like", model.feature_names)
        self.assertIn("rank_high_divergence", model.feature_names)

    def test_default_model_reproduces_sixteen_cached_gt_clips_without_runtime_labels(self):
        rows = load_feature_rows_cache(DEFAULT_CACHE_PATH)
        runtime = TransparentFamilySelectorRuntime(DEFAULT_MODEL_PATH)

        selected = runtime.select(rows)
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

    def test_runtime_selects_from_path_pool_rows(self):
        model = LinearSelectorModel(
            feature_names=("rank_rough",),
            weights=(-1.0,),
            mean=(0.0,),
            scale=(1.0,),
        )
        paths = {
            "steady": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
            },
            "jumpy": {
                0: (0.0, 0.0),
                1: (50.0, 0.0),
                2: (20.0, 0.0),
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.json"
            save_gt_free_selector_model(path, model)
            runtime = TransparentFamilySelectorRuntime(path)

            selected, rows = runtime.select_from_path_pool(
                "live_clip",
                paths,
                [0, 1, 2],
            )

        self.assertEqual(selected["live_clip"]["family"], "steady")
        self.assertEqual(len(rows), 2)
        self.assertIn("rank_rough", rows[0])

    def test_runtime_path_pool_prefers_judge_scoreboard_when_candidate_sets_are_available(self):
        model = LinearSelectorModel(
            feature_names=("rank_rough",),
            weights=(-1.0,),
            mean=(0.0,),
            scale=(1.0,),
        )
        paths = {
            "raw_candidate_cont12_center_mild_state_mild": {
                0: (100.0, 0.0),
                1: (110.0, 0.0),
                2: (120.0, 0.0),
            },
            "raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at1_state_mild": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
            },
        }
        candidate_sets = {
            0: [(0.0, 0.0, 0.90, 24.0, 24.0), (100.0, 0.0, 0.55, 24.0, 24.0)],
            1: [(10.0, 0.0, 0.90, 24.0, 24.0), (110.0, 0.0, 0.55, 24.0, 24.0)],
            2: [(20.0, 0.0, 0.90, 24.0, 24.0), (120.0, 0.0, 0.55, 24.0, 24.0)],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.json"
            save_gt_free_selector_model(path, model)
            runtime = TransparentFamilySelectorRuntime(path)

            with patch(
                "core.vision.transparent_family_selector_runtime.build_transparent_feature_rows",
                side_effect=AssertionError("scoreboard selection should skip feature rows"),
            ):
                selected, rows = runtime.select_from_path_pool(
                    "live_clip",
                    paths,
                    [0, 1, 2],
                    candidate_sets=candidate_sets,
                    anchor_points={0: (106.5, 0.0), 1: (116.5, 0.0), 2: (126.5, 0.0)},
                )

        self.assertEqual(
            selected["live_clip"]["family"],
            "raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at1_state_mild",
        )
        self.assertEqual(selected["live_clip"]["selector"], "judge_scoreboard")
        self.assertIn("judge_total_score", selected["live_clip"])
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
