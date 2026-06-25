# 라이브와 녹화 공용 family selector feature row 생성을 검증합니다.
import unittest
import warnings

import _phase_catalog_score as phase_catalog
import _local_box_family_score as local_box
from core.vision.transparent_feature_rows import (
    build_transparent_feature_rows,
    nearest_candidate_distance,
    path_consensus_median,
)


class TransparentFeatureRowsTests(unittest.TestCase):
    def test_nearest_candidate_distance_uses_frame_candidates(self):
        distance = nearest_candidate_distance(
            (10.0, 10.0),
            [
                (40.0, 10.0, 0.8, 20.0, 20.0),
                (13.0, 14.0, 0.7, 20.0, 20.0),
            ],
        )

        self.assertAlmostEqual(distance, 5.0)

    def test_path_consensus_median_measures_distance_to_other_families(self):
        frames = [0, 1]
        paths = {
            "near_a": {0: (0.0, 0.0), 1: (10.0, 0.0)},
            "near_b": {0: (1.0, 0.0), 1: (11.0, 0.0)},
            "far": {0: (100.0, 0.0), 1: (110.0, 0.0)},
        }

        self.assertLess(
            path_consensus_median(paths["near_a"], paths, frames),
            path_consensus_median(paths["far"], paths, frames),
        )

    def test_build_rows_adds_name_quality_and_rank_features_without_gt_labels(self):
        frames = [0, 1, 2]
        paths = {
            "panel_default_center_mild_state_mild": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
            },
            "balanced_viterbi_center_mild_state_mild_lb_free": {
                0: (0.0, 0.0),
                1: (50.0, 0.0),
                2: (20.0, 0.0),
            },
        }
        meta = {
            "panel_default_center_mild_state_mild": {
                "source": "panel_default_center_mild_state_mild",
                "mode": "state",
            },
            "balanced_viterbi_center_mild_state_mild_lb_free": {
                "source": "balanced_viterbi_center_mild_state_mild",
                "mode": "local_box",
                "variant": "free",
            },
        }
        candidate_sets = {
            0: [(0.0, 0.0, 0.9, 20.0, 20.0)],
            1: [(10.0, 0.0, 0.9, 20.0, 20.0), (50.0, 0.0, 0.7, 20.0, 20.0)],
            2: [(20.0, 0.0, 0.9, 20.0, 20.0)],
        }

        rows = build_transparent_feature_rows(
            "live_clip",
            paths,
            frames,
            meta=meta,
            candidate_sets=candidate_sets,
        )
        by_family = {row["family"]: row for row in rows}
        steady = by_family["panel_default_center_mild_state_mild"]
        jumpy = by_family["balanced_viterbi_center_mild_state_mild_lb_free"]

        self.assertEqual(len(rows), 2)
        self.assertEqual(steady["clip"], "live_clip")
        self.assertEqual(steady["source_panel_default"], 1.0)
        self.assertEqual(jumpy["source_balanced_viterbi"], 1.0)
        self.assertEqual(jumpy["variant_free"], 1.0)
        self.assertLess(steady["rough"], jumpy["rough"])
        self.assertLess(steady["rank_rough"], jumpy["rank_rough"])
        self.assertIn("rank_cons_med", steady)
        self.assertNotIn("success", steady)
        self.assertNotIn("mean", steady)
        self.assertNotIn("max", steady)
        self.assertNotIn("coverage", steady)

    def test_optional_background_and_residual_stats_are_mapped_to_selector_columns(self):
        rows = build_transparent_feature_rows(
            "live_clip",
            {"family_a": {0: (0.0, 0.0)}},
            [0],
            background_stats={
                "family_a": {
                    "matched_ratio": 0.25,
                    "run_identity_ratio": 0.75,
                    "id_switches": 2,
                },
            },
            residual_stats={
                "family_a": {
                    "contrast_mean": 4.0,
                    "contrast_median": 5.0,
                    "ring_mean": 6.0,
                },
            },
        )

        row = rows[0]
        self.assertEqual(row["match"], 0.25)
        self.assertEqual(row["run"], 0.75)
        self.assertEqual(row["idsw"], 2.0)
        self.assertEqual(row["contrast"], 4.0)
        self.assertEqual(row["contrast_med"], 5.0)
        self.assertEqual(row["ring"], 6.0)

    def test_build_rows_from_recorded_local_box_pool_has_selector_columns(self):
        name = "000_0615_035137"
        gt = phase_catalog.load_gt(name)
        frames = sorted(gt)[:12]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ResourceWarning)
            paths, meta, _failures = local_box.local_box_family_paths(
                name,
                frames=frames,
                max_local_box_families=2,
            )

        rows = build_transparent_feature_rows(
            name,
            paths,
            frames,
            meta=meta,
        )

        self.assertGreaterEqual(len(rows), 2)
        self.assertTrue(all(row["clip"] == name for row in rows))
        self.assertTrue(all("rank_rough" in row for row in rows))
        self.assertTrue(all("rank_cons_med" in row for row in rows))
        self.assertTrue(all("source_panel_default" in row for row in rows))


if __name__ == "__main__":
    unittest.main()
