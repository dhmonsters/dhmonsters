# 라이브 family pool GT 채점기의 빠른 반복 옵션을 검증합니다.
import unittest
from unittest.mock import patch

from _live_family_pool_gt_score import best_family_score, score_all
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


if __name__ == "__main__":
    unittest.main()
