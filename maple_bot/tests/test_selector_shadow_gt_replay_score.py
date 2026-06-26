# selector shadow rescue를 GT 리플레이에서 채점하는 흐름을 검증합니다.
import unittest

from _selector_shadow_gt_replay_score import (
    apply_live_health_selection,
    score_path,
    track_path_from_rows,
)


class SelectorShadowGtReplayScoreTests(unittest.TestCase):
    def test_track_path_from_rows_uses_row_order_frames(self):
        rows = [
            {"i": 10, "track": [1.0, 2.0]},
            {"i": 11, "track": None},
            {"i": 12, "track": [3.0, 4.0]},
        ]

        path = track_path_from_rows(rows)

        self.assertEqual(path, {0: (1.0, 2.0), 2: (3.0, 4.0)})

    def test_health_selection_keeps_healthy_primary_even_when_rescue_exists(self):
        rows = [
            {"track": [0.0, 0.0]},
            {
                "track": [10.0, 0.0],
                "selector_shadow": {
                    "available": True,
                    "rescue_allowed": True,
                    "rescue_point": [80.0, 0.0],
                },
            },
        ]

        path, decisions = apply_live_health_selection(rows, frame_shape=(200, 200))

        self.assertEqual(path[0], (0.0, 0.0))
        self.assertEqual(path[1], (10.0, 0.0))
        self.assertEqual(decisions[1]["source"], "primary")

    def test_health_selection_uses_allowed_rescue_when_primary_jumps(self):
        rows = [
            {"track": [0.0, 0.0]},
            {"track": [10.0, 0.0]},
            {
                "track": [250.0, 0.0],
                "selector_shadow": {
                    "available": True,
                    "rescue_allowed": True,
                    "rescue_point": [20.0, 0.0],
                },
            },
        ]

        path, decisions = apply_live_health_selection(rows, frame_shape=(300, 300))

        self.assertEqual(path[2], (20.0, 0.0))
        self.assertEqual(decisions[2]["source"], "rescue")
        self.assertEqual(decisions[2]["reason"], "primary_immediate_jump")

    def test_health_selection_ignores_blocked_rescue(self):
        rows = [
            {"track": [0.0, 0.0]},
            {"track": [10.0, 0.0]},
            {
                "track": [250.0, 0.0],
                "selector_shadow": {
                    "available": True,
                    "rescue_allowed": False,
                    "rescue_point": [20.0, 0.0],
                },
            },
        ]

        path, decisions = apply_live_health_selection(rows, frame_shape=(300, 300))

        self.assertEqual(path[2], (250.0, 0.0))
        self.assertEqual(decisions[2]["source"], "primary")

    def test_score_path_reports_success_by_mean_error(self):
        gt = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (20.0, 0.0)}
        path = {0: (3.0, 4.0), 1: (16.0, 8.0)}

        score = score_path(path, gt, [0, 1, 2], success_px=8.0)

        self.assertEqual(score["n"], 2)
        self.assertAlmostEqual(score["mean"], 7.5)
        self.assertAlmostEqual(score["max"], 10.0)
        self.assertTrue(score["success"])
        self.assertEqual(score["worst"][0]["frame"], 1)


if __name__ == "__main__":
    unittest.main()
