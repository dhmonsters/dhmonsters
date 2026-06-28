# 라이브 temporal selector GT replay 채점 유틸을 검증합니다.
import math
import unittest

from _live_temporal_selector_gt_score import (
    compact_results,
    replay_live_temporal_rows,
    score_rows_against_gt,
    summarize,
)
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

    def test_score_rows_against_gt_can_skip_heavy_decision_payloads(self) -> None:
        class _FakeSelector:
            def update(self, **_kwargs):
                return LiveTemporalDecision(
                    (1.0, 1.0),
                    "fake",
                    "test",
                    selector_record={"large": list(range(100))},
                )

        result = score_rows_against_gt(
            [{"i": 0, "cands": [], "track": [0.0, 0.0]}],
            {0: (1.0, 1.0)},
            selector=_FakeSelector(),
            collect_decisions=False,
        )

        self.assertEqual(result["decisions"], {})
        self.assertEqual(result["selector_records"], 1)

    def test_compact_results_keeps_only_summary_fields(self) -> None:
        compact = compact_results([
            {
                "name": "clip",
                "selected": {
                    "success": True,
                    "mean": 12.5,
                    "max": 22.0,
                    "coverage": 1.0,
                    "n": 3,
                    "worst": [{"frame": 1}],
                },
                "selector_records": 7,
            }
        ])

        self.assertEqual(compact[0]["name"], "clip")
        self.assertEqual(compact[0]["selector_records"], 7)
        self.assertNotIn("worst", compact[0]["selected"])

    def test_summarize_counts_success_and_mean(self) -> None:
        summary = summarize([
            {"selected": {"success": True, "mean": 10.0}},
            {"selected": {"success": False, "mean": 30.0}},
        ])

        self.assertEqual(summary["success"], 1)
        self.assertEqual(summary["total"], 2)
        self.assertTrue(math.isclose(summary["mean"], 20.0))


if __name__ == "__main__":
    unittest.main()
