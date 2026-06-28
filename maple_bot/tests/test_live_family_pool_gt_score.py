# 라이브 family pool GT 채점기의 빠른 반복 옵션을 검증합니다.
import unittest
from unittest.mock import patch

from _live_family_pool_gt_score import (
    best_family_score,
    occlusion_variant_paths,
    score_clip,
    score_all,
)
from core.vision.transparent_live_family_pool import LiveFamilyDecision


class LiveFamilyPoolGtScoreTests(unittest.TestCase):
    def test_best_family_score_accepts_injected_family_pool(self) -> None:
        class _FakePool:
            def update(self, frame_index, **_kwargs):
                return LiveFamilyDecision(
                    points={"fake_family": (float(frame_index), 0.0)},
                    debug={},
                )

        score = best_family_score(
            [{"i": 0, "cands": [], "track": [0.0, 0.0]}],
            {0: (0.0, 0.0)},
            family_pool=_FakePool(),
            success_px=1.0,
        )

        self.assertEqual(score["family"], "fake_family")
        self.assertTrue(score["success"])

    def test_score_all_fast_mode_creates_pool_per_clip(self) -> None:
        created = []

        class _FakePool:
            pass

        def _fake_pool():
            pool = _FakePool()
            created.append(pool)
            return pool

        with patch("_live_family_pool_gt_score._fast_family_pool", side_effect=_fake_pool):
            with patch("_live_family_pool_gt_score.score_clip") as score_clip:
                score_clip.side_effect = [
                    {"name": "a", "best_family": {"success": True}},
                    {"name": "b", "best_family": {"success": False}},
                ]

                results = score_all(names=["a", "b"], fast_mode=True)

        self.assertEqual(len(results), 2)
        self.assertEqual(len(created), 2)
        self.assertIs(score_clip.call_args_list[0].kwargs["family_pool"], created[0])
        self.assertIs(score_clip.call_args_list[1].kwargs["family_pool"], created[1])

    def test_score_all_forwards_occlusion_variant_option(self) -> None:
        with patch("_live_family_pool_gt_score.score_clip") as score_clip_mock:
            score_clip_mock.return_value = {"name": "a", "best_family": {"success": False}}

            score_all(names=["a"], include_occlusion_variants=True)

        self.assertTrue(score_clip_mock.call_args.kwargs["include_occlusion_variants"])

    def test_score_clip_loads_expected_background_for_occlusion_variants(self) -> None:
        with patch("_live_family_pool_gt_score._load_jsonl", return_value=[{"i": 0, "track": [0.0, 0.0], "cands": []}]):
            with patch("_live_family_pool_gt_score.load_red_gt", return_value={0: (0.0, 0.0)}):
                with patch(
                    "_live_family_pool_gt_score.expected_background_for_clip",
                    return_value={0: [(1, (10.0, 0.0, 12.0, 12.0, 0.9))]},
                ) as expected:
                    with patch("_live_family_pool_gt_score.best_family_score") as best:
                        best.return_value = {"family": "x", "success": False}

                        score_clip("clip", include_occlusion_variants=True)

        expected.assert_called_once()
        self.assertTrue(best.call_args.kwargs["include_occlusion_variants"])
        self.assertEqual(
            best.call_args.kwargs["expected_by_frame"],
            {0: [(1, (10.0, 0.0, 12.0, 12.0, 0.9))]},
        )

    def test_occlusion_variant_paths_coast_and_release_background_merge(self) -> None:
        paths = {
            "observed": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
                3: (55.0, 0.0),
                4: (60.0, 0.0),
            }
        }
        expected_by_frame = {
            3: [(1, (55.0, 0.0, 12.0, 12.0, 0.9))],
            4: [(1, (60.0, 0.0, 12.0, 12.0, 0.9))],
        }
        candidate_sets = {
            3: [(55.0, 0.0, 36.0, 12.0, 0.9)],
            4: [
                (40.0, 0.0, 12.0, 12.0, 0.9),
                (60.0, 0.0, 12.0, 12.0, 0.9),
            ],
        }

        variants = occlusion_variant_paths(
            paths,
            frames=[0, 1, 2, 3, 4],
            expected_by_frame=expected_by_frame,
            candidate_sets=candidate_sets,
        )

        self.assertEqual(variants["observed_occlusion_state"][3], (30.0, 0.0))
        self.assertEqual(variants["observed_occlusion_state"][4], (40.0, 0.0))

    def test_best_family_score_can_select_occlusion_variant(self) -> None:
        class _FakePool:
            def update(self, frame_index, **_kwargs):
                points = {
                    0: (0.0, 0.0),
                    1: (10.0, 0.0),
                    2: (20.0, 0.0),
                    3: (55.0, 0.0),
                    4: (60.0, 0.0),
                }
                return LiveFamilyDecision(
                    points={"observed": points[int(frame_index)]},
                    debug={},
                )

        rows = [
            {"i": frame, "track": [0.0, 0.0], "cands": []}
            for frame in range(5)
        ]
        expected_by_frame = {
            3: [(1, (55.0, 0.0, 12.0, 12.0, 0.9))],
            4: [(1, (60.0, 0.0, 12.0, 12.0, 0.9))],
        }
        candidate_sets = {
            3: [(55.0, 0.0, 36.0, 12.0, 0.9)],
            4: [
                (40.0, 0.0, 12.0, 12.0, 0.9),
                (60.0, 0.0, 12.0, 12.0, 0.9),
            ],
        }

        score = best_family_score(
            rows,
            {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (20.0, 0.0), 3: (30.0, 0.0), 4: (40.0, 0.0)},
            family_pool=_FakePool(),
            success_px=5.0,
            include_occlusion_variants=True,
            expected_by_frame=expected_by_frame,
            candidate_sets=candidate_sets,
        )

        self.assertEqual(score["family"], "observed_occlusion_state")
        self.assertTrue(score["success"])


if __name__ == "__main__":
    unittest.main()
