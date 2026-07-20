# Studio trace로 시간축 가설 보관 전략을 재생 비교하는 도구를 검증합니다.
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.puzzle.hypothesis_challenge import HypothesisChallengeGuard
from core.puzzle.studio_hypothesis_shadow import (
    replay_hypothesis_selection,
    replay_hypothesis_selection_details,
    replay_hypothesis_tracker,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


class StudioHypothesisShadowTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
