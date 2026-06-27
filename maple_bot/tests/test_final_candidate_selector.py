# final selector가 평가할 pattern family shortlist를 검증합니다.
import tempfile
import unittest
from pathlib import Path

from _final_candidate_selector import (
    add_conditional_feature_rows,
    add_occlusion_release_proxy_rows,
    add_interaction_feature_rows,
    add_selector_provenance_feature_rows,
    add_variant_divergence_feature_rows,
    build_feature_table,
    family_name_features,
    is_pattern_candidate_family,
    LinearSelectorModel,
    load_feature_rows_cache,
    pattern_candidate_families,
    rank_normalized_feature_rows,
    rank_linear_feature_rows,
    save_feature_rows_cache,
    fit_success_perceptron_selector,
    select_weighted_feature_table,
    select_weighted_feature_rows,
    select_linear_feature_rows,
    selector_bank_oracle,
    summarize_selected_rows,
)


class FinalCandidateSelectorTests(unittest.TestCase):
    def test_is_pattern_candidate_family_includes_hard_clip_winners(self):
        self.assertTrue(is_pattern_candidate_family("balanced_viterbi_state_mild_lb_free"))
        self.assertTrue(is_pattern_candidate_family("panel_default_center_mild_lb_smooth"))
        self.assertTrue(is_pattern_candidate_family("merge_context_center_mild_offset_mild"))
        self.assertTrue(is_pattern_candidate_family("strict_transition_viterbi_center_mild_state_medium_lb_loose"))

    def test_is_pattern_candidate_family_rejects_unrelated_or_unhelpful_names(self):
        self.assertFalse(is_pattern_candidate_family("random_tracker_state_mild_lb_free"))
        self.assertFalse(is_pattern_candidate_family("balanced_viterbi_center_aggressive_offset_aggressive"))
        self.assertFalse(is_pattern_candidate_family("phase_catalog_center_medium_offset_aggressive"))

    def test_pattern_candidate_families_preserves_existing_paths(self):
        paths = {
            "balanced_viterbi_state_mild_lb_free": {0: (1.0, 1.0)},
            "balanced_viterbi_center_aggressive_offset_aggressive": {0: (2.0, 2.0)},
            "panel_default_center_mild_lb_smooth": {0: (3.0, 3.0)},
        }

        out = pattern_candidate_families(paths)

        self.assertEqual(
            sorted(out),
            [
                "balanced_viterbi_state_mild_lb_free",
                "panel_default_center_mild_lb_smooth",
            ],
        )
        self.assertIs(out["panel_default_center_mild_lb_smooth"], paths["panel_default_center_mild_lb_smooth"])

    def test_family_name_features_extracts_source_variant_and_state_tokens(self):
        features = family_name_features("panel_default_center_mild_offset_medium_lb_smooth")

        self.assertEqual(features["source_panel_default"], 1.0)
        self.assertEqual(features["variant_smooth"], 1.0)
        self.assertEqual(features["center_mild"], 1.0)
        self.assertEqual(features["offset_medium"], 1.0)
        self.assertEqual(features["state_medium"], 0.0)

    def test_rank_normalized_feature_rows_scales_inside_each_clip(self):
        rows = [
            {"clip": "a", "family": "bad", "rough": 20.0, "support": 1.0},
            {"clip": "a", "family": "good", "rough": 10.0, "support": 5.0},
            {"clip": "b", "family": "only", "rough": 99.0, "support": 0.0},
        ]

        ranked = rank_normalized_feature_rows(
            rows,
            lower_is_better=("rough",),
            higher_is_better=("support",),
        )

        by_family = {row["family"]: row for row in ranked}
        self.assertEqual(by_family["good"]["rank_rough"], 0.0)
        self.assertEqual(by_family["bad"]["rank_rough"], 1.0)
        self.assertEqual(by_family["good"]["rank_high_support"], 0.0)
        self.assertEqual(by_family["bad"]["rank_high_support"], 1.0)
        self.assertEqual(by_family["only"]["rank_rough"], 0.0)
        self.assertEqual(by_family["only"]["rank_high_support"], 0.0)

    def test_select_weighted_feature_rows_picks_lowest_cost_per_clip(self):
        rows = rank_normalized_feature_rows(
            [
                {"clip": "a", "family": "noisy", "rough": 20.0, "support": 1.0},
                {"clip": "a", "family": "target_like", "rough": 10.0, "support": 5.0},
                {"clip": "b", "family": "stable", "rough": 3.0, "support": 0.0},
                {"clip": "b", "family": "jumpy", "rough": 30.0, "support": 9.0},
            ],
            lower_is_better=("rough",),
            higher_is_better=("support",),
        )

        selected = select_weighted_feature_rows(
            rows,
            {
                "rank_rough": 2.0,
                "rank_high_support": 1.0,
            },
        )

        self.assertEqual(selected["a"]["family"], "target_like")
        self.assertEqual(selected["b"]["family"], "stable")

    def test_select_weighted_feature_table_reuses_matrix_for_fast_selection(self):
        rows = [
            {"clip": "a", "family": "noisy", "rank_rough": 1.0, "rank_high_support": 1.0},
            {"clip": "a", "family": "target_like", "rank_rough": 0.0, "rank_high_support": 0.0},
            {"clip": "b", "family": "stable", "rank_rough": 0.0, "rank_high_support": 1.0},
            {"clip": "b", "family": "jumpy", "rank_rough": 1.0, "rank_high_support": 0.0},
        ]
        table = build_feature_table(rows, ("rank_rough", "rank_high_support"))

        selected = select_weighted_feature_table(
            table,
            {
                "rank_rough": 2.0,
                "rank_high_support": 1.0,
            },
        )

        self.assertEqual(selected["a"]["family"], "target_like")
        self.assertEqual(selected["b"]["family"], "stable")
        self.assertEqual(table.feature_names, ("rank_rough", "rank_high_support"))

    def test_feature_rows_cache_round_trips_json_rows(self):
        rows = [
            {"clip": "a", "family": "target", "mean": 12.5, "success": True},
            {"clip": "b", "family": "decal", "mean": 55.0, "success": False},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.json"

            save_feature_rows_cache(path, rows)
            loaded = load_feature_rows_cache(path)

        self.assertEqual(loaded, rows)

    def test_feature_rows_cache_loads_utf8_bom_files_from_powershell(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.json"
            path.write_text('{"rows":[{"clip":"a","family":"target"}]}', encoding="utf-8-sig")

            loaded = load_feature_rows_cache(path)

        self.assertEqual(loaded, [{"clip": "a", "family": "target"}])

    def test_selector_bank_oracle_picks_best_candidate_per_clip(self):
        selector_picks = {
            "smooth": {
                "a": {"clip": "a", "family": "wrong", "mean": 80.0, "success": False},
                "b": {"clip": "b", "family": "ok", "mean": 10.0, "success": True},
            },
            "outlier": {
                "a": {"clip": "a", "family": "ok", "mean": 12.0, "success": True},
                "b": {"clip": "b", "family": "bad", "mean": 50.0, "success": False},
            },
        }

        picked = selector_bank_oracle(selector_picks)
        summary = summarize_selected_rows(picked)

        self.assertEqual(picked["a"]["family"], "ok")
        self.assertEqual(picked["a"]["selector_name"], "outlier")
        self.assertEqual(picked["b"]["family"], "ok")
        self.assertEqual(summary["success"], 2)
        self.assertEqual(summary["total"], 2)

    def test_add_interaction_feature_rows_adds_product_terms_without_mutating_input(self):
        rows = [{"clip": "a", "source_panel": 1.0, "rank_rough": 0.25}]

        out = add_interaction_feature_rows(rows, [("source_panel", "rank_rough")])

        self.assertEqual(out[0]["source_panel*rank_rough"], 0.25)
        self.assertNotIn("source_panel*rank_rough", rows[0])

    def test_selector_provenance_counts_independent_selector_groups(self):
        rows = [
            {"clip": "a", "family": "target"},
            {"clip": "a", "family": "decal"},
        ]
        selector_picks = {
            "smooth_a": {"a": {"clip": "a", "family": "target"}},
            "smooth_b": {"a": {"clip": "a", "family": "target"}},
            "outlier": {"a": {"clip": "a", "family": "target"}},
            "decal_vote": {"a": {"clip": "a", "family": "decal"}},
        }

        out = add_selector_provenance_feature_rows(
            rows,
            selector_picks,
            selector_groups={
                "smooth_a": "smooth",
                "smooth_b": "smooth",
                "outlier": "outlier",
                "decal_vote": "decal",
            },
        )

        by_family = {row["family"]: row for row in out}
        self.assertEqual(by_family["target"]["selector_vote_count"], 3.0)
        self.assertEqual(by_family["target"]["selector_group_count"], 2.0)
        self.assertEqual(by_family["decal"]["selector_group_count"], 1.0)

    def test_variant_divergence_measures_sibling_feature_spread(self):
        rows = [
            {"clip": "a", "family": "root_lb_free", "rank_cons_med": 0.0, "rank_rough": 0.0},
            {"clip": "a", "family": "root_lb_loose", "rank_cons_med": 0.5, "rank_rough": 0.25},
            {"clip": "a", "family": "root_lb_smooth", "rank_cons_med": 1.0, "rank_rough": 0.5},
            {"clip": "a", "family": "other_lb_free", "rank_cons_med": 0.2, "rank_rough": 0.2},
        ]

        out = add_variant_divergence_feature_rows(rows, feature_names=("rank_cons_med", "rank_rough"))

        by_family = {row["family"]: row for row in out}
        self.assertEqual(by_family["root_lb_free"]["variant_sibling_count"], 3.0)
        self.assertGreater(by_family["root_lb_free"]["variant_feature_spread_mean"], 0.0)
        self.assertEqual(by_family["other_lb_free"]["variant_sibling_count"], 1.0)
        self.assertEqual(by_family["other_lb_free"]["variant_feature_spread_mean"], 0.0)

    def test_occlusion_release_proxy_rewards_smooth_consensus_outliers(self):
        rows = [
            {"clip": "a", "family": "release", "rank_cons_med": 0.9, "rank_rough": 0.1, "rank_run": 0.8},
            {"clip": "a", "family": "decal", "rank_cons_med": 0.2, "rank_rough": 0.1, "rank_run": 0.1},
        ]

        out = add_occlusion_release_proxy_rows(rows)

        by_family = {row["family"]: row for row in out}
        self.assertGreater(
            by_family["release"]["occlusion_release_proxy"],
            by_family["decal"]["occlusion_release_proxy"],
        )

    def test_add_conditional_feature_rows_adds_anchor_products(self):
        rows = [
            {"clip": "a", "source_panel_default": 1.0, "rank_rough": 0.25},
            {"clip": "a", "source_panel_default": 0.0, "rank_rough": 0.75},
        ]

        out = add_conditional_feature_rows(
            rows,
            anchor_features=("source_panel_default",),
            conditioned_features=("rank_rough",),
        )

        self.assertEqual(out[0]["source_panel_default*rank_rough"], 0.25)
        self.assertEqual(out[1]["source_panel_default*rank_rough"], 0.0)
        self.assertNotIn("source_panel_default*rank_rough", rows[0])

    def test_fit_success_perceptron_selector_learns_clipwise_success(self):
        rows = [
            {"clip": "a", "family": "a_bad", "good_signal": 0.0, "success": False, "mean": 80.0},
            {"clip": "a", "family": "a_good", "good_signal": 1.0, "success": True, "mean": 10.0},
            {"clip": "b", "family": "b_bad", "good_signal": 0.2, "success": False, "mean": 90.0},
            {"clip": "b", "family": "b_good", "good_signal": 0.8, "success": True, "mean": 12.0},
        ]

        model = fit_success_perceptron_selector(
            rows,
            feature_names=("good_signal",),
            max_epochs=10,
        )
        selected = select_linear_feature_rows(rows, model)

        self.assertEqual(selected["a"]["family"], "a_good")
        self.assertEqual(selected["b"]["family"], "b_good")

    def test_rank_linear_feature_rows_exposes_selector_scores_per_clip(self):
        rows = [
            {"clip": "a", "family": "low", "signal": 0.1},
            {"clip": "a", "family": "high", "signal": 0.9},
            {"clip": "b", "family": "only", "signal": 0.2},
        ]
        model = LinearSelectorModel(
            feature_names=("signal",),
            weights=(1.0,),
            mean=(0.0,),
            scale=(1.0,),
        )

        ranked = rank_linear_feature_rows(rows, model)

        self.assertEqual(ranked["a"][0]["family"], "high")
        self.assertEqual(ranked["a"][0]["selector_rank"], 0)
        self.assertGreater(ranked["a"][0]["selector_score"], ranked["a"][1]["selector_score"])
        self.assertEqual(ranked["b"][0]["selector_rank"], 0)


if __name__ == "__main__":
    unittest.main()
