# selector shadow rescue를 GT 리플레이에서 채점하는 흐름을 검증합니다.
import unittest

from _selector_shadow_gt_replay_score import (
    apply_live_health_selection,
    guarded_debug_stats_from_rows,
    guarded_reason_counts_from_rows,
    guarded_emitted_path_from_rows,
    guarded_selected_path_from_rows,
    score_path,
    score_gt_clip,
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

    def test_guarded_selected_path_uses_only_guarded_selector_family(self):
        rows = [
            {
                "selector_shadow": {
                    "available": True,
                    "family": "guarded_decal_identity_center_mild_state_mild",
                    "point": [10.0, 20.0],
                },
            },
            {
                "selector_shadow": {
                    "available": True,
                    "family": "bg_split_viterbi_center_mild_state_mild",
                    "point": [30.0, 40.0],
                },
            },
        ]

        path = guarded_selected_path_from_rows(rows)

        self.assertEqual(path, {0: (10.0, 20.0)})

    def test_guarded_emitted_path_uses_live_family_points(self):
        rows = [
            {
                "live_family": {
                    "points": {
                        "guarded_decal_identity_center_mild_state_mild": [12.0, 34.0],
                    }
                }
            },
            {
                "live_family": {
                    "points": {
                        "balanced_viterbi_center_mild_state_mild": [56.0, 78.0],
                    }
                }
            },
        ]

        path = guarded_emitted_path_from_rows(rows)

        self.assertEqual(path, {0: (12.0, 34.0)})

    def test_guarded_reason_counts_from_live_family_debug(self):
        rows = [
            {
                "live_family": {
                    "debug": {
                        "guarded_decal_identity": {
                            "reason": "period",
                            "accepted": False,
                        }
                    }
                }
            },
            {
                "live_family": {
                    "debug": {
                        "guarded_decal_identity": {
                            "reason": "background_signal",
                            "accepted": False,
                        }
                    }
                }
            },
            {
                "live_family": {
                    "debug": {
                        "guarded_decal_identity": {
                            "reason": "background_signal",
                            "accepted": False,
                        }
                    }
                }
            },
            {
                "live_family": {
                    "debug": {
                        "guarded_decal_identity": {
                            "reason": "accepted",
                            "accepted": True,
                        }
                    }
                }
            },
        ]

        counts = guarded_reason_counts_from_rows(rows)

        self.assertEqual(counts, {"background_signal": 2, "period": 1, "accepted": 1})

    def test_guarded_debug_stats_groups_numeric_fields_by_reason(self):
        rows = [
            {
                "live_family": {
                    "debug": {
                        "guarded_decal_identity": {
                            "reason": "background_signal",
                            "accepted": False,
                            "background_frames": 1,
                            "expected_frames": 4,
                        }
                    }
                }
            },
            {
                "live_family": {
                    "debug": {
                        "guarded_decal_identity": {
                            "reason": "background_signal",
                            "accepted": False,
                            "background_frames": 2,
                            "expected_frames": 5,
                        }
                    }
                }
            },
            {
                "live_family": {
                    "debug": {
                        "guarded_decal_identity": {
                            "reason": "max_step",
                            "accepted": False,
                            "background_frames": 3,
                            "expected_frames": 5,
                            "background_ratio": 0.2,
                            "max_step": 91.0,
                        }
                    }
                }
            },
        ]

        stats = guarded_debug_stats_from_rows(rows)

        self.assertEqual(stats["background_signal"]["count"], 2)
        self.assertEqual(stats["background_signal"]["background_frames"], {"min": 1.0, "mean": 1.5, "max": 2.0})
        self.assertEqual(stats["background_signal"]["expected_frames"], {"min": 4.0, "mean": 4.5, "max": 5.0})
        self.assertEqual(stats["max_step"]["max_step"], {"min": 91.0, "mean": 91.0, "max": 91.0})

    def test_score_gt_clip_forwards_guarded_decal_option(self):
        captured = {}

        def fake_backfill(rows, **kwargs):
            captured.update(kwargs)
            return list(rows)

        rows = [
            {
                "track": [0.0, 0.0],
                "selector_shadow": {
                    "available": True,
                    "family": "guarded_decal_identity_center_mild_state_mild",
                    "point": [0.0, 0.0],
                    "rescue_allowed": True,
                    "rescue_point": [0.0, 0.0],
                },
                "live_family": {
                    "debug": {
                        "guarded_decal_identity": {
                            "reason": "background_signal",
                            "accepted": False,
                        }
                    }
                },
            }
        ]

        from unittest.mock import patch
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            record = root / "_record_debug"
            record.mkdir()
            (record / "sample.jsonl").write_text("{}\n", encoding="utf-8")
            with patch("_selector_shadow_gt_replay_score._load_jsonl", return_value=rows):
                with patch("_selector_shadow_gt_replay_score.backfill_selector_shadow_rows", fake_backfill):
                    with patch("_selector_shadow_gt_replay_score.load_red_gt", return_value={0: (0.0, 0.0)}):
                        with patch("_selector_shadow_gt_replay_score.frame_shape_from_mp4", return_value=(100, 100)):
                            result = score_gt_clip(
                                "sample",
                                root=root,
                                runtime=object(),
                                include_local_box=False,
                                live_max_candidates=24,
                                enable_guarded_decal_identity=True,
                                guarded_decal_min_background_frames=2,
                                guarded_decal_match_distance_px=16.0,
                                guarded_decal_shape_pct=12.0,
                                guarded_decal_max_step_px=180.0,
                            )

        self.assertTrue(captured["enable_guarded_decal_identity"])
        self.assertEqual(captured["guarded_decal_min_background_frames"], 2)
        self.assertEqual(captured["guarded_decal_match_distance_px"], 16.0)
        self.assertEqual(captured["guarded_decal_shape_pct"], 12.0)
        self.assertEqual(captured["guarded_decal_max_step_px"], 180.0)
        self.assertEqual(captured["live_max_candidates"], 24)
        self.assertEqual(result["live_max_candidates"], 24)
        self.assertEqual(result["guarded_emitted_frames"], 0)
        self.assertEqual(result["guarded_selected_frames"], 1)
        self.assertEqual(result["guarded_reason_counts"], {"background_signal": 1})
        self.assertTrue(result["guarded_selected"]["success"])


if __name__ == "__main__":
    unittest.main()
