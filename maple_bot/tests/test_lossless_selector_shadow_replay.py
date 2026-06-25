# 무손실 녹화의 selector_shadow 오프라인 재생과 채점을 검증합니다.
import unittest

from _lossless_selector_shadow_replay import (
    lossless_valid_frames,
    replay_shadow_path_from_rows,
    score_path,
)


class FakeRuntime:
    available = True
    load_error = ""

    def select_from_path_pool(self, clip, paths, frames, **kwargs):
        family = "panel_default_center_mild_state_mild"
        row = {
            "clip": clip,
            "family": family,
            "rank_center": 0.0,
            "rank_rough": 0.0,
        }
        return {clip: row}, [row]


class LosslessSelectorShadowReplayTests(unittest.TestCase):
    def test_lossless_valid_frames_excludes_cursor_ranges_and_bad_frames(self):
        gt = {index: (float(index), 0.0) for index in range(45)}

        frames = lossless_valid_frames(
            "000_0621_165634",
            gt,
            frame_count=45,
            bad_frames={31},
        )

        self.assertNotIn(0, frames)
        self.assertNotIn(3, frames)
        self.assertNotIn(31, frames)
        self.assertNotIn(36, frames)
        self.assertNotIn(42, frames)
        self.assertIn(4, frames)
        self.assertIn(35, frames)
        self.assertIn(43, frames)

    def test_score_path_reports_mean_max_success_and_worst_frames(self):
        gt = {
            0: (0.0, 0.0),
            1: (10.0, 0.0),
            2: (20.0, 0.0),
        }
        path = {
            0: (3.0, 4.0),
            1: (16.0, 8.0),
        }

        score = score_path(path, gt, [0, 1, 2])

        self.assertEqual(score["n"], 2)
        self.assertAlmostEqual(score["mean"], 7.5)
        self.assertAlmostEqual(score["max"], 10.0)
        self.assertTrue(score["success"])
        self.assertEqual(score["worst"][0]["frame"], 1)

    def test_replay_shadow_path_uses_track_anchor(self):
        rows = [
            {
                "track": [10 + frame, 20],
                "cands": [
                    [10 + frame, 20, 0.9, 20, 20],
                    [100, 100, 0.1, 20, 20],
                ],
            }
            for frame in range(4)
        ]

        path, records = replay_shadow_path_from_rows(
            rows,
            runtime=FakeRuntime(),
            clip_id="sample",
            window=4,
            min_frames=2,
            max_candidates=4,
            include_local_box=False,
        )

        self.assertEqual(path[1], (11.0, 20.0))
        self.assertEqual(path[3], (13.0, 20.0))
        self.assertEqual(records[3]["family"], "panel_default_center_mild_state_mild")


if __name__ == "__main__":
    unittest.main()
