# local-box family가 후보 박스 내부의 매끄러운 경로를 생성하는지 검증합니다.
import unittest

from _local_box_family_score import (
    LocalBoxVariant,
    augment_local_box_paths,
    local_box_smooth_path,
    select_local_box_family_names,
)


class LocalBoxFamilyTests(unittest.TestCase):
    def test_local_box_smooth_path_uses_smooth_internal_point(self):
        frames = [0, 1, 2]
        anchor_path = {
            0: (0.0, 0.0),
            1: (50.0, 0.0),
            2: (20.0, 0.0),
        }
        candidate_sets = {
            0: [(0.0, 0.0, 10.0, 10.0, 0.9)],
            1: [(50.0, 0.0, 80.0, 10.0, 0.9)],
            2: [(20.0, 0.0, 10.0, 10.0, 0.9)],
        }

        path = local_box_smooth_path(
            anchor_path,
            candidate_sets,
            frames,
            grid_size=3,
            shrink=1.0,
            max_dist=80.0,
            fallback_candidates=1,
            transition_weight=0.2,
            accel_weight=1.0,
            anchor_weight=0.0,
            center_weight=0.2,
        )

        self.assertEqual(path[1], (10.0, 0.0))

    def test_augment_local_box_paths_adds_named_variants(self):
        frames = [0]
        paths = {"base": {0: (10.0, 10.0)}}
        candidate_sets = {0: [(10.0, 10.0, 20.0, 20.0, 0.8)]}
        variants = [
            LocalBoxVariant(
                "test",
                transition_weight=0.1,
                accel_weight=0.0,
                anchor_weight=0.0,
                center_weight=1.0,
            ),
        ]

        out = augment_local_box_paths(paths, candidate_sets, frames, variants=variants)

        self.assertIn("base", out)
        self.assertIn("base_lb_test", out)
        self.assertEqual(out["base_lb_test"][0], (10.0, 10.0))

    def test_select_local_box_family_names_prioritizes_hard_clip_sources(self):
        paths = {
            "phase_catalog_center_aggressive": {},
            "balanced_viterbi_state_mild": {},
            "panel_default_center_mild": {},
            "merge_context": {},
            "mht_motion_bg_offset_aggressive": {},
        }
        meta = {
            "balanced_viterbi_state_mild": {"source": "balanced_viterbi", "mode": "state"},
            "panel_default_center_mild": {"source": "panel_default", "mode": "base"},
            "merge_context": {"source": "merge_context", "mode": "base"},
            "mht_motion_bg_offset_aggressive": {"source": "mht_motion_bg", "mode": "offset"},
            "phase_catalog_center_aggressive": {"source": "phase_catalog", "mode": "base"},
        }

        selected = select_local_box_family_names(paths, meta, max_families=3)

        self.assertEqual(
            selected,
            [
                "balanced_viterbi_state_mild",
                "panel_default_center_mild",
                "merge_context",
            ],
        )

    def test_augment_local_box_paths_can_limit_local_box_families(self):
        frames = [0]
        paths = {
            "keep": {0: (10.0, 10.0)},
            "skip": {0: (10.0, 10.0)},
        }
        candidate_sets = {0: [(10.0, 10.0, 20.0, 20.0, 0.8)]}
        variants = [
            LocalBoxVariant(
                "test",
                transition_weight=0.1,
                accel_weight=0.0,
                anchor_weight=0.0,
                center_weight=1.0,
            ),
        ]

        out = augment_local_box_paths(
            paths,
            candidate_sets,
            frames,
            variants=variants,
            local_box_families=["keep"],
        )

        self.assertIn("keep_lb_test", out)
        self.assertNotIn("skip_lb_test", out)


if __name__ == "__main__":
    unittest.main()
