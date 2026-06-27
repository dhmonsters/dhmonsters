# 라이브 temporal selector GT replay 채점 유틸을 검증합니다.
import unittest

from _live_temporal_selector_gt_score import replay_live_temporal_rows, score_rows_against_gt
from core.puzzle.live_temporal_selector import LiveTemporalDecision


class LiveTemporalSelectorGtScoreTests(unittest.TestCase):
    def test_replay_live_temporal_rows_uses_selector_decision_path_by_row_index(self) -> None:
        class _FakeSelector:
            def update(self, **kwargs):
                frame = int(kwargs["frame_index"])
                return LiveTemporalDecision(
                    point=(float(frame), float(frame + 1)),
                    source="fake",
                    reason="test",
                )

        rows = [{"i": 10, "cands": [[1.0, 2.0, 0.8, 4.0, 5.0]], "track": [9.0, 9.0]}]

        path, decisions = replay_live_temporal_rows(rows, selector=_FakeSelector())

        self.assertEqual(path, {0: (10.0, 11.0)})
        self.assertEqual(decisions[0]["source"], "fake")

    def test_score_rows_against_gt_scores_live_temporal_path(self) -> None:
        class _FakeSelector:
            def update(self, **_kwargs):
                return LiveTemporalDecision((3.0, 4.0), "fake", "test")

        result = score_rows_against_gt(
            [{"i": 0, "cands": [], "track": [0.0, 0.0]}],
            {0: (0.0, 0.0)},
            selector=_FakeSelector(),
            success_px=6.0,
        )

        self.assertTrue(result["selected"]["success"])
        self.assertAlmostEqual(result["selected"]["mean"], 5.0)

    def test_score_rows_against_gt_requires_minimum_coverage(self) -> None:
        class _FakeSelector:
            def update(self, **kwargs):
                if int(kwargs["frame_index"]) == 0:
                    return LiveTemporalDecision((0.0, 0.0), "fake", "test")
                return LiveTemporalDecision(None, "fake", "missing")

        result = score_rows_against_gt(
            [
                {"i": 0, "cands": [], "track": [0.0, 0.0]},
                {"i": 1, "cands": [], "track": [0.0, 0.0]},
            ],
            {0: (0.0, 0.0), 1: (0.0, 0.0)},
            selector=_FakeSelector(),
            success_px=1.0,
            min_coverage=0.9,
        )

        self.assertFalse(result["selected"]["success"])
        self.assertAlmostEqual(result["selected"]["coverage"], 0.5)


if __name__ == "__main__":
    unittest.main()
