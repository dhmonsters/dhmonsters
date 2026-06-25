# 무손실 녹화의 selector_shadow 오프라인 재생과 채점을 검증합니다.
import unittest

import numpy as np

from _lossless_selector_shadow_replay import (
    lossless_valid_frames,
    path_health,
    raw_candidate_anchor_paths,
    replay_shadow_path_from_rows,
    score_path,
    select_path_by_track_health,
    track_rescue_beam_path,
    track_rescue_candidate_path,
    track_rescue_visual_beam_path,
    visual_rank_scores_for_candidates,
)


class FakeRuntime:
    available = True
    load_error = ""

    def __init__(self, family="panel_default_center_mild_state_mild"):
        self.family = family

    def select_from_path_pool(self, clip, paths, frames, **kwargs):
        family = self.family
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

    def test_raw_candidate_anchor_paths_create_rank_and_continuity_families(self):
        rows = [
            {"cands": [[10, 0, 0.9, 10, 10], [100, 0, 0.8, 10, 10]]},
            {"cands": [[12, 0, 0.9, 10, 10], [98, 0, 0.8, 10, 10]]},
            {"cands": [[14, 0, 0.9, 10, 10], [96, 0, 0.8, 10, 10]]},
        ]

        paths = raw_candidate_anchor_paths(
            rows,
            max_rank_families=2,
            max_continuity_families=2,
            max_step_px=20.0,
        )

        self.assertEqual(
            paths["panel_default_center_mild_state_mild_raw_rank0"][2],
            (14.0, 0.0),
        )
        self.assertEqual(
            paths["panel_default_center_mild_state_mild_raw_rank1"][2],
            (96.0, 0.0),
        )
        self.assertEqual(
            paths["panel_default_center_mild_state_mild_raw_cont0"][2],
            (14.0, 0.0),
        )
        self.assertEqual(
            paths["panel_default_center_mild_state_mild_raw_cont1"][2],
            (96.0, 0.0),
        )

    def test_replay_shadow_path_can_select_raw_candidate_anchor(self):
        rows = [
            {
                "track": [200, 200],
                "cands": [
                    [10 + frame, 20, 0.9, 20, 20],
                    [200, 200, 0.1, 20, 20],
                ],
            }
            for frame in range(4)
        ]

        path, records = replay_shadow_path_from_rows(
            rows,
            runtime=FakeRuntime("panel_default_center_mild_state_mild_raw_rank0"),
            clip_id="sample",
            window=4,
            min_frames=2,
            max_candidates=4,
            include_local_box=False,
            include_raw_candidate_anchors=True,
        )

        self.assertEqual(path[1], (11.0, 20.0))
        self.assertEqual(path[3], (13.0, 20.0))
        self.assertEqual(
            records[3]["family"],
            "panel_default_center_mild_state_mild_raw_rank0",
        )

    def test_track_rescue_candidate_path_uses_prediction_when_track_jumps(self):
        rows = [
            {"track": [0, 0], "cands": [[0, 0, 0.9], [100, 0, 0.8]]},
            {"track": [10, 0], "cands": [[10, 0, 0.9], [100, 0, 0.8]]},
            {"track": [100, 0], "cands": [[20, 0, 0.8], [100, 0, 0.9]]},
            {"track": None, "cands": [[30, 0, 0.8], [100, 0, 0.9]]},
        ]

        path = track_rescue_candidate_path(
            rows,
            track_prediction_gate=35.0,
            rescue_prediction_gate=45.0,
        )

        self.assertEqual(path[0], (0.0, 0.0))
        self.assertEqual(path[1], (10.0, 0.0))
        self.assertEqual(path[2], (20.0, 0.0))
        self.assertEqual(path[3], (30.0, 0.0))

    def test_track_rescue_beam_path_keeps_smooth_branch_when_track_is_wrong(self):
        rows = [
            {"track": [0, 0], "cands": [[0, 0, 0.8], [100, 0, 0.9]]},
            {"track": [10, 0], "cands": [[10, 0, 0.8], [100, 0, 0.9]]},
            {"track": [100, 0], "cands": [[20, 0, 0.7], [100, 0, 0.95]]},
            {"track": None, "cands": [[30, 0, 0.7], [110, 0, 0.95]]},
            {"track": None, "cands": [[40, 0, 0.7], [120, 0, 0.95]]},
        ]

        path = track_rescue_beam_path(
            rows,
            keep=6,
            branch=2,
            track_prediction_gate=35.0,
            rescue_prediction_gate=50.0,
            detection_weight=0.2,
        )

        self.assertEqual(path[0], (0.0, 0.0))
        self.assertEqual(path[1], (10.0, 0.0))
        self.assertEqual(path[2], (20.0, 0.0))
        self.assertEqual(path[3], (30.0, 0.0))
        self.assertEqual(path[4], (40.0, 0.0))

    def test_visual_rank_scores_for_candidates_prefers_center_residual(self):
        diff = np.zeros((60, 60), dtype=np.float32)
        diff[18:23, 18:23] = 100.0
        diff[42:47, 42:47] = 20.0
        candidates = [
            [20, 20, 0.4, 16, 16],
            [44, 44, 0.9, 16, 16],
        ]

        scores = visual_rank_scores_for_candidates(
            diff,
            candidates,
            metric="center_mean",
            inner_radius=4,
            outer_radius=10,
        )

        self.assertGreater(scores[0], scores[1])
        self.assertAlmostEqual(scores[0], 10.0)

    def test_track_rescue_visual_beam_path_uses_visual_score_for_branch_choice(self):
        rows = [
            {"track": [0, 0], "cands": [[0, 0, 0.8], [90, 0, 0.9]]},
            {"track": [10, 0], "cands": [[10, 0, 0.8], [90, 0, 0.9]]},
            {"track": None, "cands": [[20, 0, 0.4], [15, 0, 0.95]]},
            {"track": None, "cands": [[30, 0, 0.4], [18, 0, 0.95]]},
            {"track": None, "cands": [[40, 0, 0.4], [21, 0, 0.95]]},
        ]
        visual_scores = {
            2: [10.0, 0.0],
            3: [10.0, 0.0],
            4: [10.0, 0.0],
        }

        path = track_rescue_visual_beam_path(
            rows,
            visual_scores,
            keep=8,
            branch=2,
            track_prediction_gate=35.0,
            rescue_prediction_gate=50.0,
            detection_weight=0.2,
            visual_weight=1.5,
        )

        self.assertEqual(path[2], (20.0, 0.0))
        self.assertEqual(path[3], (30.0, 0.0))
        self.assertEqual(path[4], (40.0, 0.0))

    def test_path_health_counts_points_far_outside_frame(self):
        path = {
            0: (10.0, 10.0),
            1: (20.0, 20.0),
            2: (50.0, -120.0),
        }

        health = path_health(path, frames=[0, 1, 2], frame_shape=(100, 100), margin=20.0)

        self.assertEqual(health["covered"], 3)
        self.assertEqual(health["out_of_bounds"], 1)
        self.assertGreater(health["max_step"], 100.0)

    def test_select_path_by_track_health_uses_visual_when_track_leaves_screen(self):
        track = {
            0: (10.0, 10.0),
            1: (20.0, 20.0),
            2: (40.0, -130.0),
        }
        rescue = {
            0: (10.0, 10.0),
            1: (19.0, 20.0),
            2: (28.0, 29.0),
        }
        visual = {
            0: (10.0, 10.0),
            1: (20.0, 20.0),
            2: (30.0, 30.0),
        }

        selected, reason, health = select_path_by_track_health(
            track,
            rescue,
            visual,
            frames=[0, 1, 2],
            frame_shape=(100, 100),
            margin=20.0,
        )

        self.assertEqual(reason, "visual_rescue_track_unhealthy")
        self.assertEqual(selected[2], (30.0, 30.0))
        self.assertEqual(health["track"]["out_of_bounds"], 1)


if __name__ == "__main__":
    unittest.main()
