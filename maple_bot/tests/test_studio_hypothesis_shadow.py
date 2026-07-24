# Studio trace로 시간축 가설 보관 전략을 재생 비교하는 도구를 검증합니다.
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.puzzle.hypothesis_challenge import HypothesisChallengeGuard
from core.puzzle.models import Candidate
from core.puzzle.studio_hypothesis_shadow import (
    _stable_target_area,
    replay_hypothesis_selection,
    replay_hypothesis_selection_details,
    replay_hypothesis_tracker,
)


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
                    _trace_candidate(f"target-{frame_index}", target),
                ]
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
                "insufficient_local_lag_evidence",
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

            diagnostic = details[14]["merge_split_relative"]
            self.assertIsNone(diagnostic["period"])
            self.assertFalse(diagnostic["phase_qualified"])
            self.assertEqual(
                diagnostic["cycle_evidence_reason"],
                "inactive_prior_period_insufficient_episode_evidence",
            )
            self.assertIsNone(diagnostic["local_lag"])
            self.assertEqual(
                diagnostic["local_lag_evidence_reason"],
                "insufficient_episode_evidence",
            )
            self.assertIn(
                diagnostic["qualified_anchor_count"],
                {0, None},
            )

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
) -> list[dict[str, object]]:
    score_path = root / "score.jsonl"
    trace_path = root / "trace.jsonl"
    scores = [
        {"solver_frame_index": frame_index, "target_x": 60.0, "target_y": 50.0}
        for frame_index in range(len(frames))
    ]
    trace: list[dict[str, object]] = [
        {
            "type": "SESSION_START",
            "frame_index": None,
            "payload": {"board_roi": {"w": 140, "h": 100}},
        }
    ]
    for frame_index, candidates in enumerate(frames):
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
    return replay_hypothesis_selection_details(
        score_path,
        trace_path,
        merge_split_relative=True,
    )


if __name__ == "__main__":
    unittest.main()
