# path pool 기반 selector 학습 cache 생성을 검증합니다.
import unittest

from _transparent_motion_feature_cache import build_motion_feature_rows_from_pool


class MotionFeatureCacheTests(unittest.TestCase):
    def test_build_motion_feature_rows_from_pool_adds_motion_features_and_gt_labels(self):
        frames = [0, 1, 2]
        paths = {
            "background_like": {
                0: (0.0, 0.0),
                1: (1.0, 0.0),
                2: (2.0, 0.0),
            },
            "also_background_like": {
                0: (10.0, 0.0),
                1: (11.0, 0.0),
                2: (12.0, 0.0),
            },
            "target_divergent": {
                0: (0.0, 40.0),
                1: (8.0, 40.0),
                2: (16.0, 40.0),
            },
        }
        gt = {
            0: (0.0, 40.0),
            1: (8.0, 40.0),
            2: (16.0, 40.0),
        }
        background_stats = {
            "background_like": {"matched_ratio": 0.9, "run_identity_ratio": 0.8},
            "also_background_like": {"matched_ratio": 0.8, "run_identity_ratio": 0.7},
            "target_divergent": {"matched_ratio": 0.1, "run_identity_ratio": 0.2},
        }

        rows = build_motion_feature_rows_from_pool(
            "clip_a",
            paths,
            frames,
            gt=gt,
            background_stats=background_stats,
        )
        by_family = {row["family"]: row for row in rows}
        target = by_family["target_divergent"]
        background = by_family["background_like"]

        self.assertEqual(len(rows), 3)
        self.assertTrue(target["success"])
        self.assertEqual(target["mean"], 0.0)
        self.assertLessEqual(target["coverage"], 1.0)
        self.assertIn("motion_div", target)
        self.assertIn("rank_high_motion_div", target)
        self.assertIn("bg_like", target)
        self.assertIn("rank_bg_like", target)
        self.assertGreater(target["motion_div"], background["motion_div"])
        self.assertLess(target["rank_high_motion_div"], background["rank_high_motion_div"])
        self.assertLess(target["rank_bg_like"], background["rank_bg_like"])


if __name__ == "__main__":
    unittest.main()
