# 겹침 전후 lifecycle 신호가 배경 줄기와 타겟 줄기를 구분하는지 검증합니다.
import unittest

from _merge_lifecycle_signal import (
    background_flow_escape_frame_score,
    background_flow_escape_point_score,
    release_event_frames,
    score_paths_by_background_flow_escape,
    score_paths_by_identity_escape,
    score_paths_by_merge_lifecycle,
    score_paths_by_source_identity_escape,
)


class MergeLifecycleSignalTests(unittest.TestCase):
    def test_release_event_frames_detects_background_and_non_background_siblings(self):
        candidate_sets = {
            3: [
                (30.0, 0.0, 12.0, 12.0, 0.8),
                (60.0, 0.0, 12.0, 12.0, 0.9),
            ],
        }
        expected_by_frame = {
            3: [(7, (60.0, 0.0, 12.0, 12.0, 0.9))],
        }

        events = release_event_frames(
            candidate_sets,
            expected_by_frame,
            frames=[3],
            sibling_radius=36.0,
        )

        self.assertEqual(events, [3])

    def test_release_event_frames_detects_duplicate_background_identity_siblings(self):
        candidate_sets = {
            3: [
                (30.0, 0.0, 12.0, 12.0, 0.8),
                (42.0, 0.0, 12.0, 12.0, 0.7),
            ],
        }
        expected_by_frame = {
            3: [(7, (36.0, 0.0, 12.0, 12.0, 0.9))],
        }

        events = release_event_frames(
            candidate_sets,
            expected_by_frame,
            frames=[3],
            sibling_radius=20.0,
            pos_tol=16.0,
        )

        self.assertEqual(events, [3])

    def test_score_paths_rewards_target_release_over_background_release(self):
        frames = [0, 1, 2, 3, 4, 5]
        paths = {
            "target_release": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
                3: (30.0, 0.0),
                4: (40.0, 0.0),
                5: (50.0, 0.0),
            },
            "background_release": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
                3: (60.0, 0.0),
                4: (70.0, 0.0),
                5: (80.0, 0.0),
            },
        }
        candidate_sets = {
            3: [
                (30.0, 0.0, 12.0, 12.0, 0.8),
                (60.0, 0.0, 12.0, 12.0, 0.9),
            ],
            4: [
                (40.0, 0.0, 12.0, 12.0, 0.8),
                (70.0, 0.0, 12.0, 12.0, 0.9),
            ],
            5: [
                (50.0, 0.0, 12.0, 12.0, 0.8),
                (80.0, 0.0, 12.0, 12.0, 0.9),
            ],
        }
        expected_by_frame = {
            3: [(7, (60.0, 0.0, 12.0, 12.0, 0.9))],
            4: [(7, (70.0, 0.0, 12.0, 12.0, 0.9))],
            5: [(7, (80.0, 0.0, 12.0, 12.0, 0.9))],
        }

        rows = score_paths_by_merge_lifecycle(
            paths,
            candidate_sets,
            expected_by_frame,
            frames,
            sibling_radius=36.0,
            pos_tol=18.0,
            post_window=2,
        )

        self.assertGreater(
            rows["target_release"]["merge_lifecycle_score"],
            rows["background_release"]["merge_lifecycle_score"],
        )
        self.assertEqual(rows["target_release"]["merge_lifecycle_events"], 1)
        self.assertLess(rows["target_release"]["merge_post_bg_ratio"], 0.5)
        self.assertGreater(rows["background_release"]["merge_post_bg_ratio"], 0.5)

    def test_background_flow_escape_frame_rewards_branch_leaving_expected_background(self):
        expected = [(7, (60.0, 0.0, 12.0, 12.0, 0.9))]
        candidates = [
            (30.0, 0.0, 12.0, 12.0, 0.8),
            (60.0, 0.0, 12.0, 12.0, 0.9),
        ]

        target_score = background_flow_escape_frame_score(
            candidates[0],
            candidates,
            expected,
            sibling_radius=36.0,
            pos_tol=18.0,
        )
        background_score = background_flow_escape_frame_score(
            candidates[1],
            candidates,
            expected,
            sibling_radius=36.0,
            pos_tol=18.0,
        )

        self.assertGreater(target_score, 0.0)
        self.assertLess(background_score, 0.0)
        self.assertGreater(target_score, background_score)

    def test_background_flow_escape_point_rewards_inside_merged_box_away_from_background(self):
        expected = [(7, (60.0, 0.0, 12.0, 12.0, 0.9))]
        candidates = [
            (45.0, 0.0, 42.0, 12.0, 0.8),
        ]

        target_point_score = background_flow_escape_point_score(
            (30.0, 0.0),
            candidates,
            expected,
            sibling_radius=48.0,
            pos_tol=18.0,
        )
        background_point_score = background_flow_escape_point_score(
            (60.0, 0.0),
            candidates,
            expected,
            sibling_radius=48.0,
            pos_tol=18.0,
        )

        self.assertGreater(target_point_score, 0.0)
        self.assertLess(background_point_score, 0.0)
        self.assertGreater(target_point_score, background_point_score)

    def test_score_paths_by_background_flow_escape_accumulates_post_release_escape(self):
        frames = [0, 1, 2, 3, 4, 5]
        paths = {
            "target_escape": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
                3: (30.0, 0.0),
                4: (40.0, 0.0),
                5: (50.0, 0.0),
            },
            "background_flow": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
                3: (60.0, 0.0),
                4: (70.0, 0.0),
                5: (80.0, 0.0),
            },
        }
        candidate_sets = {
            3: [
                (30.0, 0.0, 12.0, 12.0, 0.8),
                (60.0, 0.0, 12.0, 12.0, 0.9),
            ],
            4: [
                (40.0, 0.0, 12.0, 12.0, 0.8),
                (70.0, 0.0, 12.0, 12.0, 0.9),
            ],
            5: [
                (50.0, 0.0, 12.0, 12.0, 0.8),
                (80.0, 0.0, 12.0, 12.0, 0.9),
            ],
        }
        expected_by_frame = {
            3: [(7, (60.0, 0.0, 12.0, 12.0, 0.9))],
            4: [(7, (70.0, 0.0, 12.0, 12.0, 0.9))],
            5: [(7, (80.0, 0.0, 12.0, 12.0, 0.9))],
        }

        rows = score_paths_by_background_flow_escape(
            paths,
            candidate_sets,
            expected_by_frame,
            frames,
            sibling_radius=36.0,
            pos_tol=18.0,
            post_window=2,
        )

        self.assertGreater(
            rows["target_escape"]["background_flow_escape_score"],
            rows["background_flow"]["background_flow_escape_score"],
        )
        self.assertGreater(rows["target_escape"]["background_flow_escape_ratio"], 0.9)
        self.assertLess(rows["background_flow"]["background_flow_escape_ratio"], 0.1)

    def test_score_paths_by_identity_escape_prefers_pre_merge_continuity(self):
        frames = [0, 1, 2, 3, 4, 5]
        paths = {
            "identity_escape": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
                3: (30.0, 0.0),
                4: (40.0, 0.0),
                5: (50.0, 0.0),
            },
            "late_escape": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
                3: (95.0, 0.0),
                4: (105.0, 0.0),
                5: (115.0, 0.0),
            },
            "background_flow": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
                3: (60.0, 0.0),
                4: (70.0, 0.0),
                5: (80.0, 0.0),
            },
        }
        candidate_sets = {
            3: [
                (30.0, 0.0, 12.0, 12.0, 0.8),
                (60.0, 0.0, 12.0, 12.0, 0.9),
                (95.0, 0.0, 12.0, 12.0, 0.7),
            ],
            4: [
                (40.0, 0.0, 12.0, 12.0, 0.8),
                (70.0, 0.0, 12.0, 12.0, 0.9),
                (105.0, 0.0, 12.0, 12.0, 0.7),
            ],
            5: [
                (50.0, 0.0, 12.0, 12.0, 0.8),
                (80.0, 0.0, 12.0, 12.0, 0.9),
                (115.0, 0.0, 12.0, 12.0, 0.7),
            ],
        }
        expected_by_frame = {
            3: [(7, (60.0, 0.0, 12.0, 12.0, 0.9))],
            4: [(7, (70.0, 0.0, 12.0, 12.0, 0.9))],
            5: [(7, (80.0, 0.0, 12.0, 12.0, 0.9))],
        }

        rows = score_paths_by_identity_escape(
            paths,
            candidate_sets,
            expected_by_frame,
            frames,
            sibling_radius=80.0,
            pos_tol=18.0,
            post_window=2,
        )

        self.assertGreater(
            rows["identity_escape"]["identity_escape_score"],
            rows["late_escape"]["identity_escape_score"],
        )
        self.assertGreater(
            rows["identity_escape"]["identity_escape_score"],
            rows["background_flow"]["identity_escape_score"],
        )
        self.assertGreater(rows["identity_escape"]["identity_escape_continuity"], 0.9)
        self.assertLess(rows["late_escape"]["identity_escape_continuity"], 0.2)

    def test_source_identity_escape_uses_original_family_history(self):
        frames = [0, 1, 2, 3, 4, 5]
        paths = {
            "raw_candidate_cont0_box_rel_p05_z0_state_mild": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
            },
            "raw_candidate_cont0_box_rel_p05_z0_state_mild_occlusion_state": {
                3: (30.0, 0.0),
                4: (40.0, 0.0),
                5: (50.0, 0.0),
            },
            "raw_candidate_cont0_box_rel_p1_z0_state_mild": {
                0: (0.0, 0.0),
                1: (10.0, 0.0),
                2: (20.0, 0.0),
            },
            "raw_candidate_cont0_box_rel_p1_z0_state_mild_occlusion_state": {
                3: (95.0, 0.0),
                4: (105.0, 0.0),
                5: (115.0, 0.0),
            },
        }
        candidate_sets = {
            3: [
                (30.0, 0.0, 12.0, 12.0, 0.8),
                (60.0, 0.0, 12.0, 12.0, 0.9),
                (95.0, 0.0, 12.0, 12.0, 0.7),
            ],
            4: [
                (40.0, 0.0, 12.0, 12.0, 0.8),
                (70.0, 0.0, 12.0, 12.0, 0.9),
                (105.0, 0.0, 12.0, 12.0, 0.7),
            ],
        }
        expected_by_frame = {
            3: [(7, (60.0, 0.0, 12.0, 12.0, 0.9))],
            4: [(7, (70.0, 0.0, 12.0, 12.0, 0.9))],
        }

        rows = score_paths_by_source_identity_escape(
            paths,
            candidate_sets,
            expected_by_frame,
            frames,
            sibling_radius=80.0,
            pos_tol=18.0,
            post_window=1,
        )

        good = rows["raw_candidate_cont0_box_rel_p05_z0_state_mild_occlusion_state"]
        late = rows["raw_candidate_cont0_box_rel_p1_z0_state_mild_occlusion_state"]
        self.assertGreater(good["source_identity_escape_score"], late["source_identity_escape_score"])
        self.assertGreater(good["source_identity_escape_source_continuity"], 0.9)
        self.assertLess(late["source_identity_escape_source_continuity"], 0.2)


if __name__ == "__main__":
    unittest.main()
