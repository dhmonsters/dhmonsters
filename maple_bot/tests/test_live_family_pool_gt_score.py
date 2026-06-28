# 라이브 family pool GT 채점기의 빠른 반복 옵션을 검증합니다.
import unittest
from unittest.mock import patch

from _live_family_pool_gt_score import (
    DEFAULT_FAST_BOX_REL_PAIRS,
    _fast_family_pool,
    _occlusion_signal_adjustment,
    _switch_signal_penalty,
    _box_rel_consistency_bonus,
    best_family_score,
    box_switch_variant_paths,
    build_family_paths,
    event_gate_shortlist_paths,
    gap_fill_variant_paths,
    occlusion_variant_paths,
    select_event_gate_family,
    selected_family_score,
    score_clip,
    score_all,
    summarize_selected,
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

    def test_fast_family_pool_keeps_expanded_candidate_width(self) -> None:
        pool = _fast_family_pool()

        self.assertEqual(pool.raw_rank_families, 0)
        self.assertEqual(pool.raw_continuity_families, 20)
        self.assertEqual(pool.raw_beam_families, 0)
        self.assertEqual(pool.raw_beam_spawn, 0)
        self.assertEqual(pool.raw_max_candidates_per_frame, 24)
        self.assertEqual(pool.raw_box_rel_pairs, DEFAULT_FAST_BOX_REL_PAIRS)

    def test_score_all_forwards_occlusion_variant_option(self) -> None:
        with patch("_live_family_pool_gt_score.score_clip") as score_clip_mock:
            score_clip_mock.return_value = {"name": "a", "best_family": {"success": False}}

            score_all(names=["a"], include_occlusion_variants=True)

        self.assertTrue(score_clip_mock.call_args.kwargs["include_occlusion_variants"])

    def test_score_all_forwards_event_gate_shortlist_option(self) -> None:
        with patch("_live_family_pool_gt_score.score_clip") as score_clip_mock:
            score_clip_mock.return_value = {"name": "a", "best_family": {"success": False}}

            score_all(names=["a"], event_gate_shortlist=True)

        self.assertTrue(score_clip_mock.call_args.kwargs["event_gate_shortlist"])

    def test_score_all_forwards_selector_scoreboard_option(self) -> None:
        with patch("_live_family_pool_gt_score.score_clip") as score_clip_mock:
            score_clip_mock.return_value = {"name": "a", "best_family": {"success": False}}

            score_all(names=["a"], selector_scoreboard=True)

        self.assertTrue(score_clip_mock.call_args.kwargs["selector_scoreboard"])

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

    def test_score_clip_adds_selected_family_when_selector_scoreboard_enabled(self) -> None:
        with patch("_live_family_pool_gt_score._load_jsonl", return_value=[{"i": 0, "track": [0.0, 0.0], "cands": []}]):
            with patch("_live_family_pool_gt_score.load_red_gt", return_value={0: (0.0, 0.0)}):
                with patch("_live_family_pool_gt_score.best_family_score", return_value={"family": "upper", "success": True}):
                    with patch(
                        "_live_family_pool_gt_score.selected_family_score",
                        return_value={"selected_family": {"family": "selected", "success": True}},
                    ) as selected:
                        score = score_clip("clip", selector_scoreboard=True)

        self.assertEqual(score["selected_family"], {"family": "selected", "success": True})
        selected.assert_called_once()

    def test_score_clip_reuses_built_paths_for_selector_scoreboard(self) -> None:
        paths = {"family": {0: (0.0, 0.0)}}
        with patch("_live_family_pool_gt_score._load_jsonl", return_value=[{"i": 0, "track": [0.0, 0.0], "cands": []}]):
            with patch("_live_family_pool_gt_score.load_red_gt", return_value={0: (0.0, 0.0)}):
                with patch("_live_family_pool_gt_score.build_family_paths", return_value=paths) as build:
                    with patch("_live_family_pool_gt_score.best_family_score", return_value={"family": "upper", "success": True}) as best:
                        with patch(
                            "_live_family_pool_gt_score.selected_family_score",
                            return_value={"selected_family": {"family": "selected", "success": True}},
                        ) as selected:
                            score_clip("clip", selector_scoreboard=True)

        build.assert_called_once()
        self.assertIs(best.call_args.kwargs["paths"], paths)
        self.assertIs(selected.call_args.kwargs["paths"], paths)

    def test_summarize_selected_uses_selected_family_result(self) -> None:
        summary = summarize_selected([
            {"best_family": {"success": True}, "selected_family": {"success": False}},
            {"best_family": {"success": False}, "selected_family": {"success": True}},
        ])

        self.assertEqual(summary, {"success": 1, "total": 2})

    def test_event_gate_shortlist_keeps_verified_live_family_bands(self) -> None:
        paths = {
            "raw_candidate_cont10_center_mild_state_mild": {0: (10.0, 0.0)},
            "raw_candidate_cont16_center_mild_state_mild": {0: (16.0, 0.0)},
            "raw_candidate_cont10_box_rel_p05_n05_state_mild": {0: (11.0, 0.0)},
            "raw_candidate_cont10_box_rel_n1_n1_state_mild": {0: (-11.0, 0.0)},
            "raw_candidate_cont10_box_switch_p05_p1_to_n1_z0_at8_state_mild": {0: (12.0, 0.0)},
            "balanced_viterbi_center_mild_state_mild": {0: (13.0, 0.0)},
        }

        shortlisted = event_gate_shortlist_paths(paths)

        self.assertIn("raw_candidate_cont10_center_mild_state_mild", shortlisted)
        self.assertNotIn("raw_candidate_cont16_center_mild_state_mild", shortlisted)
        self.assertIn("raw_candidate_cont10_box_rel_p05_n05_state_mild", shortlisted)
        self.assertNotIn("raw_candidate_cont10_box_rel_n1_n1_state_mild", shortlisted)
        self.assertIn("raw_candidate_cont10_box_switch_p05_p1_to_n1_z0_at8_state_mild", shortlisted)
        self.assertIn("balanced_viterbi_center_mild_state_mild", shortlisted)

    def test_event_gate_shortlist_keeps_box_rel_occlusion_variants(self) -> None:
        paths = {
            "raw_candidate_cont4_box_rel_n1_p05_state_mild_occlusion_state": {0: (4.0, 0.0)},
            "raw_candidate_cont4_box_rel_n1_n1_state_mild_occlusion_state": {0: (-4.0, 0.0)},
        }

        shortlisted = event_gate_shortlist_paths(paths)

        self.assertIn("raw_candidate_cont4_box_rel_n1_p05_state_mild_occlusion_state", shortlisted)
        self.assertNotIn("raw_candidate_cont4_box_rel_n1_n1_state_mild_occlusion_state", shortlisted)

    def test_select_event_gate_family_prefers_occlusion_when_it_is_coherent(self) -> None:
        selected = select_event_gate_family(
            {
                "raw_candidate_cont10_center_mild_state_mild": {
                    0: (0.0, 0.0),
                    1: (80.0, 0.0),
                    2: (160.0, 0.0),
                },
                "raw_candidate_cont4_box_rel_n1_p05_state_mild_occlusion_state": {
                    0: (0.0, 0.0),
                    1: (10.0, 0.0),
                    2: (20.0, 0.0),
                },
            },
            frames=[0, 1, 2],
        )

        self.assertEqual(
            selected["family"],
            "raw_candidate_cont4_box_rel_n1_p05_state_mild_occlusion_state",
        )
        self.assertEqual(selected["judge"], "occlusion")

    def test_select_event_gate_family_does_not_overtrust_weak_occlusion_rel(self) -> None:
        selected = select_event_gate_family(
            {
                "raw_candidate_cont10_center_mild_state_mild": {
                    0: (0.0, 0.0),
                    1: (5.0, 0.0),
                    2: (10.0, 0.0),
                },
                "raw_candidate_cont12_box_rel_z0_p1_state_mild_occlusion_state": {
                    0: (100.0, 0.0),
                    1: (100.0, 0.0),
                    2: (100.0, 0.0),
                },
            },
            frames=[0, 1, 2],
        )

        self.assertEqual(selected["family"], "raw_candidate_cont10_center_mild_state_mild")
        self.assertEqual(selected["judge"], "center")

    def test_select_event_gate_family_penalizes_late_cont_occlusion(self) -> None:
        selected = select_event_gate_family(
            {
                "raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state": {
                    0: (0.0, 0.0),
                    1: (5.0, 0.0),
                    2: (10.0, 0.0),
                },
                "raw_candidate_cont12_box_rel_p1_n05_state_mild_occlusion_state": {
                    0: (100.0, 0.0),
                    1: (100.0, 0.0),
                    2: (100.0, 0.0),
                },
            },
            frames=[0, 1, 2],
        )

        self.assertEqual(
            selected["family"],
            "raw_candidate_cont11_box_rel_p05_z0_state_mild_occlusion_state",
        )

    def test_select_event_gate_family_uses_switch_when_no_occlusion_wins(self) -> None:
        selected = select_event_gate_family(
            {
                "raw_candidate_cont10_center_mild_state_mild": {
                    0: (0.0, 0.0),
                    1: (5.0, 0.0),
                    2: (10.0, 0.0),
                },
                "raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at1_state_mild": {
                    0: (0.0, 0.0),
                    1: (20.0, 0.0),
                    2: (40.0, 0.0),
                },
            },
            frames=[0, 1, 2],
        )

        self.assertEqual(
            selected["family"],
            "raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at1_state_mild",
        )
        self.assertEqual(selected["judge"], "switch")

    def test_select_event_gate_family_uses_visible_anchor_when_available(self) -> None:
        selected = select_event_gate_family(
            {
                "raw_candidate_cont10_box_switch_z0_n05_to_p1_n05_at1_state_mild": {
                    0: (100.0, 0.0),
                    1: (120.0, 0.0),
                    2: (140.0, 0.0),
                },
                "raw_candidate_cont11_center_mild_state_mild": {
                    0: (0.0, 0.0),
                    1: (5.0, 0.0),
                    2: (10.0, 0.0),
                },
            },
            frames=[0, 1, 2],
            anchor_points={0: (0.0, 0.0), 1: (5.0, 0.0), 2: (10.0, 0.0)},
        )

        self.assertEqual(selected["family"], "raw_candidate_cont11_center_mild_state_mild")
        self.assertEqual(selected["judge"], "anchor_center")

    def test_occlusion_signal_rewards_corrected_release_and_penalizes_background_stick(self) -> None:
        expected = {
            1: [(1, (20.0, 0.0, 10.0, 10.0))],
            2: [(1, (30.0, 0.0, 10.0, 10.0))],
            3: [(1, (40.0, 0.0, 10.0, 10.0))],
        }
        original = {
            0: (0.0, 0.0),
            1: (20.0, 0.0),
            2: (30.0, 0.0),
            3: (40.0, 0.0),
        }
        released = {
            0: (0.0, 0.0),
            1: (10.0, 0.0),
            2: (20.0, 0.0),
            3: (30.0, 0.0),
        }
        stuck = dict(original)

        self.assertGreater(
            _occlusion_signal_adjustment(released, original, [0, 1, 2, 3], expected),
            _occlusion_signal_adjustment(stuck, original, [0, 1, 2, 3], expected),
        )

    def test_switch_signal_penalizes_discontinuous_switch_and_anchor_drift(self) -> None:
        smooth = {
            0: (0.0, 0.0),
            1: (5.0, 0.0),
            2: (10.0, 0.0),
            3: (15.0, 0.0),
        }
        jump = {
            0: (0.0, 0.0),
            1: (5.0, 0.0),
            2: (100.0, 0.0),
            3: (105.0, 0.0),
        }

        self.assertLess(
            _switch_signal_penalty(
                jump,
                [0, 1, 2, 3],
                switch_frame=2,
                anchor_points={0: (0.0, 0.0), 1: (5.0, 0.0)},
            ),
            _switch_signal_penalty(
                smooth,
                [0, 1, 2, 3],
                switch_frame=2,
                anchor_points={0: (0.0, 0.0), 1: (5.0, 0.0)},
            ),
        )

    def test_box_rel_consistency_prefers_stable_offset_member(self) -> None:
        paths = {
            "raw_candidate_cont4_box_rel_p05_z0_state_mild": {
                0: (5.0, 0.0),
                1: (6.0, 0.0),
                2: (7.0, 0.0),
            },
            "raw_candidate_cont4_box_rel_p1_z0_state_mild": {
                0: (20.0, 0.0),
                1: (28.0, 0.0),
                2: (45.0, 0.0),
            },
        }

        self.assertGreater(
            _box_rel_consistency_bonus(
                "raw_candidate_cont4_box_rel_p05_z0_state_mild",
                paths,
                [0, 1, 2],
            ),
            _box_rel_consistency_bonus(
                "raw_candidate_cont4_box_rel_p1_z0_state_mild",
                paths,
                [0, 1, 2],
            ),
        )

    def test_selected_family_score_scores_selector_pick_separately_from_upper(self) -> None:
        class _FakePool:
            def update(self, frame_index, **_kwargs):
                points = {
                    "bad_center": (100.0, 0.0),
                    "raw_candidate_cont4_box_rel_n1_p05_state_mild": (float(frame_index), 0.0),
                }
                return LiveFamilyDecision(points=points, debug={})

        score = selected_family_score(
            [{"i": 0, "track": [0.0, 0.0], "cands": []}],
            {0: (0.0, 0.0)},
            family_pool=_FakePool(),
            success_px=1.0,
        )

        self.assertEqual(score["selected_family"]["family"], "raw_candidate_cont4_box_rel_n1_p05_state_mild")
        self.assertTrue(score["selected_family"]["success"])

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

    def test_gap_fill_variant_paths_interpolates_short_missing_run(self) -> None:
        variants = gap_fill_variant_paths(
            {"observed": {0: (0.0, 0.0), 1: (10.0, 0.0), 4: (40.0, 0.0)}},
            frames=[0, 1, 2, 3, 4],
            max_gap=2,
        )

        self.assertEqual(variants["observed_gap_fill"][2], (20.0, 0.0))
        self.assertEqual(variants["observed_gap_fill"][3], (30.0, 0.0))

    def test_gap_fill_variant_paths_keeps_large_gap_missing(self) -> None:
        variants = gap_fill_variant_paths(
            {"observed": {0: (0.0, 0.0), 4: (40.0, 0.0)}},
            frames=[0, 1, 2, 3, 4],
            max_gap=2,
        )

        self.assertNotIn(1, variants["observed_gap_fill"])
        self.assertNotIn(2, variants["observed_gap_fill"])
        self.assertNotIn(3, variants["observed_gap_fill"])

    def test_box_switch_variant_paths_splices_same_raw_box_family(self) -> None:
        variants = box_switch_variant_paths(
            {
                "raw_candidate_cont0_box_rel_p05_p1_state_mild": {
                    0: (0.0, 10.0),
                    1: (10.0, 10.0),
                    2: (20.0, 10.0),
                },
                "raw_candidate_cont0_box_rel_n1_z0_state_mild": {
                    0: (0.0, -10.0),
                    1: (10.0, -10.0),
                    2: (20.0, -10.0),
                },
            },
            frames=[0, 1, 2],
            switch_stride=1,
        )

        path = variants[
            "raw_candidate_cont0_box_switch_p05_p1_to_n1_z0_at1_state_mild"
        ]
        self.assertEqual(path[0], (0.0, 10.0))
        self.assertEqual(path[1], (10.0, -10.0))
        self.assertEqual(path[2], (20.0, -10.0))

    def test_box_switch_variant_paths_filters_unverified_rel_pairs(self) -> None:
        variants = box_switch_variant_paths(
            {
                "raw_candidate_cont0_box_rel_n1_n1_state_mild": {
                    0: (0.0, 0.0),
                    1: (10.0, 0.0),
                    2: (20.0, 0.0),
                },
                "raw_candidate_cont0_box_rel_p1_p1_state_mild": {
                    0: (0.0, 20.0),
                    1: (10.0, 20.0),
                    2: (20.0, 20.0),
                },
            },
            frames=[0, 1, 2],
            switch_stride=1,
        )

        self.assertEqual(variants, {})

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
