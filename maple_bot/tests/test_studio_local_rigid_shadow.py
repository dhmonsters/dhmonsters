# Studio trace에서 독립 강체 신호의 선택 효과를 검증합니다.
from __future__ import annotations

import json
from pathlib import Path

from core.puzzle.studio_local_rigid_shadow import (
    LocalRigidGateConfig,
    score_local_rigid_shadow,
    sweep_local_rigid_shadow,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_local_rigid_shadow_recovers_a_retained_hypothesis_without_gt_input(tmp_path: Path) -> None:
    gt_path = tmp_path / "studio_gt.jsonl"
    trace_path = tmp_path / "trace.jsonl"
    _write_jsonl(
        gt_path,
        [{
            "run_id": "run-1",
            "run_index": 0,
            "frame_id": 0,
            "solver_frame_index": 7,
            "target_x": 100,
            "target_y": 20,
        }],
    )
    _write_jsonl(
        trace_path,
        [
            {
                "type": "CANDIDATES",
                "frame_index": 7,
                "payload": {
                    "candidates": [
                        {
                            "candidate_id": "base",
                            "bbox": [0, 10, 20, 30],
                            "center": [10, 20],
                            "score": 0.8,
                            "source": "raw",
                        },
                        {
                            "candidate_id": "target",
                            "bbox": [90, 10, 110, 30],
                            "center": [100, 20],
                            "score": 0.5,
                            "source": "raw",
                        },
                    ]
                },
            },
            {
                "type": "EVIDENCE",
                "frame_index": 7,
                "payload": {
                    "evidence": [
                        {"candidate_id": "base", "local_rigid_residual": 0.10},
                        {"candidate_id": "target", "local_rigid_residual": 0.35},
                    ]
                },
            },
            {
                "type": "TEMPORAL_SELECTOR",
                "frame_index": 7,
                "payload": {
                    "debug": {"kinematic_wide_beam_points": [[10, 20], [100, 20]]}
                },
            },
            {
                "type": "TARGET_SELECTION",
                "frame_index": 7,
                "payload": {
                    "point": [10, 20],
                    "source": "identity",
                    "identity_state": "TRACK_CONFIDENT",
                },
            },
        ],
    )

    result = score_local_rigid_shadow(
        gt_path,
        trace_path,
        LocalRigidGateConfig(
            min_residual=0.20,
            min_advantage=0.10,
            min_shift_px=40.0,
        ),
    )

    assert result.total_frames == 1
    assert result.base_passed_frames == 0
    assert result.shadow_passed_frames == 1
    assert result.improved_frames == 1
    assert result.regressed_frames == 0
    assert result.frames[0].selected is True
    assert result.frames[0].selected_candidate_id == "target"


def test_local_rigid_sweep_compares_configs_on_one_loaded_session(tmp_path: Path) -> None:
    gt_path = tmp_path / "studio_gt.jsonl"
    trace_path = tmp_path / "trace.jsonl"
    _write_jsonl(
        gt_path,
        [{
            "run_id": "run-1",
            "run_index": 0,
            "frame_id": 0,
            "solver_frame_index": 7,
            "target_x": 100,
            "target_y": 20,
        }],
    )
    _write_jsonl(
        trace_path,
        [
            {
                "type": "CANDIDATES",
                "frame_index": 7,
                "payload": {"candidates": [
                    {"candidate_id": "base", "center": [10, 20]},
                    {"candidate_id": "target", "center": [100, 20]},
                ]},
            },
            {
                "type": "EVIDENCE",
                "frame_index": 7,
                "payload": {"evidence": [
                    {"candidate_id": "base", "local_rigid_residual": 0.10},
                    {"candidate_id": "target", "local_rigid_residual": 0.35},
                ]},
            },
            {
                "type": "TEMPORAL_SELECTOR",
                "frame_index": 7,
                "payload": {"debug": {"kinematic_wide_beam_points": [[10, 20], [100, 20]]}},
            },
            {
                "type": "TARGET_SELECTION",
                "frame_index": 7,
                "payload": {"point": [10, 20], "source": "identity"},
            },
        ],
    )
    permissive = LocalRigidGateConfig(0.20, 0.10, 40.0)
    strict = LocalRigidGateConfig(0.40, 0.10, 40.0)

    rows = sweep_local_rigid_shadow([(gt_path, trace_path)], [permissive, strict])

    assert [row.shadow_passed_frames for row in rows] == [1, 0]
    assert [row.delta_frames for row in rows] == [1, 0]
    assert [row.regressed_runs for row in rows] == [0, 0]


def test_local_rigid_shadow_does_not_treat_unavailable_zero_as_background_evidence(tmp_path: Path) -> None:
    gt_path = tmp_path / "studio_gt.jsonl"
    trace_path = tmp_path / "trace.jsonl"
    _write_jsonl(
        gt_path,
        [{
            "run_id": "run-1",
            "run_index": 0,
            "frame_id": 0,
            "solver_frame_index": 7,
            "target_x": 10,
            "target_y": 20,
        }],
    )
    _write_jsonl(
        trace_path,
        [
            {
                "type": "CANDIDATES",
                "frame_index": 7,
                "payload": {"candidates": [
                    {"candidate_id": "base", "center": [10, 20]},
                    {"candidate_id": "other", "center": [100, 20]},
                ]},
            },
            {
                "type": "EVIDENCE",
                "frame_index": 7,
                "payload": {"evidence": [
                    {"candidate_id": "base", "local_rigid_residual": 0.0},
                    {"candidate_id": "other", "local_rigid_residual": 0.35},
                ]},
            },
            {
                "type": "TEMPORAL_SELECTOR",
                "frame_index": 7,
                "payload": {"debug": {"kinematic_wide_beam_points": [[10, 20], [100, 20]]}},
            },
            {
                "type": "TARGET_SELECTION",
                "frame_index": 7,
                "payload": {"point": [10, 20], "source": "identity"},
            },
        ],
    )

    result = score_local_rigid_shadow(
        gt_path,
        trace_path,
        LocalRigidGateConfig(0.20, 0.10, 40.0),
    )

    assert result.shadow_passed_frames == 1
    assert result.regressed_frames == 0
    assert result.frames[0].selected is False
    assert result.frames[0].reason == "base_residual_unavailable"
