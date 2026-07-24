# Studio trace로 시간축 가설 보관 전략을 재생 비교하는 도구를 검증합니다.
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.puzzle.hypothesis_challenge import HypothesisChallengeGuard
from core.puzzle.models import Candidate
from core.puzzle.studio_hypothesis_shadow import (
    _FrozenCycleObservation,
    _StableCycleTracks,
    _local_lag_temporal_support,
    _observed_episode_period,
    _period_recurrence_support,
    _valid_cycle_frame_shape,
    _stable_target_area,
    replay_hypothesis_selection,
    replay_hypothesis_selection_details,
    replay_hypothesis_tracker,
)
from core.vision.transparent_puzzle_engine import BackgroundCatalog, PuzzleCandidate


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


class StudioHypothesisShadowTest(unittest.TestCase):
    def test_stable_target_area_prefers_visible_anchor_shape(self) -> None:
        candidates = [
            Candidate("small-a", 0, (0.0, 0.0, 2.0, 2.0), (1.0, 1.0), 0.8, "raw"),
            Candidate("small-b", 0, (4.0, 0.0, 6.0, 2.0), (5.0, 1.0), 0.8, "raw"),
            Candidate("target", 0, (10.0, 10.0, 20.0, 20.0), (15.0, 15.0), 0.9, "raw"),
        ]

        area = _stable_target_area(
            candidates,
            incumbent_point=(15.0, 15.0),
            anchor_shapes=[(100.0, 1.0)],
        )

        self.assertEqual(area, 100.0)

    def test_challenger_must_persist_before_replacing_incumbent(self) -> None:
        guard = HypothesisChallengeGuard(confirm_frames=2, max_step_px=30.0)

        first_point, first_debug = guard.update(
            incumbent_point=(20.0, 50.0),
            challenger_point=(80.0, 50.0),
        )
        second_point, second_debug = guard.update(
            incumbent_point=(25.0, 50.0),
            challenger_point=(90.0, 50.0),
        )
        jump_point, jump_debug = guard.update(
            incumbent_point=(30.0, 50.0),
            challenger_point=(150.0, 50.0),
        )

        self.assertEqual(first_point, (20.0, 50.0))
        self.assertEqual(first_debug["reason"], "challenger_pending")
        self.assertEqual(second_point, (90.0, 50.0))
        self.assertEqual(second_debug["reason"], "challenger_confirmed")
        self.assertEqual(jump_point, (30.0, 50.0))
        self.assertEqual(jump_debug["reason"], "challenger_reset")

        protected_point, protected_debug = guard.update(
            incumbent_point=(40.0, 50.0),
            challenger_point=(160.0, 50.0),
            protect_incumbent=True,
        )

        self.assertEqual(protected_point, (40.0, 50.0))
        self.assertEqual(protected_debug["reason"], "incumbent_protected")

    def test_replay_reconstructs_anchor_and_scores_retained_coverage(self) -> None:
        with TemporaryDirectory(prefix="studio-hypothesis-shadow-") as tmp:
            root = Path(tmp)
            score_path = root / "score.jsonl"
            trace_path = root / "trace.jsonl"
            _write_jsonl(
                score_path,
                [
                    {
                        "solver_frame_index": 0,
                        "target_x": 10.0,
                        "target_y": 10.0,
                        "passed": True,
                    }
                ],
            )
            _write_jsonl(
                trace_path,
                [
                    {
                        "type": "CANDIDATES",
                        "frame_index": 0,
                        "payload": {
                            "candidates": [
                                {
                                    "candidate_id": "target",
                                    "center": [10.0, 10.0],
                                    "bbox": [5.0, 5.0, 15.0, 15.0],
                                    "score": 0.9,
                                    "source": "white_anchor",
                                }
                            ]
                        },
                    },
                    {
                        "type": "TEMPORAL_SELECTOR",
                        "frame_index": 0,
                        "payload": {
                            "debug": {
                                "kinematic_wide_beam_points": [[10.0, 10.0]],
                                "kinematic_wide_beam_debug": {
                                    "reason": "white_anchor",
                                    "point": [10.0, 10.0],
                                    "state_count": 1,
                                },
                            }
                        },
                    },
                ],
            )

            result = replay_hypothesis_tracker(score_path, trace_path)

            self.assertEqual(result.total_frames, 1)
            self.assertEqual(result.candidate_center_frames, 1)
            self.assertEqual(result.recorded_hit_frames, 1)
            self.assertEqual(result.replay_hit_frames, 1)
            self.assertEqual(result.improved_frames, 0)
            self.assertEqual(result.regressed_frames, 0)

    def test_selection_replay_applies_live_wide_and_local_rigid_gates(self) -> None:
        with TemporaryDirectory(prefix="studio-hypothesis-selection-") as tmp:
            root = Path(tmp)
            score_path = root / "score.jsonl"
            trace_path = root / "trace.jsonl"
            _write_jsonl(
                score_path,
                [
                    {
                        "solver_frame_index": 1,
                        "target_x": 80.0,
                        "target_y": 50.0,
                        "selected_x": 20.0,
                        "selected_y": 50.0,
                        "passed": False,
                    }
                ],
            )
            _write_jsonl(
                trace_path,
                [
                    {
                        "type": "SESSION_START",
                        "frame_index": None,
                        "payload": {"board_roi": {"w": 120, "h": 100}},
                    },
                    {
                        "type": "CANDIDATES",
                        "frame_index": 0,
                        "payload": {
                            "candidates": [
                                {
                                    "candidate_id": "anchor",
                                    "center": [20.0, 50.0],
                                    "bbox": [15.0, 45.0, 25.0, 55.0],
                                    "score": 0.99,
                                    "source": "white_anchor",
                                }
                            ]
                        },
                    },
                    {
                        "type": "TEMPORAL_SELECTOR",
                        "frame_index": 0,
                        "payload": {
                            "debug": {
                                "kinematic_wide_beam_debug": {
                                    "reason": "white_anchor",
                                    "point": [20.0, 50.0],
                                }
                            }
                        },
                    },
                    {
                        "type": "CANDIDATES",
                        "frame_index": 1,
                        "payload": {
                            "candidates": [
                                {
                                    "candidate_id": "base",
                                    "center": [20.0, 50.0],
                                    "bbox": [15.0, 45.0, 25.0, 55.0],
                                    "score": 0.8,
                                    "source": "raw",
                                },
                                {
                                    "candidate_id": "target",
                                    "center": [80.0, 50.0],
                                    "bbox": [75.0, 45.0, 85.0, 55.0],
                                    "score": 0.7,
                                    "source": "raw",
                                },
                            ]
                        },
                    },
                    {
                        "type": "EVIDENCE",
                        "frame_index": 1,
                        "payload": {
                            "evidence": [
                                {
                                    "candidate_id": "base",
                                    "texture_bg_score": 0.8,
                                    "color_residual": 0.2,
                                    "local_rigid_residual": 0.1,
                                },
                                {
                                    "candidate_id": "target",
                                    "texture_bg_score": 0.9,
                                    "color_residual": 0.2,
                                    "local_rigid_residual": 0.5,
                                },
                            ]
                        },
                    },
                    {
                        "type": "IDENTITY_STATE",
                        "frame_index": 1,
                        "payload": {"state": "TRACK_CONFIDENT"},
                    },
                    {
                        "type": "TEMPORAL_SELECTOR",
                        "frame_index": 1,
                        "payload": {
                            "debug": {
                                "kinematic_wide_beam_debug": {
                                    "reason": "tracking",
                                }
                            }
                        },
                    },
                    {
                        "type": "TARGET_SELECTION",
                        "frame_index": 1,
                        "payload": {
                            "point": [20.0, 50.0],
                            "source": "kinematic_local_rigid",
                            "kinematic_wide_beam_gate": {
                                "base_point": [20.0, 50.0]
                            },
                        },
                    },
                ],
            )

            result = replay_hypothesis_selection(
                score_path,
                trace_path,
                width=2,
                branch=2,
                diverse_first=True,
            )

            self.assertEqual(result.total_frames, 1)
            self.assertEqual(result.recorded_passed_frames, 0)
            self.assertEqual(result.replay_passed_frames, 1)
            self.assertEqual(result.improved_frames, 1)
            self.assertEqual(result.regressed_frames, 0)
            self.assertEqual(result.local_rigid_selected_frames, 1)

            details = replay_hypothesis_selection_details(
                score_path,
                trace_path,
                width=2,
                branch=2,
                diverse_first=True,
            )

            self.assertEqual(len(details), 1)
            self.assertTrue(details[0]["improved"])
            self.assertEqual(details[0]["replay_source"], "kinematic_local_rigid")
            self.assertEqual(details[0]["replay_point"], [80.0, 50.0])
            self.assertEqual(details[0]["replay_hypothesis_rank"], 1)

            limited = replay_hypothesis_selection(
                score_path,
                trace_path,
                width=2,
                branch=2,
                diverse_first=True,
                judge_hypothesis_limit=1,
            )

            self.assertEqual(limited.replay_passed_frames, 0)
            self.assertEqual(limited.local_rigid_selected_frames, 0)

            guarded = replay_hypothesis_selection(
                score_path,
                trace_path,
                width=2,
                branch=2,
                diverse_first=True,
                challenge_confirm_frames=2,
                challenge_max_step_px=30.0,
            )

            self.assertEqual(guarded.replay_passed_frames, 0)
            self.assertEqual(guarded.changed_frames, 0)

            protected = replay_hypothesis_selection(
                score_path,
                trace_path,
                width=2,
                branch=2,
                diverse_first=True,
                challenge_confirm_frames=1,
                protect_incumbent_sources=("kinematic_local_rigid",),
            )

            self.assertEqual(protected.replay_passed_frames, 0)
            self.assertEqual(protected.changed_frames, 0)

            persistent_details = replay_hypothesis_selection_details(
                score_path,
                trace_path,
                width=2,
                branch=2,
                diverse_first=True,
                persistent_evidence_quorum=True,
            )

            self.assertTrue(persistent_details[0]["replay_passed"])
            self.assertEqual(
                persistent_details[0]["persistent_evidence_quorum"]["reason"],
                "quorum_pending",
            )
            self.assertIsNotNone(
                persistent_details[0]["persistent_evidence_quorum"]
                ["challenger"]["group_margins"]["anchor_shape_identity"]
            )

    def test_wide_gate_accepts_legacy_numeric_frame_shapes_when_opted_out(self) -> None:
        with TemporaryDirectory(prefix="studio-wide-frame-shape-opt-out-") as tmp:
            root = Path(tmp)
            score_path = root / "score.jsonl"
            _write_jsonl(
                score_path,
                [{"solver_frame_index": 1, "target_x": 80.0, "target_y": 50.0}],
            )
            baseline_path = root / "baseline.jsonl"
            _write_jsonl(baseline_path, _wide_gate_trace((100, 120)))
            baseline = replay_hypothesis_selection_details(
                score_path,
                baseline_path,
                width=2,
                branch=2,
            )

            for label, frame_shape in (
                ("strings", ("100", "120")),
                ("whole_floats", (100.0, 120.0)),
            ):
                with self.subTest(label=label):
                    trace_path = root / f"{label}.jsonl"
                    _write_jsonl(trace_path, _wide_gate_trace(frame_shape))
                    details = replay_hypothesis_selection_details(
                        score_path,
                        trace_path,
                        width=2,
                        branch=2,
                    )

                    self.assertEqual(details, baseline)
                    self.assertTrue(details[0]["wide_gate"]["available"])
                    self.assertEqual(
                        details[0]["wide_gate"]["beam_guard"]["bottom_margin"],
                        45.0,
                    )
                    self.assertTrue(details[0]["local_rigid_gate"]["selected"])

    def test_wide_gate_skips_invalid_session_start_before_legacy_shape(self) -> None:
        with TemporaryDirectory(prefix="studio-wide-multi-session-start-") as tmp:
            root = Path(tmp)
            score_path = root / "score.jsonl"
            _write_jsonl(
                score_path,
                [{"solver_frame_index": 1, "target_x": 80.0, "target_y": 50.0}],
            )
            baseline_path = root / "baseline.jsonl"
            _write_jsonl(baseline_path, _wide_gate_trace((100, 120)))
            baseline = replay_hypothesis_selection_details(
                score_path,
                baseline_path,
                width=2,
                branch=2,
            )

            for label, frame_shape in (
                ("strings", ("100", "120")),
                ("whole_floats", (100.0, 120.0)),
            ):
                with self.subTest(label=label):
                    trace_path = root / f"multi-{label}.jsonl"
                    _write_jsonl(
                        trace_path,
                        [
                            {
                                "type": "SESSION_START",
                                "frame_index": None,
                                "payload": {"board_roi": {"w": "invalid", "h": "invalid"}},
                            },
                            *_wide_gate_trace(frame_shape),
                        ],
                    )
                    details = replay_hypothesis_selection_details(
                        score_path,
                        trace_path,
                        width=2,
                        branch=2,
                    )

                    self.assertEqual(details, baseline)
                    self.assertEqual(
                        details[0]["wide_gate"]["beam_guard"]["bottom_margin"],
                        45.0,
                    )

    def test_merge_split_relative_is_opt_in_and_reports_state(self) -> None:
        with TemporaryDirectory(prefix="studio-merge-split-opt-in-") as tmp:
            root = Path(tmp)
            score_path = root / "score.jsonl"
            trace_path = root / "trace.jsonl"
            _write_jsonl(
                score_path,
                [{"solver_frame_index": 0, "target_x": 20.0, "target_y": 20.0}],
            )
            _write_jsonl(
                trace_path,
                [
                    {
                        "type": "SESSION_START",
                        "frame_index": None,
                        "payload": {"board_roi": {"w": 100, "h": 100}},
                    },
                    {
                        "type": "CANDIDATES",
                        "frame_index": 0,
                        "payload": {
                            "candidates": [
                                {
                                    "candidate_id": "target",
                                    "center": [20.0, 20.0],
                                    "bbox": [18.0, 18.0, 22.0, 22.0],
                                    "score": 0.9,
                                    "source": "raw",
                                }
                            ]
                        },
                    },
                    {
                        "type": "TARGET_SELECTION",
                        "frame_index": 0,
                        "payload": {"point": [20.0, 20.0], "source": "recorded"},
                    },
                    {
                        "type": "TEMPORAL_SELECTOR",
                        "frame_index": 0,
                        "payload": {
                            "debug": {
                                "kinematic_wide_beam_debug": {
                                    "reason": "white_anchor",
                                    "point": [20.0, 20.0],
                                }
                            }
                        },
                    },
                ],
            )

            baseline = replay_hypothesis_selection_details(score_path, trace_path)
            enabled = replay_hypothesis_selection_details(
                score_path,
                trace_path,
                merge_split_relative=True,
            )

            self.assertNotIn("merge_split_relative", baseline[0])
            self.assertIn("merge_split_relative", enabled[0])
            self.assertIn(
                enabled[0]["merge_split_relative"]["state"],
                {"SEPARATE", "PARTIAL_OVERLAP", "MERGED", "SPLITTING", "REACQUIRED"},
            )
            self.assertIn("anchor_count", enabled[0]["merge_split_relative"])
            self.assertIn("fingerprint_pair_count", enabled[0]["merge_split_relative"])
            self.assertEqual(
                enabled[0]["merge_split_relative"]["quorum"]["reason"],
                "protected_incumbent",
            )

    def test_temporal_only_frames_do_not_change_non_opt_in_replay(self) -> None:
        with TemporaryDirectory(prefix="studio-temporal-only-opt-out-") as tmp:
            root = Path(tmp)
            score_path = root / "score.jsonl"
            baseline_trace_path = root / "baseline.jsonl"
            temporal_only_trace_path = root / "temporal-only.jsonl"
            scores = [
                {"solver_frame_index": frame_index, "target_x": 20.0, "target_y": 20.0}
                for frame_index in (0, 1, 2)
            ]
            candidate_rows = [
                {
                    "type": "CANDIDATES",
                    "frame_index": frame_index,
                    "payload": {"candidates": [_trace_candidate(f"target-{frame_index}", (20.0, 20.0))]},
                }
                for frame_index in (0, 2)
            ]
            target_rows = [
                {
                    "type": "TARGET_SELECTION",
                    "frame_index": frame_index,
                    "payload": {"point": [20.0, 20.0], "source": "recorded"},
                }
                for frame_index in (0, 1, 2)
            ]
            temporal_only = {
                "type": "TEMPORAL_SELECTOR",
                "frame_index": 1,
                "payload": {"debug": {"kinematic_wide_beam_debug": {"reason": "tracking"}}},
            }
            _write_jsonl(score_path, scores)
            _write_jsonl(baseline_trace_path, candidate_rows + target_rows)
            _write_jsonl(
                temporal_only_trace_path,
                candidate_rows[:1] + target_rows[:1] + [temporal_only] + candidate_rows[1:] + target_rows[1:],
            )

            baseline = replay_hypothesis_selection_details(score_path, baseline_trace_path)
            temporal_only_result = replay_hypothesis_selection_details(
                score_path,
                temporal_only_trace_path,
            )

            self.assertEqual(temporal_only_result, baseline)

    def test_merge_split_shadow_reports_cycle_phase_without_runtime_gt(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-lineage-") as tmp:
            root = Path(tmp)
            score_path = root / "score.jsonl"
            trace_path = root / "trace.jsonl"
            scores: list[dict[str, object]] = []
            trace: list[dict[str, object]] = [
                {
                    "type": "SESSION_START",
                    "frame_index": None,
                    "payload": {"board_roi": {"w": 120, "h": 100}},
                }
            ]
            for frame_index in range(12):
                phase = frame_index % 3
                anchor_a = (20.0 + phase * 2.0, 20.0)
                anchor_b = (80.0 + phase * 2.0, 20.0)
                background = (48.0 + phase * 2.0, 50.0)
                target = (
                    (60.0, 50.0)
                    if frame_index < 9
                    else (58.0 + float(frame_index - 9), 50.0)
                )
                candidates = [
                    _trace_candidate(f"anchor-a-{frame_index}", anchor_a),
                    _trace_candidate(f"anchor-b-{frame_index}", anchor_b),
                    _trace_candidate(f"background-{frame_index}", background),
                ]
                if frame_index < 9:
                    candidates.append(_trace_candidate(f"target-{frame_index}", target))
                candidates = candidates[phase:] + candidates[:phase]
                scores.append(
                    {
                        "solver_frame_index": frame_index,
                        "target_x": target[0],
                        "target_y": target[1],
                    }
                )
                trace.append(
                    {
                        "type": "CANDIDATES",
                        "frame_index": frame_index,
                        "payload": {"candidates": candidates},
                    }
                )
                if frame_index < 9:
                    trace.append(
                        {
                            "type": "TEMPORAL_SELECTOR",
                            "frame_index": frame_index,
                            "payload": {
                                "debug": {
                                    "kinematic_wide_beam_debug": {
                                        "reason": "white_anchor",
                                        "point": [target[0], target[1]],
                                    }
                                }
                            },
                        }
                    )
                trace.extend(
                    [
                        {
                            "type": "EVIDENCE",
                            "frame_index": frame_index,
                            "payload": {
                                "evidence": [
                                    {
                                        "candidate_id": row["candidate_id"],
                                        "bg_score": (
                                            0.1
                                            if row["candidate_id"].startswith("target-")
                                            else 0.8
                                        ),
                                    }
                                    for row in candidates
                                ]
                            },
                        },
                        {
                            "type": "TARGET_SELECTION",
                            "frame_index": frame_index,
                            "payload": {
                                "point": [target[0], target[1]],
                                "source": "recorded",
                            },
                        },
                    ]
                )
            _write_jsonl(score_path, scores)
            _write_jsonl(trace_path, trace)

            baseline = replay_hypothesis_selection_details(score_path, trace_path)
            details = replay_hypothesis_selection_details(
                score_path,
                trace_path,
                merge_split_relative=True,
            )

            self.assertNotIn("merge_split_relative", baseline[-1])
            self.assertEqual(baseline[-1]["replay_point"], details[-1]["replay_point"])
            phased = [
                row["merge_split_relative"]
                for row in details
                if row["merge_split_relative"]["period"] is not None
            ]
            self.assertTrue(phased)
            diagnostic = phased[-1]
            self.assertEqual(diagnostic["period"], 3)
            self.assertEqual(diagnostic["local_lag"], 3)
            self.assertEqual(diagnostic["reference_frame"], 8)
            self.assertGreaterEqual(diagnostic["period_recurrence_comparisons"], 2)
            self.assertIn("merge_event_id", diagnostic)
            self.assertIn("selected_split_child_ids", diagnostic)
            self.assertIn("hold_reason", diagnostic)
            self.assertIn("quorum", diagnostic)
            self.assertNotIn("target_point", diagnostic["cycle_input"])

    def test_merge_split_shadow_fails_closed_without_cycle_evidence(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-lineage-weak-") as tmp:
            root = Path(tmp)
            score_path = root / "score.jsonl"
            trace_path = root / "trace.jsonl"
            scores = [
                {"solver_frame_index": frame_index, "target_x": 60.0, "target_y": 50.0}
                for frame_index in range(4)
            ]
            trace: list[dict[str, object]] = [
                {
                    "type": "SESSION_START",
                    "frame_index": None,
                    "payload": {"board_roi": {"w": 120, "h": 100}},
                }
            ]
            for frame_index in range(4):
                candidates = [
                    _trace_candidate(f"anchor-{frame_index}", (20.0 + frame_index, 20.0)),
                    _trace_candidate(f"target-{frame_index}", (60.0, 50.0)),
                ]
                trace.extend(
                    [
                        {
                            "type": "CANDIDATES",
                            "frame_index": frame_index,
                            "payload": {"candidates": candidates},
                        },
                        {
                            "type": "TEMPORAL_SELECTOR",
                            "frame_index": frame_index,
                            "payload": {
                                "debug": {
                                    "kinematic_wide_beam_debug": {
                                        "reason": "white_anchor" if frame_index < 2 else "tracking",
                                        "point": [60.0, 50.0],
                                    }
                                }
                            },
                        },
                        {
                            "type": "TARGET_SELECTION",
                            "frame_index": frame_index,
                            "payload": {"point": [60.0, 50.0], "source": "recorded"},
                        },
                    ]
                )
            _write_jsonl(score_path, scores)
            _write_jsonl(trace_path, trace)

            details = replay_hypothesis_selection_details(
                score_path,
                trace_path,
                merge_split_relative=True,
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertIsNone(diagnostic["period"])
            self.assertIsNone(diagnostic["local_lag"])
            self.assertEqual(diagnostic["cycle_evidence_reason"], "period_unavailable")

    def test_merge_split_shadow_rejects_finite_nonperiodic_episode(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-nonperiodic-") as tmp:
            root = Path(tmp)
            frames = [
                [
                    _trace_candidate(f"left-{frame_index}", (20.0 + frame_index * 12.0, 20.0)),
                    _trace_candidate(f"right-{frame_index}", (80.0 + frame_index * 12.0, 20.0)),
                    _trace_candidate(f"background-{frame_index}", (48.0 + frame_index * 12.0, 50.0)),
                    _trace_candidate(f"target-{frame_index}", (60.0, 50.0)),
                ]
                for frame_index in range(10)
            ]
            details = _replay_cycle_details(
                root,
                frames,
                white_frames=set(range(9)),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertIsNone(diagnostic["period"])
            self.assertEqual(
                diagnostic["cycle_evidence_reason"],
                "period_association_quality",
            )

    def test_merge_split_shadow_rejects_unverified_local_lag(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-local-lag-") as tmp:
            root = Path(tmp)
            frames = _periodic_cycle_frames(total_frames=10, empty_frames={9})
            details = _replay_cycle_details(
                root,
                frames,
                white_frames=set(range(9)),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertEqual(diagnostic["period"], 3)
            self.assertIsNone(diagnostic["local_lag"])
            self.assertFalse(diagnostic["phase_qualified"])
            self.assertEqual(
                diagnostic["local_lag_evidence_reason"],
                "frozen_survivor_missing",
            )

    def test_merge_split_shadow_local_lag_requires_strict_bijection(self) -> None:
        cases: dict[str, tuple[list[dict[str, object]], bool]] = {}
        extra = _periodic_cycle_frames(total_frames=10)
        cases["extra_current_candidate"] = (extra[-1], True)
        missing = _periodic_cycle_frames(total_frames=10)
        missing[-1] = [
            candidate
            for candidate in missing[-1]
            if not str(candidate["candidate_id"]).startswith(("anchor-b-", "target-"))
        ]
        cases["missing_current_candidate"] = (missing[-1], False)
        reordered = _periodic_cycle_frames(total_frames=10)
        reordered[-1] = [
            {
                **candidate,
                "candidate_id": f"reordered-{index}",
            }
            for index, candidate in enumerate(
                reversed(
                    [
                        candidate
                        for candidate in reordered[-1]
                        if not str(candidate["candidate_id"]).startswith("target-")
                    ]
                )
            )
        ]
        cases["reordered_equal_cardinality"] = (reordered[-1], True)

        for name, (last_frame, expected_qualified) in cases.items():
            with self.subTest(name=name), TemporaryDirectory(
                prefix=f"studio-local-bijection-{name}-"
            ) as tmp:
                frames = _periodic_cycle_frames(total_frames=10)
                frames[-1] = last_frame
                details = _replay_cycle_details(
                    Path(tmp),
                    frames,
                    white_frames=set(range(9)),
                )

                diagnostic = details[-1]["merge_split_relative"]
                self.assertEqual(diagnostic["period"], 3)
                self.assertEqual(
                    diagnostic["phase_qualified"],
                    expected_qualified,
                )
                self.assertEqual(
                    diagnostic["phase_context_active"],
                    expected_qualified,
                )
                if expected_qualified:
                    self.assertEqual(diagnostic["local_lag"], 3)
                else:
                    self.assertIsNone(diagnostic["local_lag"])
                    self.assertEqual(
                        diagnostic["local_lag_evidence_reason"],
                        "frozen_survivor_missing",
                    )

    def test_merge_split_shadow_local_lag_requires_temporal_consistency(self) -> None:
        cases: dict[str, list[list[dict[str, object]]]] = {}
        swap = _periodic_cycle_frames(total_frames=10)
        swap[3] = _temporal_chain_candidates(3, (13.0, 47.0), include_anchor=True)
        swap[6] = _temporal_chain_candidates(6, (28.0, 32.0), include_anchor=True)
        swap[9] = _temporal_chain_candidates(9, (24.0, 36.0), include_anchor=False)
        cases["temporal_swap"] = swap

        missing_history = _periodic_cycle_frames(total_frames=10)
        missing_history[3] = []
        missing_history[9] = [
            candidate
            for candidate in missing_history[9]
            if not str(candidate["candidate_id"]).startswith("target-")
        ]
        cases["missing_history"] = missing_history

        stable = _periodic_cycle_frames(total_frames=10)
        stable[3] = _temporal_chain_candidates(3, (20.0, 50.0), include_anchor=True)
        stable[6] = _temporal_chain_candidates(
            6,
            (24.0, 54.0),
            include_anchor=True,
            reverse=True,
        )
        stable[9] = _temporal_chain_candidates(
            9,
            (28.0, 58.0),
            include_anchor=False,
            reverse=True,
        )
        cases["stable_reordered_chain"] = stable

        for name, frames in cases.items():
            with self.subTest(name=name), TemporaryDirectory(
                prefix=f"studio-local-temporal-{name}-"
            ) as tmp:
                details = _replay_cycle_details(
                    Path(tmp),
                    frames,
                    white_frames=set(range(9)),
                )

                diagnostic = details[-1]["merge_split_relative"]
                self.assertIsNone(diagnostic["period"])
                self.assertFalse(diagnostic["phase_qualified"])
                self.assertTrue(diagnostic["stable_cycle_exclusion_reasons"])

    def test_merge_split_shadow_uses_stable_tracks_when_raw_cardinality_varies(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-stable-subset-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _volatile_periodic_cycle_frames(total_frames=10),
                white_frames=set(range(9)),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertEqual(diagnostic["period"], 3)
            self.assertEqual(diagnostic["local_lag"], 3)
            self.assertTrue(diagnostic["phase_qualified"])
            self.assertEqual(diagnostic["stable_cycle_track_count"], 3)
            self.assertEqual(len(diagnostic["stable_cycle_track_ids"]), 3)
            self.assertGreater(diagnostic["raw_candidate_count"], 3)
            self.assertTrue(diagnostic["stable_cycle_excluded_counts"])

    def test_merge_split_shadow_stable_tracks_ignore_reordered_volatile_extras(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-stable-reordered-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _volatile_periodic_cycle_frames(total_frames=10, reorder_extras=True),
                white_frames=set(range(9)),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertEqual(diagnostic["period"], 3)
            self.assertEqual(diagnostic["local_lag"], 3)
            self.assertEqual(diagnostic["local_lag_evidence_reason"], "observed_local_lag")
            self.assertNotIn(
                "association_permutation",
                diagnostic["stable_cycle_excluded_counts"],
            )

    def test_merge_split_shadow_rejects_distinct_destination_track_swap(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-track-swap-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _track_swap_cycle_frames(total_frames=10),
                white_frames=set(range(9)),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertIsNone(diagnostic["period"])
            self.assertFalse(diagnostic["phase_qualified"])
            self.assertGreaterEqual(
                diagnostic["stable_cycle_excluded_counts"].get(
                    "association_permutation",
                    0,
                ),
                2,
            )

    def test_merge_split_shadow_rejects_same_assignment_path_crossing(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-path-crossing-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _same_assignment_crossing_cycle_frames(total_frames=10),
                white_frames=set(range(9)),
                frame_shape=(400, 400),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertIsNone(diagnostic["period"])
            self.assertGreaterEqual(
                diagnostic["stable_cycle_excluded_counts"].get(
                    "association_crossing",
                    0,
                ),
                2,
            )

    def test_merge_split_shadow_rejects_initial_actual_path_crossing(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-initial-path-crossing-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _initial_actual_crossing_cycle_frames(total_frames=10),
                white_frames=set(range(9)),
                frame_shape=(400, 400),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertIsNone(diagnostic["period"])
            self.assertGreaterEqual(
                diagnostic["stable_cycle_excluded_counts"].get(
                    "association_crossing",
                    0,
                ),
                2,
            )

    def test_merge_split_shadow_rejects_predicted_assignment_failure(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-prediction-reject-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _predicted_rejection_cycle_frames(total_frames=10),
                white_frames=set(range(9)),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertIsNone(diagnostic["period"])
            self.assertTrue(
                diagnostic["stable_cycle_excluded_counts"].get(
                    "association_ambiguous",
                    0,
                )
                or diagnostic["stable_cycle_excluded_counts"].get(
                    "association_disagreement",
                    0,
                )
            )

    def test_merge_split_shadow_does_not_freeze_ambiguous_rejected_candidates(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-ambiguous-atomic-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _long_ambiguous_candidate_cycle_frames(total_frames=30),
                white_frames=set(range(29)),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertIsNone(diagnostic["period"])
            self.assertEqual(diagnostic["stable_cycle_track_count"], 0)
            self.assertGreaterEqual(
                diagnostic["stable_cycle_excluded_counts"].get(
                    "association_ambiguous",
                    0,
                ),
                3,
            )

    def test_cycle_frame_shape_requires_finite_positive_integers(self) -> None:
        for frame_shape in (
            (True, 100),
            (100, False),
            (100.5, 80),
            (100, float("inf")),
            (100, -1),
        ):
            with self.subTest(frame_shape=frame_shape):
                self.assertFalse(_valid_cycle_frame_shape(frame_shape))

    def test_merge_split_shadow_rejects_noninteger_frame_shapes(self) -> None:
        for frame_shape in (
            (True, 100),
            (100.5, 80),
            (100, float("inf")),
            ("100", "140"),
            (100.0, 140.0),
        ):
            with self.subTest(frame_shape=frame_shape), TemporaryDirectory(
                prefix="studio-cycle-invalid-frame-shape-",
            ) as tmp:
                details = _replay_cycle_details(
                    Path(tmp),
                    _periodic_cycle_frames(total_frames=10),
                    white_frames=set(range(9)),
                    frame_shape=frame_shape,
                )

                diagnostic = details[-1]["merge_split_relative"]
                self.assertIsNone(diagnostic["period"])
                self.assertFalse(diagnostic["phase_qualified"])
                self.assertEqual(
                    diagnostic["stable_cycle_frame_shape_reason"],
                    "frame_shape_unavailable",
                )

    def test_period_recurrence_rejects_frozen_track_position_permutation(self) -> None:
        positions = ((20.0, 20.0), (80.0, 20.0), (50.0, 50.0))
        observations = {
            frame_index: tuple(
                _FrozenCycleObservation(
                    f"cycle-track-{track_index}",
                    PuzzleCandidate(cx, cy, 0.8, 10.0, 10.0),
                )
                for track_index, (cx, cy) in enumerate(
                    positions if frame_index != 3 else positions[1:] + positions[:1]
                )
            )
            for frame_index in (0, 3, 6)
        }

        supported, reason, comparisons = _period_recurrence_support(observations, 3)

        self.assertFalse(supported)
        self.assertEqual(reason, "period_association_quality")
        self.assertEqual(comparisons, 0)

    def test_period_recurrence_rejects_later_frozen_track_permutation(self) -> None:
        positions = ((20.0, 20.0), (80.0, 20.0), (50.0, 50.0))
        observations = {
            frame_index: tuple(
                _FrozenCycleObservation(
                    f"cycle-track-{track_index}",
                    PuzzleCandidate(cx, cy, 0.8, 10.0, 10.0),
                )
                for track_index, (cx, cy) in enumerate(
                    positions if frame_index != 9 else positions[1:] + positions[:1]
                )
            )
            for frame_index in (0, 3, 6, 9)
        }

        supported, reason, comparisons = _period_recurrence_support(observations, 3)

        self.assertFalse(supported)
        self.assertEqual(reason, "period_association_quality")
        self.assertEqual(comparisons, 0)

    def test_merge_split_shadow_does_not_freeze_duplicate_rejected_candidates(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-duplicate-atomic-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _long_duplicate_candidate_cycle_frames(total_frames=30),
                white_frames=set(range(29)),
                frame_shape=(200, 200),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertEqual(diagnostic["stable_cycle_track_ids"], ("cycle-track-3",))
            self.assertGreaterEqual(
                diagnostic["stable_cycle_excluded_counts"].get(
                    "association_ambiguous",
                    0,
                ),
                2,
            )

    def test_merge_split_shadow_does_not_freeze_reverse_only_candidates(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-reverse-only-atomic-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _long_reverse_only_candidate_cycle_frames(total_frames=30),
                white_frames=set(range(29)),
                frame_shape=(300, 300),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertEqual(
                diagnostic["stable_cycle_track_ids"],
                ("cycle-track-2", "cycle-track-3"),
            )
            self.assertGreaterEqual(
                diagnostic["stable_cycle_excluded_counts"].get(
                    "association_ambiguous",
                    0,
                ),
                1,
            )

    def test_frozen_tracks_reject_predicted_assignment_without_committing_state(self) -> None:
        tracks = _StableCycleTracks(frame_shape=(200, 200))
        tracks.update(
            0,
            _cycle_candidates(0, ((20.0, 20.0), (60.0, 20.0), (120.0, 20.0))),
        )
        tracks.update(
            1,
            _cycle_candidates(1, ((30.0, 20.0), (50.0, 20.0), (120.0, 20.0))),
        )
        frozen_before = tracks.freeze()

        tracks.update(
            2,
            _cycle_candidates(
                2,
                ((30.0, 20.0), (50.0, 20.0), (120.0, 20.0)),
            ),
        )

        observation, reason = tracks.frozen_observation(2)
        self.assertIsNone(observation)
        self.assertEqual(reason, "ambiguous")
        self.assertEqual(tracks.freeze(), frozen_before)
        self.assertEqual(
            set(tracks._tracks["cycle-track-1"].observations),
            {0, 1},
        )

    def test_frozen_tracks_reject_reverse_velocity_prediction_without_commit(self) -> None:
        tracks = _StableCycleTracks(frame_shape=(300, 300))
        tracks.update(
            0,
            _cycle_candidates(0, ((50.0, 20.0), (160.0, 20.0), (230.0, 20.0))),
        )
        tracks.update(
            1,
            _cycle_candidates(1, ((70.0, 20.0), (160.0, 20.0), (230.0, 20.0))),
        )
        frozen_before = tracks.freeze()

        tracks.update(
            2,
            _cycle_candidates(2, ((29.0, 20.0), (160.0, 20.0), (230.0, 20.0))),
        )

        observation, reason = tracks.frozen_observation(2)
        self.assertIsNone(observation)
        self.assertEqual(reason, "missing")
        self.assertEqual(tracks.freeze(), frozen_before)
        self.assertEqual(
            set(tracks._tracks["cycle-track-1"].observations),
            {0, 1},
        )

    def test_merge_split_shadow_rejects_late_tracks_after_empty_white_start(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-empty-start-") as tmp:
            frames = _periodic_cycle_frames(total_frames=10)
            frames[0] = [_trace_candidate("target-0", (60.0, 50.0))]
            details = _replay_cycle_details(
                Path(tmp),
                frames,
                white_frames=set(range(9)),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertIsNone(diagnostic["period"])
            self.assertEqual(
                diagnostic["stable_cycle_excluded_counts"].get("cycle_coverage"),
                3,
            )

    def test_merge_split_shadow_counts_missing_candidate_frame_in_episode_coverage(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-missing-candidates-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _periodic_cycle_frames(total_frames=10),
                white_frames=set(range(9)),
                omit_candidate_frames={4},
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertIsNone(diagnostic["period"])
            self.assertEqual(
                diagnostic["stable_cycle_excluded_counts"].get("association_missing"),
                3,
            )

    def test_merge_split_shadow_rejects_cycle_when_frame_shape_is_unknown(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-frame-shape-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _periodic_cycle_frames(total_frames=10),
                white_frames=set(range(9)),
                include_frame_shape=False,
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertIsNone(diagnostic["period"])
            self.assertFalse(diagnostic["phase_qualified"])
            self.assertEqual(
                diagnostic["stable_cycle_frame_shape_reason"],
                "frame_shape_unavailable",
            )

    def test_merge_split_shadow_requires_three_stable_cycle_tracks(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-stable-minimum-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _volatile_periodic_cycle_frames(total_frames=10, stable_count=2),
                white_frames=set(range(9)),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertIsNone(diagnostic["period"])
            self.assertFalse(diagnostic["phase_qualified"])
            self.assertEqual(diagnostic["stable_cycle_track_count"], 2)

    def test_merge_split_shadow_rejects_invalid_frozen_stable_survivor(self) -> None:
        cases = {
            "missing": _volatile_periodic_cycle_frames(
                total_frames=10,
                missing_stable_frame=5,
            ),
            "clipped": _volatile_periodic_cycle_frames(
                total_frames=10,
                clipped_stable_frame=5,
            ),
            "crossing": _volatile_periodic_cycle_frames(
                total_frames=10,
                crossing_frame=5,
            ),
        }
        for name, frames in cases.items():
            with self.subTest(name=name), TemporaryDirectory(
                prefix=f"studio-cycle-stable-{name}-"
            ) as tmp:
                details = _replay_cycle_details(
                    Path(tmp),
                    frames,
                    white_frames=set(range(9)),
                )

                diagnostic = details[-1]["merge_split_relative"]
                self.assertIsNone(diagnostic["period"])
                self.assertFalse(diagnostic["phase_qualified"])
                self.assertTrue(diagnostic["stable_cycle_exclusion_reasons"])

    def test_merge_split_shadow_local_lag_rejects_missing_frozen_survivor(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-frozen-local-lag-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _volatile_periodic_cycle_frames(
                    total_frames=10,
                    missing_post_episode_stable=True,
                ),
                white_frames=set(range(9)),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertEqual(diagnostic["period"], 3)
            self.assertIsNone(diagnostic["local_lag"])
            self.assertFalse(diagnostic["phase_qualified"])
            self.assertEqual(
                diagnostic["local_lag_evidence_reason"],
                "frozen_survivor_missing",
            )

    def test_merge_split_shadow_closes_second_white_episode(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-second-episode-") as tmp:
            root = Path(tmp)
            frames = _periodic_cycle_frames(total_frames=15)
            details = _replay_cycle_details(
                root,
                frames,
                white_frames=set(range(9)) | set(range(10, 14)),
            )

            self.assertEqual(details[9]["merge_split_relative"]["period"], 3)
            preparing = details[13]["merge_split_relative"]
            self.assertIsNone(preparing["period"])
            self.assertIsNone(preparing["local_lag"])
            self.assertFalse(preparing["phase_qualified"])
            self.assertEqual(preparing["stable_cycle_track_count"], 0)
            self.assertEqual(preparing["stable_cycle_track_ids"], ())
            self.assertEqual(preparing["stable_cycle_excluded_counts"], {})
            self.assertEqual(preparing["stable_cycle_exclusion_reasons"], {})

            diagnostic = details[14]["merge_split_relative"]
            self.assertEqual(diagnostic["period"], 3)
            self.assertTrue(diagnostic["phase_qualified"])
            self.assertEqual(
                diagnostic["cycle_evidence_reason"],
                "observed_period",
            )
            self.assertEqual(diagnostic["local_lag"], 3)
            self.assertEqual(
                diagnostic["local_lag_evidence_reason"],
                "observed_local_lag",
            )
            self.assertEqual(diagnostic["stable_cycle_track_count"], 3)
            self.assertEqual(diagnostic["period_recurrence_comparisons"], 1)

    def test_merge_split_shadow_rejects_cardinality_and_temporal_swap(self) -> None:
        cases = {
            "first_occurrence_missing": (
                ((20.0, 40.0), (20.0, 40.0, 60.0), (20.0, 40.0, 60.0)),
                1.0,
            ),
            "last_occurrence_missing": (
                ((20.0, 40.0, 60.0), (20.0, 40.0, 60.0), (20.0, 40.0)),
                1.0,
            ),
            "temporal_swap": (
                ((20.0, 40.0), (28.0, 32.0), (40.0, 20.0)),
                8.0,
            ),
        }
        for name, (occurrences, half_size) in cases.items():
            with self.subTest(name=name), TemporaryDirectory(
                prefix=f"studio-cycle-{name}-"
            ) as tmp:
                frames = _sparse_cycle_chain_frames(
                    occurrences,
                    half_size=half_size,
                )
                details = _replay_cycle_details(
                    Path(tmp),
                    frames,
                    white_frames=set(range(7)),
                )

                diagnostic = details[-1]["merge_split_relative"]
                self.assertIsNone(diagnostic["period"])
                self.assertFalse(diagnostic["phase_qualified"])
                self.assertIn(
                    diagnostic["cycle_evidence_reason"],
                    {
                        "period_association_incomplete",
                        "period_association_permutation",
                    },
                )

    def test_merge_split_shadow_rejects_ambiguous_or_incomplete_cycle_association(self) -> None:
        cases: dict[str, tuple[list[list[dict[str, object]]], set[int]]] = {}
        crossing = _periodic_cycle_frames(total_frames=10)
        for frame_index in range(3, 6):
            phase = frame_index % 3
            crossing[frame_index] = [
                _trace_candidate(f"anchor-a-{frame_index}", (20.0 + phase * 2.0, 20.0)),
                _trace_candidate(f"cross-a-{frame_index}", (20.0 + phase * 2.0, 20.0)),
                _trace_candidate(f"anchor-b-{frame_index}", (80.0 + phase * 2.0, 20.0)),
                _trace_candidate(f"background-{frame_index}", (48.0 + phase * 2.0, 50.0)),
                _trace_candidate(f"target-{frame_index}", (60.0, 50.0)),
            ]
        cases["crossing"] = (crossing, set(range(9)))
        omitted: list[list[dict[str, object]]] = []
        for frame_index in range(8):
            if frame_index % 3 != 0:
                omitted.append([_trace_candidate(f"target-{frame_index}", (60.0, 50.0))])
                continue
            rows = _periodic_cycle_frames(total_frames=frame_index + 1)[-1]
            if frame_index == 3:
                rows = [
                    candidate
                    for candidate in rows
                    if not str(candidate["candidate_id"]).startswith("anchor-b-")
                ]
            omitted.append(rows)
        cases["one_frame_omission"] = (omitted, set(range(7)))

        for name, (frames, white_frames) in cases.items():
            with self.subTest(name=name), TemporaryDirectory(
                prefix=f"studio-cycle-{name}-"
            ) as tmp:
                details = _replay_cycle_details(
                    Path(tmp),
                    frames,
                    white_frames=white_frames,
                )

                diagnostic = details[-1]["merge_split_relative"]
                self.assertIsNone(diagnostic["period"])
                self.assertIn(
                    diagnostic["cycle_evidence_reason"],
                    {
                        "period_association_ambiguous",
                        "period_association_incomplete",
                    },
                )

    def test_merge_split_relative_reports_relation_preserving_split_child(self) -> None:
        with TemporaryDirectory(prefix="studio-merge-split-trace-") as tmp:
            root = Path(tmp)
            score_path = root / "score.jsonl"
            trace_path = root / "trace.jsonl"
            frame_candidates = [
                ((34.0, 32.0), (30.0, 28.0), "target"),
                ((34.0, 32.0), (30.0, 28.0), "target"),
                ((34.0, 32.0), (30.0, 28.0), "target"),
                ((31.0, 29.0), (30.0, 28.0), "overlap-target"),
                ((31.0, 29.0), (30.0, 28.0), "overlap-target"),
                ((33.0, 31.0), (30.0, 28.0), "target-child"),
                ((33.0, 31.0), (30.0, 28.0), "target-child"),
                ((33.0, 31.0), (30.0, 28.0), "target-child"),
            ]
            scores: list[dict[str, object]] = []
            trace: list[dict[str, object]] = [
                {
                    "type": "SESSION_START",
                    "frame_index": None,
                    "payload": {"board_roi": {"w": 100, "h": 100}},
                }
            ]
            for frame_index, (target, background, target_id) in enumerate(frame_candidates):
                scores.append(
                    {
                        "solver_frame_index": frame_index,
                        "target_x": target[0],
                        "target_y": target[1],
                    }
                )
                candidates = [
                    _trace_candidate(target_id, target),
                    _trace_candidate(
                        "background-child" if frame_index == 5 else "background",
                        background,
                    ),
                    _trace_candidate("anchor-a", (20.0, 20.0)),
                    _trace_candidate("anchor-b", (40.0, 20.0)),
                ]
                trace.extend(
                    [
                        {
                            "type": "CANDIDATES",
                            "frame_index": frame_index,
                            "payload": {"candidates": candidates},
                        },
                        {
                            "type": "EVIDENCE",
                            "frame_index": frame_index,
                            "payload": {
                                "evidence": [
                                    {
                                        "candidate_id": candidate["candidate_id"],
                                        "bg_score": (
                                            0.1 if candidate["candidate_id"] == target_id else 0.8
                                        ),
                                        "motion_divergence": (
                                            0.9 if candidate["candidate_id"] == target_id else 0.1
                                        ),
                                    }
                                    for candidate in candidates
                                ]
                            },
                        },
                        {
                            "type": "TARGET_SELECTION",
                            "frame_index": frame_index,
                            "payload": {
                                "point": (
                                    [background[0], background[1]]
                                    if frame_index >= 5
                                    else [target[0], target[1]]
                                ),
                                "source": "recorded",
                            },
                        },
                    ]
                )
            _write_jsonl(score_path, scores)
            _write_jsonl(trace_path, trace)

            details = replay_hypothesis_selection_details(
                score_path,
                trace_path,
                merge_split_relative=True,
            )

            split = details[5]["merge_split_relative"]
            self.assertEqual(split["state"], "SPLITTING")
            self.assertEqual(split["background_candidate_id"], "background-child")
            self.assertEqual(split["target_candidate_id"], "target-child")
            self.assertGreater(split["relative_margin"], 1.0)
            self.assertFalse(details[5]["changed"])
            self.assertFalse(details[6]["changed"])
            self.assertEqual(details[7]["replay_source"], "merge_split_relative")
            self.assertEqual(details[7]["replay_point"], [33.0, 31.0])
            self.assertTrue(details[7]["replay_passed"])

    def test_opt_in_cycle_without_period_holds_and_preserves_baseline(self) -> None:
        with TemporaryDirectory(prefix="studio-cycle-hard-gate-") as tmp:
            score_path, trace_path = _write_merge_lineage_replay(Path(tmp))

            baseline = replay_hypothesis_selection_details(score_path, trace_path)
            enabled = replay_hypothesis_selection_details(
                score_path,
                trace_path,
                merge_split_relative=True,
            )

            self.assertEqual(
                [row["replay_point"] for row in enabled],
                [row["replay_point"] for row in baseline],
            )
            split = enabled[5]["merge_split_relative"]
            self.assertEqual(split["state"], "SPLITTING")
            self.assertEqual(split["reason"], "cycle_phase_unavailable")
            self.assertEqual(split["hold_reason"], "cycle_phase_unavailable")
            self.assertIsNone(split["target_candidate_id"])

    def test_score_rows_do_not_control_runtime_lineage_state(self) -> None:
        with TemporaryDirectory(prefix="studio-score-independent-full-") as full_tmp:
            full_score, full_trace = _write_merge_lineage_replay(Path(full_tmp))
            full = replay_hypothesis_selection_details(
                full_score,
                full_trace,
                merge_split_relative=True,
            )
        with TemporaryDirectory(prefix="studio-score-independent-sparse-") as sparse_tmp:
            sparse_score, sparse_trace = _write_merge_lineage_replay(
                Path(sparse_tmp),
                omitted_score_frames={3, 4},
            )
            sparse = replay_hypothesis_selection_details(
                sparse_score,
                sparse_trace,
                merge_split_relative=True,
            )

        full_by_frame = {row["frame_index"]: row for row in full}
        sparse_by_frame = {row["frame_index"]: row for row in sparse}
        for frame_index in range(5, 9):
            with self.subTest(frame_index=frame_index):
                full_row = full_by_frame[frame_index]
                sparse_row = sparse_by_frame[frame_index]
                self.assertEqual(sparse_row["replay_point"], full_row["replay_point"])
                self.assertEqual(sparse_row["replay_source"], full_row["replay_source"])
                self.assertEqual(
                    sparse_row["merge_split_relative"]["merge_event_id"],
                    full_row["merge_split_relative"]["merge_event_id"],
                )
                self.assertEqual(
                    sparse_row["merge_split_relative"]["state"],
                    full_row["merge_split_relative"]["state"],
                )
                self.assertEqual(
                    sparse_row["merge_split_relative"]["reason"],
                    full_row["merge_split_relative"]["reason"],
                )
        self.assertEqual(len(sparse), len(full) - 2)

    def test_phase_resolver_uses_studio_frozen_track_ids(self) -> None:
        with TemporaryDirectory(prefix="studio-phase-stable-id-") as tmp:
            details = _replay_cycle_details(
                Path(tmp),
                _periodic_cycle_frames(total_frames=12),
                white_frames=set(range(9)),
            )

            diagnostic = details[-1]["merge_split_relative"]
            self.assertTrue(diagnostic["phase_qualified"])
            self.assertEqual(
                set(diagnostic["resolver_anchor_track_ids"]),
                set(diagnostic["stable_cycle_track_ids"]),
            )
            self.assertTrue(
                all(
                    track_id.startswith("cycle-track-")
                    for track_id in diagnostic["resolver_anchor_track_ids"]
                )
            )

    def test_shape_normalized_boundary_margin_disqualifies_stable_track(self) -> None:
        tracks = _StableCycleTracks(frame_shape=(100, 100))

        tracks.update(
            0,
            _cycle_candidates(
                0,
                ((12.0, 50.0), (50.0, 50.0), (75.0, 50.0)),
            ),
        )

        self.assertEqual(tracks.exclusion_reasons["cycle-track-1"], "cycle_clipped")

    def test_exactly_one_cycle_pair_can_estimate_period_and_local_lag(self) -> None:
        observations = {
            frame_index: tuple(
                _FrozenCycleObservation(
                    f"cycle-track-{track_index}",
                    PuzzleCandidate(cx, cy, 0.8, 10.0, 10.0),
                )
                for track_index, (cx, cy) in enumerate(
                    ((20.0, 20.0), (50.0, 20.0), (80.0, 20.0))
                )
            )
            for frame_index in (0, 3)
        }
        catalog = BackgroundCatalog()
        for frame_index, frame in observations.items():
            catalog.add_frame(
                frame_index,
                [observation.candidate for observation in frame],
            )

        period, _score, reason, comparisons = _observed_episode_period(
            catalog,
            observations,
        )
        local_ok, local_reason = _local_lag_temporal_support(
            observations,
            frame_index=3,
            lag=3,
        )

        self.assertEqual(period, 3)
        self.assertEqual(reason, "observed_period")
        self.assertGreaterEqual(comparisons, 1)
        self.assertTrue(local_ok)
        self.assertEqual(local_reason, "observed")

    def test_uniform_nonperiodic_motion_has_no_unique_small_lag(self) -> None:
        observations = {
            frame_index: tuple(
                _FrozenCycleObservation(
                    f"cycle-track-{track_index}",
                    PuzzleCandidate(
                        20.0 + track_index * 25.0 + frame_index * 0.5,
                        20.0,
                        0.8,
                        10.0,
                        10.0,
                    ),
                )
                for track_index in range(3)
            )
            for frame_index in range(5)
        }
        catalog = BackgroundCatalog()
        for frame_index, frame in observations.items():
            catalog.add_frame(
                frame_index,
                [observation.candidate for observation in frame],
            )

        period, _score, reason, _comparisons = _observed_episode_period(
            catalog,
            observations,
        )
        local_ok, local_reason = _local_lag_temporal_support(
            observations,
            frame_index=4,
            lag=2,
        )

        self.assertIsNone(period)
        self.assertEqual(reason, "period_recurrence_ambiguous")
        self.assertFalse(local_ok)
        self.assertEqual(local_reason, "nonunique_recurrence")

    def test_unique_small_lag_constant_translation_is_not_a_closed_loop(self) -> None:
        start_frame = 17
        velocity = (2.4, 1.8)
        origins = ((40.0, 30.0), (75.0, 30.0), (110.0, 30.0))
        observations = {
            frame_index: tuple(
                _FrozenCycleObservation(
                    f"cycle-track-{track_index}",
                    PuzzleCandidate(
                        origin[0] + velocity[0] * (frame_index - start_frame),
                        origin[1] + velocity[1] * (frame_index - start_frame),
                        0.8,
                        10.0,
                        10.0,
                    ),
                )
                for track_index, origin in enumerate(origins)
            )
            for frame_index in range(start_frame, start_frame + 6)
        }
        catalog = BackgroundCatalog()
        for frame_index, frame in observations.items():
            catalog.add_frame(
                frame_index,
                [observation.candidate for observation in frame],
            )

        period, _score, reason, _comparisons = _observed_episode_period(
            catalog,
            observations,
        )
        local_ok, local_reason = _local_lag_temporal_support(
            observations,
            frame_index=start_frame + 5,
            lag=2,
        )

        self.assertIsNone(period)
        self.assertEqual(reason, "period_loop_residual")
        self.assertFalse(local_ok)
        self.assertEqual(local_reason, "loop_residual")

    def test_large_constant_translation_is_not_a_closed_loop(self) -> None:
        start_frame = 31
        velocity = (1.8, -2.4)
        origins = ((40.0, 80.0), (80.0, 80.0), (120.0, 80.0))
        observations = {
            frame_index: tuple(
                _FrozenCycleObservation(
                    f"cycle-track-{track_index}",
                    PuzzleCandidate(
                        origin[0] + velocity[0] * (frame_index - start_frame),
                        origin[1] + velocity[1] * (frame_index - start_frame),
                        0.8,
                        24.0,
                        24.0,
                    ),
                )
                for track_index, origin in enumerate(origins)
            )
            for frame_index in range(start_frame, start_frame + 6)
        }
        catalog = BackgroundCatalog()
        for frame_index, frame in observations.items():
            catalog.add_frame(
                frame_index,
                [observation.candidate for observation in frame],
            )

        period, _score, reason, _comparisons = _observed_episode_period(
            catalog,
            observations,
        )
        local_ok, local_reason = _local_lag_temporal_support(
            observations,
            frame_index=start_frame + 5,
            lag=2,
        )

        self.assertIsNone(period)
        self.assertEqual(reason, "period_open_trajectory")
        self.assertFalse(local_ok)
        self.assertEqual(local_reason, "nonunique_recurrence")

    def test_global_assignment_keeps_unique_non_mutual_optimum(self) -> None:
        from core.puzzle import studio_hypothesis_shadow as shadow

        tracks = {
            track_id: shadow._StableCycleTrack(
                track_id=track_id,
                observations={0: _cycle_candidates(0, ((20.0, 20.0),))[0]},
            )
            for track_id in ("A", "B")
        }
        candidates = (
            Candidate("X", 1, (0.0, 0.0, 2.0, 2.0), (1.0, 1.0), 0.8, "test"),
            Candidate("Y", 1, (2.0, 0.0, 4.0, 2.0), (3.0, 1.0), 0.8, "test"),
        )
        costs = {
            ("A", "X"): 0.10,
            ("A", "Y"): 0.20,
            ("B", "X"): 0.11,
            ("B", "Y"): 1.40,
        }

        assignments, rejected, _blocked = shadow._global_track_assignment(
            tracks,
            candidates,
            lambda track, candidate: costs[(track.track_id, candidate.candidate_id)],
        )

        self.assertEqual(assignments, {"A": 1, "B": 0})
        self.assertEqual(rejected, {})

    def test_global_assignment_rejects_near_tied_alternative(self) -> None:
        from core.puzzle import studio_hypothesis_shadow as shadow

        tracks = {
            track_id: shadow._StableCycleTrack(
                track_id=track_id,
                observations={0: _cycle_candidates(0, ((20.0, 20.0),))[0]},
            )
            for track_id in ("A", "B")
        }
        candidates = (
            Candidate("X", 1, (0.0, 0.0, 2.0, 2.0), (1.0, 1.0), 0.8, "test"),
            Candidate("Y", 1, (2.0, 0.0, 4.0, 2.0), (3.0, 1.0), 0.8, "test"),
        )
        costs = {
            ("A", "X"): 0.10,
            ("A", "Y"): 0.11,
            ("B", "X"): 0.11,
            ("B", "Y"): 0.10,
        }

        assignments, rejected, blocked = shadow._global_track_assignment(
            tracks,
            candidates,
            lambda track, candidate: costs[(track.track_id, candidate.candidate_id)],
        )

        self.assertEqual(assignments, {})
        self.assertEqual(rejected, {"A": "association_ambiguous", "B": "association_ambiguous"})
        self.assertEqual(blocked, {0, 1})

    def test_new_white_episode_resets_unresolved_merge_state(self) -> None:
        with TemporaryDirectory(prefix="studio-white-reset-") as tmp:
            score_path, trace_path = _write_merge_lineage_replay(
                Path(tmp),
                white_frames={0, 6},
            )

            details = replay_hypothesis_selection_details(
                score_path,
                trace_path,
                merge_split_relative=True,
            )

            before_reset = details[5]["merge_split_relative"]
            after_reset = details[6]["merge_split_relative"]
            self.assertEqual(before_reset["state"], "SPLITTING")
            self.assertEqual(after_reset["state"], "SEPARATE")
            self.assertEqual(after_reset["merge_event_id"], 0)
            self.assertEqual(after_reset["fingerprint_pair_count"], 0)
            self.assertEqual(after_reset["selected_child_ids"], ())

    def test_new_white_episode_resets_beam_and_guard_timeline(self) -> None:
        with TemporaryDirectory(prefix="studio-full-timeline-reset-") as tmp:
            root = Path(tmp)
            full_score_path = root / "full-score.jsonl"
            fresh_score_path = root / "fresh-score.jsonl"
            full_trace_path = root / "full-trace.jsonl"
            fresh_trace_path = root / "fresh-trace.jsonl"
            _write_jsonl(
                full_score_path,
                [
                    {
                        "solver_frame_index": 11,
                        "target_x": 60.0,
                        "target_y": 50.0,
                    },
                    {
                        "solver_frame_index": 13,
                        "target_x": 20.0,
                        "target_y": 50.0,
                    },
                ],
            )
            _write_jsonl(
                fresh_score_path,
                [
                    {
                        "solver_frame_index": 13,
                        "target_x": 20.0,
                        "target_y": 50.0,
                    }
                ],
            )
            _write_jsonl(full_trace_path, _two_episode_reset_trace(include_history=True))
            _write_jsonl(fresh_trace_path, _two_episode_reset_trace(include_history=False))

            full = replay_hypothesis_selection_details(
                full_score_path,
                full_trace_path,
                width=3,
                branch=3,
                challenge_confirm_frames=2,
                challenge_max_step_px=500.0,
                persistent_evidence_quorum=True,
                merge_split_relative=True,
            )
            fresh = replay_hypothesis_selection_details(
                fresh_score_path,
                fresh_trace_path,
                width=3,
                branch=3,
                challenge_confirm_frames=2,
                challenge_max_step_px=500.0,
                persistent_evidence_quorum=True,
                merge_split_relative=True,
            )

            full_first = next(row for row in full if row["frame_index"] == 13)
            fresh_first = fresh[0]
            for key in (
                "replay_point",
                "replay_source",
                "replay_hypothesis_rank",
            ):
                with self.subTest(key=key):
                    self.assertEqual(full_first[key], fresh_first[key])
            self.assertEqual(
                full_first["challenge_guard"],
                fresh_first["challenge_guard"],
            )
            self.assertEqual(
                full_first["persistent_evidence_quorum"],
                fresh_first["persistent_evidence_quorum"],
            )

    def test_opt_out_scoreless_frame_does_not_advance_guard_confirmation(self) -> None:
        with TemporaryDirectory(prefix="studio-opt-out-scoreless-") as tmp:
            root = Path(tmp)
            score_path = root / "score.jsonl"
            trace_path = root / "trace.jsonl"
            _write_jsonl(
                score_path,
                [
                    {
                        "solver_frame_index": 2,
                        "target_x": 20.0,
                        "target_y": 50.0,
                    }
                ],
            )
            _write_jsonl(trace_path, _opt_out_scoreless_guard_trace())

            details = replay_hypothesis_selection_details(
                score_path,
                trace_path,
                width=2,
                branch=2,
                challenge_confirm_frames=2,
                persistent_evidence_quorum=True,
            )

            self.assertEqual(len(details), 1)
            row = details[0]
            self.assertEqual(row["frame_index"], 2)
            self.assertEqual(row["replay_point"], [20.0, 50.0])
            self.assertFalse(row["challenge_guard"]["selected"])
            self.assertEqual(row["challenge_guard"]["pending_frames"], 1)
            self.assertEqual(
                row["persistent_evidence_quorum"]["observation_count"],
                1,
            )


def _trace_candidate(
    candidate_id: str,
    center: tuple[float, float],
    *,
    half_size: float = 1.0,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "center": [center[0], center[1]],
        "bbox": [
            center[0] - half_size,
            center[1] - half_size,
            center[0] + half_size,
            center[1] + half_size,
        ],
        "score": 0.8,
        "source": "raw",
    }


def _white_anchor_events(frame_index: int, x: float) -> list[dict[str, object]]:
    return [
        {
            "type": "CANDIDATES",
            "frame_index": frame_index,
            "payload": {
                "candidates": [
                    _trace_candidate(
                        f"anchor-{frame_index}",
                        (x, 50.0),
                        half_size=5.0,
                    )
                ]
            },
        },
        {
            "type": "TEMPORAL_SELECTOR",
            "frame_index": frame_index,
            "payload": {
                "debug": {
                    "kinematic_wide_beam_debug": {
                        "reason": "white_anchor",
                        "point": [x, 50.0],
                    }
                }
            },
        },
    ]


def _challenger_frame_events(frame_index: int) -> list[dict[str, object]]:
    return [
        {
            "type": "CANDIDATES",
            "frame_index": frame_index,
            "payload": {
                "candidates": [
                    _trace_candidate(f"base-{frame_index}", (20.0, 50.0), half_size=5.0),
                    _trace_candidate(f"target-{frame_index}", (60.0, 50.0), half_size=5.0),
                ]
            },
        },
        {
            "type": "EVIDENCE",
            "frame_index": frame_index,
            "payload": {
                "evidence": [
                    {
                        "candidate_id": f"base-{frame_index}",
                        "texture_bg_score": 0.8,
                        "color_residual": 0.2,
                        "local_rigid_residual": 0.1,
                    },
                    {
                        "candidate_id": f"target-{frame_index}",
                        "texture_bg_score": 0.9,
                        "color_residual": 0.2,
                        "local_rigid_residual": 0.5,
                    },
                ]
            },
        },
        {
            "type": "IDENTITY_STATE",
            "frame_index": frame_index,
            "payload": {"state": "TRACK_CONFIDENT"},
        },
        {
            "type": "TEMPORAL_SELECTOR",
            "frame_index": frame_index,
            "payload": {
                "debug": {
                    "kinematic_wide_beam_debug": {"reason": "tracking"}
                }
            },
        },
        {
            "type": "TARGET_SELECTION",
            "frame_index": frame_index,
            "payload": {
                "point": [20.0, 50.0],
                "source": "kinematic_local_rigid",
                "kinematic_wide_beam_gate": {"base_point": [20.0, 50.0]},
            },
        },
    ]


def _two_episode_reset_trace(*, include_history: bool) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "type": "SESSION_START",
            "frame_index": None,
            "payload": {"board_roi": {"w": 400, "h": 100}},
        }
    ]
    if include_history:
        rows.extend(_white_anchor_events(0, -1400.0))
        for frame_index in range(1, 11):
            x = -1400.0 + 140.0 * frame_index
            rows.append(
                {
                    "type": "CANDIDATES",
                    "frame_index": frame_index,
                    "payload": {
                        "candidates": [
                            _trace_candidate(
                                f"velocity-{frame_index}",
                                (x, 50.0),
                                half_size=5.0,
                            )
                        ]
                    },
                }
            )
        rows.extend(_challenger_frame_events(11))
    rows.extend(_white_anchor_events(12, 20.0))
    rows.extend(_challenger_frame_events(13))
    return rows


def _opt_out_scoreless_guard_trace() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "type": "SESSION_START",
            "frame_index": None,
            "payload": {"board_roi": {"w": 120, "h": 100}},
        }
    ]
    rows.extend(_white_anchor_events(0, 20.0))
    rows.extend(_challenger_frame_events(1))
    rows.extend(_challenger_frame_events(2))
    return rows


def _cycle_candidates(
    frame_index: int,
    centers: tuple[tuple[float, float], ...],
) -> list[Candidate]:
    return [
        Candidate(
            candidate_id=f"cycle-{frame_index}-{candidate_index}",
            frame_index=frame_index,
            bbox=(center[0] - 10.0, center[1] - 10.0, center[0] + 10.0, center[1] + 10.0),
            center=center,
            score=0.8,
            source="raw",
        )
        for candidate_index, center in enumerate(centers)
    ]


def _wide_gate_trace(frame_shape: tuple[object, object]) -> list[dict[str, object]]:
    height, width = frame_shape
    return [
        {
            "type": "SESSION_START",
            "frame_index": None,
            "payload": {"board_roi": {"w": width, "h": height}},
        },
        {
            "type": "CANDIDATES",
            "frame_index": 0,
            "payload": {"candidates": [_trace_candidate("anchor", (20.0, 50.0), half_size=5.0)]},
        },
        {
            "type": "TEMPORAL_SELECTOR",
            "frame_index": 0,
            "payload": {"debug": {"kinematic_wide_beam_debug": {"reason": "white_anchor", "point": [20.0, 50.0]}}},
        },
        {
            "type": "CANDIDATES",
            "frame_index": 1,
            "payload": {
                "candidates": [
                    _trace_candidate("base", (20.0, 50.0), half_size=5.0),
                    _trace_candidate("target", (80.0, 50.0), half_size=5.0),
                ]
            },
        },
        {
            "type": "EVIDENCE",
            "frame_index": 1,
            "payload": {
                "evidence": [
                    {"candidate_id": "base", "texture_bg_score": 0.8, "color_residual": 0.2, "local_rigid_residual": 0.1},
                    {"candidate_id": "target", "texture_bg_score": 0.9, "color_residual": 0.2, "local_rigid_residual": 0.5},
                ]
            },
        },
        {"type": "IDENTITY_STATE", "frame_index": 1, "payload": {"state": "TRACK_CONFIDENT"}},
        {
            "type": "TEMPORAL_SELECTOR",
            "frame_index": 1,
            "payload": {"debug": {"kinematic_wide_beam_debug": {"reason": "tracking"}}},
        },
        {
            "type": "TARGET_SELECTION",
            "frame_index": 1,
            "payload": {"point": [20.0, 50.0], "source": "kinematic_local_rigid", "kinematic_wide_beam_gate": {"base_point": [20.0, 50.0]}},
        },
    ]


def _periodic_cycle_frames(
    *,
    total_frames: int,
    empty_frames: set[int] = set(),
) -> list[list[dict[str, object]]]:
    frames: list[list[dict[str, object]]] = []
    for frame_index in range(total_frames):
        if frame_index in empty_frames:
            frames.append([])
            continue
        phase = frame_index % 3
        rows = [
            _trace_candidate(f"anchor-a-{frame_index}", (20.0 + phase * 2.0, 20.0)),
            _trace_candidate(f"anchor-b-{frame_index}", (80.0 + phase * 2.0, 20.0)),
            _trace_candidate(f"background-{frame_index}", (48.0 + phase * 2.0, 50.0)),
            _trace_candidate(f"target-{frame_index}", (60.0, 50.0)),
        ]
        frames.append(rows[phase:] + rows[:phase])
    return frames


def _volatile_periodic_cycle_frames(
    *,
    total_frames: int,
    stable_count: int = 3,
    reorder_extras: bool = False,
    missing_stable_frame: int | None = None,
    clipped_stable_frame: int | None = None,
    crossing_frame: int | None = None,
    missing_post_episode_stable: bool = False,
) -> list[list[dict[str, object]]]:
    base_positions = ((20.0, 20.0), (80.0, 20.0), (48.0, 50.0))
    frames: list[list[dict[str, object]]] = []
    for frame_index in range(total_frames):
        phase = frame_index % 3
        stable_rows = [
            _trace_candidate(
                f"stable-{stable_index}-{frame_index}",
                (position[0] + phase * 2.0, position[1]),
            )
            for stable_index, position in enumerate(base_positions[:stable_count])
        ]
        if missing_stable_frame == frame_index or (
            missing_post_episode_stable and frame_index == total_frames - 1
        ):
            stable_rows.pop()
        if clipped_stable_frame == frame_index and stable_rows:
            stable_rows[0] = _trace_candidate(
                f"stable-clipped-{frame_index}",
                (1.0, 20.0),
            )
        if crossing_frame == frame_index and len(stable_rows) >= 2:
            stable_rows[1] = _trace_candidate(
                f"stable-crossing-{frame_index}",
                tuple(stable_rows[0]["center"]),
            )
        volatile_rows = [
            _trace_candidate(
                f"volatile-{frame_index}-{extra_index}",
                (110.0 + extra_index * 4.0, 10.0 + frame_index * 8.0),
            )
            for extra_index in range((frame_index % 5) + 1)
        ]
        if reorder_extras and frame_index % 2:
            volatile_rows.reverse()
        rows = stable_rows + volatile_rows + [
            _trace_candidate(f"target-{frame_index}", (60.0, 50.0))
        ]
        frames.append(rows[phase:] + rows[:phase])
    return frames


def _track_swap_cycle_frames(*, total_frames: int) -> list[list[dict[str, object]]]:
    frames = _periodic_cycle_frames(total_frames=total_frames)
    frames[0] = [
        _trace_candidate("swap-a-0", (20.0, 20.0), half_size=10.0),
        _trace_candidate("swap-b-0", (80.0, 20.0), half_size=10.0),
        _trace_candidate("swap-c-0", (50.0, 50.0), half_size=10.0),
        _trace_candidate("target-0", (60.0, 50.0)),
    ]
    frames[1] = [
        _trace_candidate("swap-a-1", (60.0, 20.0), half_size=10.0),
        _trace_candidate("swap-b-1", (40.0, 20.0), half_size=10.0),
        _trace_candidate("swap-c-1", (50.0, 50.0), half_size=10.0),
        _trace_candidate("target-1", (60.0, 50.0)),
    ]
    frames[2] = [
        _trace_candidate("swap-a-2", (60.0, 20.0), half_size=10.0),
        _trace_candidate("swap-b-2", (40.0, 20.0), half_size=10.0),
        _trace_candidate("swap-c-2", (52.0, 50.0), half_size=10.0),
        _trace_candidate("target-2", (60.0, 50.0)),
    ]
    return frames


def _same_assignment_crossing_cycle_frames(
    *,
    total_frames: int,
) -> list[list[dict[str, object]]]:
    frames = _periodic_cycle_frames(total_frames=total_frames)
    for frame_index, positions in enumerate(
        (
            ((150.0, 150.0), (190.0, 210.0)),
            ((160.0, 160.0), (180.0, 180.0)),
            ((175.0, 180.0), (155.0, 160.0)),
        )
    ):
        frames[frame_index] = [
            _trace_candidate(
                f"same-cross-a-{frame_index}",
                positions[0],
                half_size=60.0,
            ),
            _trace_candidate(
                f"same-cross-b-{frame_index}",
                positions[1],
                half_size=26.0,
            ),
            _trace_candidate(f"same-cross-c-{frame_index}", (320.0, 80.0)),
            _trace_candidate(f"target-{frame_index}", (60.0, 50.0)),
        ]
    return frames


def _initial_actual_crossing_cycle_frames(
    *,
    total_frames: int,
) -> list[list[dict[str, object]]]:
    frames = _periodic_cycle_frames(total_frames=total_frames)
    for frame_index, positions in enumerate(
        (
            ((160.0, 160.0), (180.0, 180.0)),
            ((180.0, 180.0), (160.0, 160.0)),
        )
    ):
        frames[frame_index] = [
            _trace_candidate(
                f"initial-cross-a-{frame_index}",
                positions[0],
                half_size=60.0,
            ),
            _trace_candidate(
                f"initial-cross-b-{frame_index}",
                positions[1],
                half_size=20.0,
            ),
            _trace_candidate(f"initial-cross-c-{frame_index}", (320.0, 80.0)),
            _trace_candidate(f"target-{frame_index}", (60.0, 50.0)),
        ]
    return frames


def _predicted_rejection_cycle_frames(*, total_frames: int) -> list[list[dict[str, object]]]:
    frames = _periodic_cycle_frames(total_frames=total_frames)
    frames[1] = [
        _trace_candidate("pred-a-1", (30.0, 20.0), half_size=10.0),
        _trace_candidate("pred-b-1", (80.0, 20.0), half_size=10.0),
        _trace_candidate("pred-c-1", (48.0, 50.0), half_size=10.0),
        _trace_candidate("target-1", (60.0, 50.0)),
    ]
    frames[2] = [
        _trace_candidate("pred-a-near-2", (30.0, 20.0), half_size=10.0),
        _trace_candidate("pred-a-tied-2", (50.0, 20.0), half_size=10.0),
        _trace_candidate("pred-b-2", (80.0, 20.0), half_size=10.0),
        _trace_candidate("pred-c-2", (48.0, 50.0), half_size=10.0),
        _trace_candidate("target-2", (60.0, 50.0)),
    ]
    return frames


def _long_ambiguous_candidate_cycle_frames(
    *,
    total_frames: int,
) -> list[list[dict[str, object]]]:
    frames = _periodic_cycle_frames(total_frames=total_frames)
    phase = 1
    stable = [
        (20.0 + phase * 2.0, 20.0),
        (80.0 + phase * 2.0, 20.0),
        (48.0 + phase * 2.0, 50.0),
    ]
    frames[1] = [
        _trace_candidate(f"ambiguous-{index}-a", point)
        for index, point in enumerate(stable)
    ] + [
        _trace_candidate(f"ambiguous-{index}-b", point)
        for index, point in enumerate(stable)
    ] + [_trace_candidate("target-1", (60.0, 50.0))]
    return frames


def _long_duplicate_candidate_cycle_frames(
    *,
    total_frames: int,
) -> list[list[dict[str, object]]]:
    frames = [
        [
            _trace_candidate("duplicate-a-0", (80.0, 20.0), half_size=10.0),
            _trace_candidate("duplicate-b-0", (104.0, 20.0), half_size=10.0),
            _trace_candidate("duplicate-c-0", (150.0, 20.0), half_size=10.0),
            _trace_candidate("target-0", (60.0, 50.0)),
        ]
    ]
    for frame_index in range(1, total_frames):
        frames.append(
            [
                _trace_candidate(f"duplicate-shared-{frame_index}", (86.0, 20.0), half_size=10.0),
                _trace_candidate(f"duplicate-extra-{frame_index}", (60.0, 20.0), half_size=10.0),
                _trace_candidate(f"duplicate-c-{frame_index}", (150.0, 20.0), half_size=10.0),
                _trace_candidate(f"target-{frame_index}", (60.0, 50.0)),
            ]
        )
    return frames


def _long_reverse_only_candidate_cycle_frames(
    *,
    total_frames: int,
) -> list[list[dict[str, object]]]:
    frames = [
        [
            _trace_candidate("reverse-a-0", (80.0, 20.0), half_size=10.0),
            _trace_candidate("reverse-b-0", (160.0, 20.0), half_size=10.0),
            _trace_candidate("reverse-c-0", (230.0, 20.0), half_size=10.0),
            _trace_candidate("target-0", (60.0, 50.0)),
        ]
    ]
    for frame_index in range(1, total_frames):
        frames.append(
            [
                _trace_candidate(f"reverse-near-{frame_index}", (80.0, 20.0), half_size=10.0),
                _trace_candidate(f"reverse-only-{frame_index}", (90.0, 20.0), half_size=10.0),
                _trace_candidate(f"reverse-b-{frame_index}", (160.0, 20.0), half_size=10.0),
                _trace_candidate(f"reverse-c-{frame_index}", (230.0, 20.0), half_size=10.0),
                _trace_candidate(f"target-{frame_index}", (60.0, 50.0)),
            ]
        )
    return frames


def _temporal_chain_candidates(
    frame_index: int,
    positions: tuple[float, float],
    *,
    include_anchor: bool,
    reverse: bool = False,
) -> list[dict[str, object]]:
    rows = [
        _trace_candidate(
            f"chain-{frame_index}-{index}",
            (position, 20.0),
            half_size=8.0,
        )
        for index, position in enumerate(positions)
    ]
    if include_anchor:
        rows.append(
            _trace_candidate(
                f"anchor-{frame_index}",
                (60.0, 50.0),
                half_size=8.0,
            )
        )
    return list(reversed(rows)) if reverse else rows


def _sparse_cycle_chain_frames(
    occurrences: tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]],
    *,
    half_size: float,
) -> list[list[dict[str, object]]]:
    frames = [
        [_trace_candidate(f"target-{frame_index}", (60.0, 50.0))]
        for frame_index in range(8)
    ]
    for frame_index, positions in zip((0, 3, 6), occurrences):
        frames[frame_index] = [
            _trace_candidate(
                f"background-{frame_index}-{index}",
                (position, 20.0),
                half_size=half_size,
            )
            for index, position in enumerate(positions)
        ] + [_trace_candidate(f"target-{frame_index}", (60.0, 50.0))]
    return frames


def _replay_cycle_details(
    root: Path,
    frames: list[list[dict[str, object]]],
    *,
    white_frames: set[int],
    omit_candidate_frames: set[int] = set(),
    include_frame_shape: bool = True,
    frame_shape: tuple[object, object] = (100, 140),
) -> list[dict[str, object]]:
    score_path = root / "score.jsonl"
    trace_path = root / "trace.jsonl"
    scores = [
        {"solver_frame_index": frame_index, "target_x": 60.0, "target_y": 50.0}
        for frame_index in range(len(frames))
    ]
    trace: list[dict[str, object]] = []
    if include_frame_shape:
        trace.append(
            {
                "type": "SESSION_START",
                "frame_index": None,
                "payload": {"board_roi": {"w": frame_shape[1], "h": frame_shape[0]}},
            }
        )
    for frame_index, candidates in enumerate(frames):
        trace.extend(
            [
                {
                    "type": "TEMPORAL_SELECTOR",
                    "frame_index": frame_index,
                    "payload": {
                        "debug": {
                            "kinematic_wide_beam_debug": {
                                "reason": (
                                    "white_anchor"
                                    if frame_index in white_frames
                                    else "tracking"
                                ),
                                "point": [60.0, 50.0],
                            }
                        }
                    },
                },
                {
                    "type": "TARGET_SELECTION",
                    "frame_index": frame_index,
                    "payload": {"point": [60.0, 50.0], "source": "recorded"},
                },
            ]
        )
        if frame_index not in omit_candidate_frames:
            trace.append(
                {
                    "type": "CANDIDATES",
                    "frame_index": frame_index,
                    "payload": {"candidates": candidates},
                }
            )
    _write_jsonl(score_path, scores)
    _write_jsonl(trace_path, trace)
    return replay_hypothesis_selection_details(
        score_path,
        trace_path,
        merge_split_relative=True,
    )


def _write_merge_lineage_replay(
    root: Path,
    *,
    omitted_score_frames: set[int] = set(),
    white_frames: set[int] = {0},
) -> tuple[Path, Path]:
    score_path = root / "score.jsonl"
    trace_path = root / "trace.jsonl"
    frame_rows = (
        ((34.0, 32.0), (30.0, 28.0), "target"),
        ((34.0, 32.0), (30.0, 28.0), "target"),
        ((34.0, 32.0), (30.0, 28.0), "target"),
        ((31.0, 29.0), (30.0, 28.0), "overlap-target"),
        ((31.0, 29.0), (30.0, 28.0), "overlap-target"),
        ((33.0, 31.0), (30.0, 28.0), "target-child"),
        ((33.0, 31.0), (30.0, 28.0), "target-child"),
        ((33.0, 31.0), (30.0, 28.0), "target-child"),
        ((33.0, 31.0), (30.0, 28.0), "target-child"),
    )
    scores: list[dict[str, object]] = []
    trace: list[dict[str, object]] = [
        {
            "type": "SESSION_START",
            "frame_index": None,
            "payload": {"board_roi": {"w": 100, "h": 100}},
        }
    ]
    for frame_index, (target, background, target_id) in enumerate(frame_rows):
        if frame_index not in omitted_score_frames:
            scores.append(
                {
                    "solver_frame_index": frame_index,
                    "target_x": target[0],
                    "target_y": target[1],
                }
            )
        candidates = [
            _trace_candidate(target_id, target),
            _trace_candidate(
                "background-child" if frame_index >= 5 else "background",
                background,
            ),
            _trace_candidate("anchor-a", (20.0, 20.0)),
            _trace_candidate("anchor-b", (40.0, 20.0)),
        ]
        trace.extend(
            [
                {
                    "type": "CANDIDATES",
                    "frame_index": frame_index,
                    "payload": {"candidates": candidates},
                },
                {
                    "type": "TEMPORAL_SELECTOR",
                    "frame_index": frame_index,
                    "payload": {
                        "debug": {
                            "kinematic_wide_beam_debug": {
                                "reason": (
                                    "white_anchor"
                                    if frame_index in white_frames
                                    else "tracking"
                                ),
                                "point": [target[0], target[1]],
                            }
                        }
                    },
                },
                {
                    "type": "IDENTITY_STATE",
                    "frame_index": frame_index,
                    "payload": {"state": "TRACK_CONFIDENT"},
                },
                {
                    "type": "EVIDENCE",
                    "frame_index": frame_index,
                    "payload": {
                        "evidence": [
                            {
                                "candidate_id": candidate["candidate_id"],
                                "bg_score": (
                                    0.1
                                    if candidate["candidate_id"] == target_id
                                    else 0.8
                                ),
                                "motion_divergence": (
                                    0.9
                                    if candidate["candidate_id"] == target_id
                                    else 0.1
                                ),
                            }
                            for candidate in candidates
                        ]
                    },
                },
                {
                    "type": "TARGET_SELECTION",
                    "frame_index": frame_index,
                    "payload": {
                        "point": (
                            [background[0], background[1]]
                            if frame_index >= 5
                            else [target[0], target[1]]
                        ),
                        "source": "recorded",
                    },
                },
            ]
        )
    _write_jsonl(score_path, scores)
    _write_jsonl(trace_path, trace)
    return score_path, trace_path


if __name__ == "__main__":
    unittest.main()
