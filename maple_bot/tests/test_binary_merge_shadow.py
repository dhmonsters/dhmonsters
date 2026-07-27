# 런타임 추적 기반 이진 병합 사건 추출과 자식 증거 계산을 검증합니다.
from __future__ import annotations

import json
import math
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

import core.puzzle.binary_merge_shadow as binary_merge_shadow
from core.puzzle.binary_merge_background import BackgroundFlowProfile
from core.puzzle.binary_merge_identity import BinaryMergeIdentityResolver, BinaryTransferStatus
from core.puzzle.binary_merge_shadow import (
    BinaryEventOutcome,
    BinaryEventReplay,
    BinaryEventScore,
    BinaryMergeEventWindow,
    BinaryPremergeSnapshot,
    BackgroundRelationSnapshot,
    build_child_evidence,
    collapse_physical_candidates,
    extract_binary_merge_events,
    _board_frame_shape,
    render_binary_merge_event_markdown,
    replay_binary_merge_events,
    score_binary_merge_events,
    summarize_binary_merge_events,
)
from core.puzzle.models import Candidate


FRAME_SHAPE = (200, 400)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _session_start_row(*, height: int, width: int) -> dict[str, object]:
    return {
        "type": "SESSION_START",
        "frame_index": None,
        "payload": {
            "source_kind": "live_screen",
            "fps": 10.0,
            "mouse_enabled": False,
            "target_visual_check": True,
            "mouse_output_forced_off": True,
            "video_recording_enabled": False,
            "board_roi": {
                "name": "board",
                "basis": "window_client",
                "x": 120,
                "y": 80,
                "w": width,
                "h": height,
                "x_ratio": 0.1,
                "y_ratio": 0.1,
                "w_ratio": 0.6,
                "h_ratio": 0.7,
                "dpi_scale": 1.0,
                "window_title": "MapleStory",
            },
        },
    }


def _candidate(
    candidate_id: str,
    frame_index: int,
    center_ratio: tuple[float, float],
    *,
    half_ratio: float = 0.035,
    score: float = 0.8,
) -> dict[str, object]:
    height, width = FRAME_SHAPE
    center = (center_ratio[0] * width, center_ratio[1] * height)
    half_width = half_ratio * width
    half_height = half_ratio * height
    return {
        "candidate_id": candidate_id,
        "center": list(center),
        "bbox": [
            center[0] - half_width,
            center[1] - half_height,
            center[0] + half_width,
            center[1] + half_height,
        ],
        "score": score,
        "source": "runtime",
    }


def _rows_for_frame(
    frame_index: int,
    candidates: list[dict[str, object]],
    target_point_ratio: tuple[float, float],
    *,
    identity_state: str = "TRACK_CONFIDENT",
) -> list[dict[str, object]]:
    height, width = FRAME_SHAPE
    return [
        {
            "type": "CANDIDATES",
            "frame_index": frame_index,
            "payload": {"candidates": candidates, "frame_shape": list(FRAME_SHAPE)},
        },
        {
            "type": "IDENTITY_STATE",
            "frame_index": frame_index,
            "payload": {"state": identity_state},
        },
        {
            "type": "TARGET_SELECTION",
            "frame_index": frame_index,
            "payload": {"point": [target_point_ratio[0] * width, target_point_ratio[1] * height]},
        },
    ]


def _white_anchor_row(
    frame_index: int,
    point_ratio: tuple[float, float],
) -> dict[str, object]:
    height, width = FRAME_SHAPE
    return {
        "type": "TEMPORAL_SELECTOR",
        "frame_index": frame_index,
        "payload": {
            "debug": {
                "kinematic_wide_beam_debug": {
                    "reason": "white_anchor",
                    "point": [point_ratio[0] * width, point_ratio[1] * height],
                }
            }
        },
    }


def _board_distractors(frame_index: int) -> list[dict[str, object]]:
    return [
        _candidate(
            f"board_distractor_{frame_index}_{index}",
            frame_index,
            (0.05 + 0.06 * (index % 14), 0.10 if index < 14 else 0.90),
        )
        for index in range(28)
    ]


def _preparation_rows(
    frame_indices: tuple[int, ...] = (0, 1, 2),
    *,
    target_start: float = 0.50,
    target_step: float = 0.02,
    background_step: float = 0.01,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    first_frame = frame_indices[0]
    for frame_index in frame_indices:
        elapsed = frame_index - first_frame
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"prep_target_{frame_index}", frame_index, (target_start + target_step * elapsed, 0.50)),
                _candidate(f"prep_background_a_{frame_index}", frame_index, (0.10 + background_step * elapsed, 0.20)),
                _candidate(f"prep_background_b_{frame_index}", frame_index, (0.30 + background_step * elapsed, 0.40)),
                _candidate(f"prep_background_c_{frame_index}", frame_index, (0.70 + background_step * elapsed, 0.60)),
            ],
            (target_start + target_step * elapsed, 0.50),
        )
    return rows


def _shift_frame_indices(rows: list[dict[str, object]], offset: int) -> list[dict[str, object]]:
    shifted = json.loads(json.dumps(rows))
    for row in shifted:
        frame_index = row.get("frame_index")
        if isinstance(frame_index, int):
            row["frame_index"] = frame_index + offset
    return shifted


def make_trace_rows_for_separate_overlap_merged_split(
    *,
    parent_center_ratio: tuple[float, float] = (0.50, 0.50),
    first_split_ambiguous: bool = False,
    identity_state: str = "TRACK_CONFIDENT",
) -> list[dict[str, object]]:
    rows = _preparation_rows(
        (-2, -1),
        target_start=0.42,
        target_step=0.0,
        background_step=0.0,
    )
    rows += _rows_for_frame(
        0,
        [
            _candidate("target_before", 0, (0.42, 0.50)),
            _candidate("background_before", 0, (0.58, 0.50)),
            _candidate("anchor_before", 0, (0.24, 0.30)),
        ],
        (0.42, 0.50),
        identity_state=identity_state,
    )
    rows += _rows_for_frame(
        1,
        [
            _candidate("target_overlap", 1, (0.455, 0.50), half_ratio=0.06),
            _candidate("background_overlap", 1, (0.545, 0.50), half_ratio=0.06),
            _candidate("anchor_overlap", 1, (0.24, 0.30)),
        ],
        (0.455, 0.50),
    )
    rows += _rows_for_frame(
        2,
        [
            _candidate("merge_parent", 2, parent_center_ratio, half_ratio=0.13),
            _candidate("anchor_merge", 2, (0.24, 0.30)),
        ],
        parent_center_ratio,
    )
    if first_split_ambiguous:
        rows += _rows_for_frame(
            3,
            [
                _candidate("target_candidate_early", 3, (0.42, 0.50), score=0.9),
                _candidate("extra_candidate_early", 3, (0.49, 0.50), score=0.7),
                _candidate("background_child_early", 3, (0.58, 0.50)),
                _candidate("outside", 3, (0.88, 0.10)),
            ],
            (0.42, 0.50),
        )
    rows += _rows_for_frame(
        4,
        [
            _candidate("target_child", 4, (0.42, 0.50)),
            _candidate("background_child", 4, (0.58, 0.50)),
            _candidate("anchor_child", 4, (0.24, 0.30)),
        ],
        (0.42, 0.50),
    )
    return rows


def _runtime_candidate(
    candidate_id: str,
    frame_index: int,
    center: tuple[float, float],
    *,
    half_size: float = 10.0,
    score: float = 0.8,
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        frame_index=frame_index,
        center=center,
        bbox=(center[0] - half_size, center[1] - half_size, center[0] + half_size, center[1] + half_size),
        score=score,
        source="runtime",
    )


def _event(*, parent_bbox: tuple[float, float, float, float] = (85.0, 45.0, 140.0, 75.0)) -> BinaryMergeEventWindow:
    return BinaryMergeEventWindow(
        event_id=7,
        premerge=BinaryPremergeSnapshot(
            frame_index=0,
            target_candidate_id="target_before",
            background_candidate_id="background_before",
            target_center=(100.0, 60.0),
            background_center=(120.0, 60.0),
            target_bbox=(90.0, 50.0, 110.0, 70.0),
            background_bbox=(110.0, 50.0, 130.0, 70.0),
            target_velocity=(0.0, 5.0),
            background_velocity=(0.0, 0.0),
            neighbor_relations=(
                BackgroundRelationSnapshot(
                    "anchor_before",
                    (40.0, 30.0),
                    (-80.0 / math.hypot(20.0, 20.0), -30.0 / math.hypot(20.0, 20.0)),
                ),
            ),
        ),
        merge_frame_indices=(1, 2),
        split_frame_indices=(1,),
        parent_bboxes=(parent_bbox,),
        split_observations=(),
        reason="children_separated",
    )


def test_binary_event_partial_merge_split_becomes_one_binary_event() -> None:
    extraction = extract_binary_merge_events(make_trace_rows_for_separate_overlap_merged_split())

    assert len(extraction.events) == 1
    assert extraction.events[0].premerge.target_candidate_id == "target_before"
    assert extraction.events[0].premerge.background_candidate_id == "background_before"
    assert len(extraction.events[0].split_observations) >= 1
    assert len(extraction.events[0].split_observations[0].children) == 2


def test_binary_event_expanded_parent_then_children_returns_one_event() -> None:
    extraction = extract_binary_merge_events(make_trace_rows_for_separate_overlap_merged_split())

    assert extraction.events[0].merge_frame_indices == (2,)
    assert extraction.events[0].parent_bboxes


def test_binary_event_untrusted_premerge_is_diagnostic_not_event() -> None:
    extraction = extract_binary_merge_events(
        make_trace_rows_for_separate_overlap_merged_split(identity_state="IDENTITY_HOLD")
    )

    assert not extraction.events
    assert any(row.reason == "premerge_identity_untrusted" for row in extraction.diagnostics)


def test_visible_white_contact_with_board_distractors_is_not_event_or_diagnostic() -> None:
    rows: list[dict[str, object]] = []
    rows += _rows_for_frame(
        0,
        [
            _candidate("visible_target_0", 0, (0.42, 0.50)),
            _candidate("visible_background_0", 0, (0.58, 0.50)),
            *_board_distractors(0),
        ],
        (0.42, 0.50),
        identity_state="UNKNOWN",
    )
    rows.append(_white_anchor_row(0, (0.42, 0.50)))
    for frame_index in (1, 2):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"visible_target_{frame_index}", frame_index, (0.455, 0.50), half_ratio=0.06),
                _candidate(f"visible_background_{frame_index}", frame_index, (0.545, 0.50), half_ratio=0.06),
                *_board_distractors(frame_index),
            ],
            (0.455, 0.50),
            identity_state="UNKNOWN",
        )
        rows.append(_white_anchor_row(frame_index, (0.455, 0.50)))

    extraction = extract_binary_merge_events(rows)

    assert not extraction.events
    assert not extraction.diagnostics


def test_identity_risk_after_visible_contact_uses_last_visible_contact_snapshot() -> None:
    rows: list[dict[str, object]] = []
    rows += _rows_for_frame(
        0,
        [
            _candidate("visible_target_0", 0, (0.42, 0.50)),
            _candidate("visible_background_0", 0, (0.58, 0.50)),
        ],
        (0.42, 0.50),
        identity_state="UNKNOWN",
    )
    rows.append(_white_anchor_row(0, (0.42, 0.50)))
    for frame_index in (1, 2):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"visible_target_{frame_index}", frame_index, (0.455, 0.50), half_ratio=0.06),
                _candidate(f"visible_background_{frame_index}", frame_index, (0.545, 0.50), half_ratio=0.06),
            ],
            (0.455, 0.50),
            identity_state="UNKNOWN",
        )
        rows.append(_white_anchor_row(frame_index, (0.455, 0.50)))
    for frame_index in (3, 4):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"risk_target_{frame_index}", frame_index, (0.455, 0.50), half_ratio=0.06),
                _candidate(f"risk_background_{frame_index}", frame_index, (0.545, 0.50), half_ratio=0.06),
            ],
            (0.455, 0.50),
            identity_state="IDENTITY_HOLD",
        )
    rows += _rows_for_frame(
        5,
        [
            _candidate("risk_target_child", 5, (0.42, 0.50)),
            _candidate("risk_background_child", 5, (0.58, 0.50)),
        ],
        (0.42, 0.50),
        identity_state="IDENTITY_HOLD",
    )

    extraction = extract_binary_merge_events(rows)

    assert len(extraction.events) == 1
    assert not extraction.diagnostics
    assert extraction.events[0].premerge.frame_index == 2
    assert extraction.events[0].premerge.target_candidate_id == "visible_target_2"
    assert extraction.events[0].premerge.background_candidate_id == "visible_background_2"


def test_open_identity_risk_event_collects_visible_separated_children() -> None:
    rows: list[dict[str, object]] = []
    rows += _rows_for_frame(
        0,
        [
            _candidate("visible_target_0", 0, (0.42, 0.50)),
            _candidate("visible_background_0", 0, (0.58, 0.50)),
        ],
        (0.42, 0.50),
        identity_state="UNKNOWN",
    )
    rows.append(_white_anchor_row(0, (0.42, 0.50)))
    rows += _rows_for_frame(
        1,
        [
            _candidate("visible_target_1", 1, (0.455, 0.50), half_ratio=0.06),
            _candidate("visible_background_1", 1, (0.545, 0.50), half_ratio=0.06),
        ],
        (0.455, 0.50),
        identity_state="UNKNOWN",
    )
    rows.append(_white_anchor_row(1, (0.455, 0.50)))
    for frame_index in (2, 3):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"risk_target_{frame_index}", frame_index, (0.455, 0.50), half_ratio=0.06),
                _candidate(f"risk_background_{frame_index}", frame_index, (0.545, 0.50), half_ratio=0.06),
            ],
            (0.455, 0.50),
            identity_state="IDENTITY_HOLD",
        )
    rows += _rows_for_frame(
        4,
        [
            _candidate("visible_target_child", 4, (0.42, 0.50)),
            _candidate("visible_background_child", 4, (0.58, 0.50)),
        ],
        (0.42, 0.50),
        identity_state="UNKNOWN",
    )
    rows.append(_white_anchor_row(4, (0.42, 0.50)))

    extraction = extract_binary_merge_events(rows)

    assert len(extraction.events) == 1
    assert not extraction.diagnostics
    assert tuple(row.frame_index for row in extraction.events[0].split_observations) == (4,)


def _two_pair_split_rows() -> list[dict[str, object]]:
    rows = make_trace_rows_for_separate_overlap_merged_split(first_split_ambiguous=True)
    for row in rows:
        if row["type"] == "CANDIDATES" and row["frame_index"] in (-2, -1):
            row["payload"]["candidates"][0]["bbox"] = [148.0, 90.0, 188.0, 110.0]
        if row["type"] == "CANDIDATES" and row["frame_index"] == 0:
            row["payload"]["candidates"][0]["bbox"] = [148.0, 90.0, 188.0, 110.0]
            row["payload"]["candidates"][1]["bbox"] = [212.0, 90.0, 252.0, 110.0]
        if row["type"] == "CANDIDATES" and row["frame_index"] == 1:
            row["payload"]["candidates"][0]["bbox"] = [185.0, 50.0, 205.0, 150.0]
            row["payload"]["candidates"][1]["bbox"] = [200.0, 50.0, 215.0, 150.0]
        if row["type"] == "CANDIDATES" and row["frame_index"] == 2:
            row["payload"]["candidates"][0]["bbox"] = [185.0, 50.0, 215.0, 150.0]
        if row["type"] == "CANDIDATES" and row["frame_index"] == 4:
            row["payload"]["candidates"][0]["bbox"] = [148.0, 75.0, 188.0, 100.0]
            row["payload"]["candidates"][1]["bbox"] = [212.0, 100.0, 252.0, 125.0]
    return rows


def test_replay_holds_pair_ambiguous_when_first_split_has_two_plausible_pairs(tmp_path: Path) -> None:
    # RED at ed04a19: replay returned two diagnostic rows instead of one event HOLD.
    rows = [
        row
        for row in _two_pair_split_rows()
        if row["frame_index"] != 4
    ]
    trace_path = tmp_path / "trace.jsonl"
    _write_jsonl(trace_path, rows)

    extraction = extract_binary_merge_events(rows)
    (replay,) = replay_binary_merge_events(trace_path)

    assert len(extraction.events) == 1
    assert len(extraction.events[0].split_observations[0].pair_hypotheses) == 2
    assert replay.event_id == 1
    assert replay.hold
    assert replay.decision_reason == "pair_ambiguous"


def test_replay_resolves_later_unique_pair_under_the_same_event_id(tmp_path: Path) -> None:
    # RED at ed04a19: replay returned two rows after dropping the ambiguous first split.
    rows = _two_pair_split_rows()
    trace_path = tmp_path / "trace.jsonl"
    _write_jsonl(trace_path, rows)

    extraction = extract_binary_merge_events(rows)
    (replay,) = replay_binary_merge_events(trace_path)

    assert len(extraction.events) == 1
    assert extraction.events[0].event_id == 1
    assert tuple(observation.frame_index for observation in extraction.events[0].split_observations) == (3, 4)
    assert len(extraction.events[0].split_observations[0].pair_hypotheses) == 2
    assert len(extraction.events[0].split_observations[1].pair_hypotheses) == 1
    assert replay.event_id == 1
    assert replay.decision_frame == 4
    assert replay.split_observations_evaluated == 2
    assert not replay.hold


def _single_retained_pair_rows(background_x: float) -> list[dict[str, object]]:
    rows = make_trace_rows_for_separate_overlap_merged_split()
    for row in rows:
        if row["type"] == "CANDIDATES" and row["frame_index"] == 4:
            row["payload"]["candidates"].append(
                _candidate(
                    "background_alternative",
                    4,
                    (background_x, 0.50),
                    half_ratio=0.02,
                )
            )
    return rows


def test_replay_holds_when_unique_retained_pair_margin_does_not_clear_uncertainty(
    tmp_path: Path,
) -> None:
    # RED at d1372b1: the retained pair skipped pair margin and resolved immediately.
    rows = _single_retained_pair_rows(0.575)
    trace_path = tmp_path / "trace.jsonl"
    _write_jsonl(trace_path, rows)

    extraction = extract_binary_merge_events(rows)
    (replay,) = replay_binary_merge_events(trace_path)

    assert len(extraction.events[0].split_observations[0].pair_hypotheses) == 1
    assert replay.hold
    assert replay.decision_reason == "pair_ambiguous"
    decision = replay.diagnostics["decisions"][0]
    assert 0.0 < decision["normalized_margin"] <= 0.25
    assert decision["pair_cost"] < decision["runner_up_pair_cost"]
    assert decision["required_pair_margin"] == pytest.approx(0.25)


def test_replay_resolves_when_unique_retained_pair_margin_clears_uncertainty(
    tmp_path: Path,
) -> None:
    rows = _single_retained_pair_rows(0.52)
    trace_path = tmp_path / "trace.jsonl"
    _write_jsonl(trace_path, rows)

    extraction = extract_binary_merge_events(rows)
    (replay,) = replay_binary_merge_events(trace_path)

    assert len(extraction.events[0].split_observations[0].pair_hypotheses) == 1
    assert not replay.hold
    assert replay.decision_reason == "binary_judges_agree"


def test_replay_holds_judge_disagreement_for_a_unique_pair(tmp_path: Path) -> None:
    # RED at ed04a19: BinarySplitObservation did not retain pair_hypotheses.
    rows = make_trace_rows_for_separate_overlap_merged_split()
    for row in rows:
        if row["type"] == "CANDIDATES" and row["frame_index"] == 4:
            row["payload"]["candidates"] = [
                _candidate("upper_child", 4, (0.50, 0.45), half_ratio=0.04),
                _candidate("lower_child", 4, (0.50, 0.55), half_ratio=0.04),
            ]
        if row["type"] == "TARGET_SELECTION" and row["frame_index"] == 4:
            row["payload"]["point"] = [200.0, 100.0]
    trace_path = tmp_path / "trace.jsonl"
    _write_jsonl(trace_path, rows)

    extraction = extract_binary_merge_events(rows)
    (replay,) = replay_binary_merge_events(trace_path)

    assert len(extraction.events) == 1
    assert len(extraction.events[0].split_observations[0].pair_hypotheses) == 1
    assert replay.hold
    assert replay.decision_reason == "judge_disagreement"


def test_split_observation_excludes_all_pair_cluster_members_from_context() -> None:
    # RED: duplicate cluster members leaked into context_candidates.
    rows = make_trace_rows_for_separate_overlap_merged_split()
    for row in rows:
        if row["type"] == "CANDIDATES" and row["frame_index"] == 4:
            row["payload"]["candidates"].extend(
                [
                    _candidate("target_child_duplicate", 4, (0.421, 0.50), score=0.7),
                    _candidate("background_child_duplicate", 4, (0.581, 0.50), score=0.7),
                ]
            )

    extraction = extract_binary_merge_events(rows)

    observation = extraction.events[0].split_observations[0]
    assert tuple(candidate.candidate_id for candidate in observation.context_candidates) == (
        "anchor_child",
    )


def _identity_risk_board_rows(
    *,
    extra_outside_candidates: int = 0,
    close_collision_distractors: bool = False,
    initial_close_collision_distractors: bool = False,
    reverse_candidates: bool = False,
    mirrored: bool = False,
) -> list[dict[str, object]]:
    target_x = 0.54 if mirrored else 0.46
    background_x = 1.0 - target_x
    split_target_x = 0.58 if mirrored else 0.42
    split_background_x = 1.0 - split_target_x

    rows = _preparation_rows(
        (-2, -1),
        target_start=target_x,
        target_step=0.0,
        background_step=0.0,
    )

    def board_candidates(frame_index: int) -> list[dict[str, object]]:
        candidates = _board_distractors(frame_index)
        candidates.extend(
            _candidate(
                f"outside_extra_{frame_index}_{index}",
                frame_index,
                (0.02 + 0.03 * index, 0.72),
                score=0.99,
            )
            for index in range(extra_outside_candidates)
        )
        if close_collision_distractors and 1 <= frame_index <= 3:
            direction = -1.0 if mirrored else 1.0
            candidates.extend(
                (
                    _candidate(
                        f"close_small_{frame_index}",
                        frame_index,
                        (target_x + direction * 0.02, 0.50),
                        half_ratio=0.01,
                        score=0.99,
                    ),
                    _candidate(
                        f"close_large_{frame_index}",
                        frame_index,
                        (target_x - direction * 0.02, 0.50),
                        score=0.99,
                    ),
                )
            )
        if initial_close_collision_distractors and 0 <= frame_index <= 3:
            direction = -1.0 if mirrored else 1.0
            candidates.extend(
                (
                    _candidate(
                        f"initial_close_a_{frame_index}",
                        frame_index,
                        (target_x + direction * 0.02, 0.50),
                        score=0.99,
                    ),
                    _candidate(
                        f"initial_close_b_{frame_index}",
                        frame_index,
                        (target_x - direction * 0.02, 0.50),
                        score=0.99,
                    ),
                )
            )
        return candidates

    rows += _rows_for_frame(
        0,
        [
            _candidate("visible_target_0", 0, (target_x, 0.50)),
            _candidate("visible_background_0", 0, (background_x, 0.50)),
            *board_candidates(0),
        ],
        (target_x, 0.50),
        identity_state="UNKNOWN",
    )
    rows.append(_white_anchor_row(0, (target_x, 0.50)))
    rows += _rows_for_frame(
        1,
        [
            _candidate("visible_target_1", 1, (target_x, 0.50), half_ratio=0.06),
            _candidate("visible_background_1", 1, (background_x, 0.50), half_ratio=0.06),
            *board_candidates(1),
        ],
        (target_x, 0.50),
        identity_state="UNKNOWN",
    )
    rows.append(_white_anchor_row(1, (target_x, 0.50)))
    for frame_index in (2, 3):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"risk_target_{frame_index}", frame_index, (target_x, 0.50), half_ratio=0.06),
                _candidate(f"risk_background_{frame_index}", frame_index, (background_x, 0.50), half_ratio=0.06),
                *board_candidates(frame_index),
            ],
            (target_x, 0.50),
            identity_state="IDENTITY_HOLD",
        )
    rows += _rows_for_frame(
        4,
        [
            _candidate("target_child_4", 4, (split_target_x, 0.50)),
            _candidate("background_child_4", 4, (split_background_x, 0.50)),
            _candidate(
                "background_alternative_4",
                4,
                ((1.0 - 0.575) if mirrored else 0.575, 0.50),
                half_ratio=0.02,
            ),
            *board_candidates(4),
        ],
        (split_target_x, 0.50),
        identity_state="IDENTITY_HOLD",
    )
    rows += _rows_for_frame(
        5,
        [
            _candidate("target_child_5", 5, (split_target_x, 0.50)),
            _candidate("background_child_5", 5, (split_background_x, 0.50)),
            *board_candidates(5),
        ],
        (split_target_x, 0.50),
        identity_state="IDENTITY_HOLD",
    )
    if reverse_candidates:
        for row in rows:
            if row.get("type") == "CANDIDATES":
                row["payload"]["candidates"].reverse()
    return rows


def _runtime_integration_signature(
    extraction: object,
    replay: BinaryEventReplay,
) -> tuple[object, ...]:
    event = getattr(extraction, "events")[0]
    pair_ids = tuple(
        tuple(
            tuple(cluster.candidate.candidate_id for cluster in pair.clusters)
            for pair in observation.pair_hypotheses
        )
        for observation in event.split_observations
    )
    return (
        event.event_id,
        event.premerge.background_candidate_id,
        event.reason,
        event.merge_frame_indices,
        event.split_frame_indices,
        pair_ids,
        replay.split_frame,
        replay.decision_frame,
        replay.split_observations_evaluated,
        tuple(
            (
                decision["frame_index"],
                decision["status"],
                decision["reason"],
                decision["normalized_margin"],
                decision["pair_cost"],
                decision["runner_up_pair_cost"],
                decision["required_pair_margin"],
                decision["h1"],
                decision["h2"],
            )
            for decision in replay.diagnostics["decisions"]
        ),
        replay.hold,
        replay.decision_reason,
        replay.selected_target_candidate_id,
        replay.selected_background_candidate_id,
    )


def test_identity_risk_board_flow_integrates_extraction_localization_and_replay(
    tmp_path: Path,
) -> None:
    # RED at 02aab3d: expanded contact sent all board candidates to event detection.
    rows = _identity_risk_board_rows()
    trace_path = tmp_path / "trace.jsonl"
    _write_jsonl(trace_path, rows)

    extraction = extract_binary_merge_events(rows, event_limit=1)
    replays = replay_binary_merge_events(trace_path, event_limit=1)

    assert len(extraction.events) == 1
    assert not extraction.diagnostics
    assert len(replays) == 1
    event = extraction.events[0]
    replay = replays[0]
    assert event.event_id == replay.event_id == 1
    assert event.premerge.frame_index == 1
    assert tuple(observation.frame_index for observation in event.split_observations) == (4, 5)
    assert all(len(observation.pair_hypotheses) == 1 for observation in event.split_observations)
    assert len(event.split_observations[0].pair_competitors) > 1
    assert replay.split_observations_evaluated == 2
    first, second = replay.diagnostics["decisions"]
    assert first["reason"] == "pair_ambiguous"
    assert 0.0 < first["normalized_margin"] <= first["required_pair_margin"]
    assert first["runner_up_pair_cost"] is not None
    assert first["pair_cost"] < first["runner_up_pair_cost"]
    assert second["status"] == "resolved"
    assert second["h1"] is not None
    assert second["h2"] is not None
    assert not replay.hold
    assert replay.decision_reason == "binary_judges_agree"
    assert replay.selected_target_candidate_id == "target_child_5"
    assert replay.selected_background_candidate_id == "background_child_5"


def test_identity_risk_runtime_isolated_from_outside_and_reordered_candidates(
    tmp_path: Path,
) -> None:
    signatures: list[tuple[object, ...]] = []
    for name, rows in (
        ("baseline", _identity_risk_board_rows()),
        ("outside", _identity_risk_board_rows(extra_outside_candidates=3)),
        ("reordered", _identity_risk_board_rows(reverse_candidates=True)),
        ("close", _identity_risk_board_rows(close_collision_distractors=True)),
        (
            "close-reordered",
            _identity_risk_board_rows(
                close_collision_distractors=True,
                reverse_candidates=True,
            ),
        ),
    ):
        trace_path = tmp_path / f"{name}.jsonl"
        _write_jsonl(trace_path, rows)
        extraction = extract_binary_merge_events(rows, event_limit=1)
        replays = replay_binary_merge_events(trace_path, event_limit=1)
        assert len(extraction.events) == 1
        assert len(replays) == 1
        signatures.append(_runtime_integration_signature(extraction, replays[0]))

    assert signatures[1:] == signatures[:1] * (len(signatures) - 1)


def test_identity_risk_frame_zero_close_distractors_do_not_replace_event_background(
    tmp_path: Path,
) -> None:
    signatures: list[tuple[object, ...]] = []
    for name, rows in (
        ("baseline", _identity_risk_board_rows()),
        (
            "initial-close",
            _identity_risk_board_rows(initial_close_collision_distractors=True),
        ),
        (
            "initial-close-reordered",
            _identity_risk_board_rows(
                initial_close_collision_distractors=True,
                reverse_candidates=True,
            ),
        ),
    ):
        trace_path = tmp_path / f"{name}.jsonl"
        _write_jsonl(trace_path, rows)
        extraction = extract_binary_merge_events(rows, event_limit=1)
        replays = replay_binary_merge_events(trace_path, event_limit=1)
        assert len(extraction.events) == 1
        assert len(replays) == 1
        event = extraction.events[0]
        assert event.premerge.background_candidate_id == "visible_background_1"
        replay = replays[0]
        signatures.append(
            (
                event.event_id,
                event.premerge.background_candidate_id,
                tuple(
                    tuple(
                        tuple(cluster.candidate.candidate_id for cluster in pair.clusters)
                        for pair in observation.pair_hypotheses
                    )
                    for observation in event.split_observations
                ),
                tuple(decision["status"] for decision in replay.diagnostics["decisions"]),
                replay.selected_target_candidate_id,
                replay.selected_background_candidate_id,
            )
        )

    assert signatures[1:] == signatures[:1] * (len(signatures) - 1)


def test_identity_risk_h1_h2_role_resolution_is_direction_invariant(tmp_path: Path) -> None:
    for name, rows in (
        ("forward", _identity_risk_board_rows()),
        ("mirrored", _identity_risk_board_rows(mirrored=True)),
    ):
        trace_path = tmp_path / f"{name}.jsonl"
        _write_jsonl(trace_path, rows)
        (replay,) = replay_binary_merge_events(trace_path, event_limit=1)

        final = replay.diagnostics["decisions"][-1]
        assert final["status"] == "resolved"
        assert final["h1"] is not None
        assert final["h2"] is not None
        assert {
            final["h1"]["target_candidate_id"],
            final["h2"]["target_candidate_id"],
        } == {"target_child_5", "background_child_5"}
        assert replay.selected_target_candidate_id == "target_child_5"
        assert replay.selected_background_candidate_id == "background_child_5"


def test_runtime_diagnostics_distinguish_candidate_pair_and_event_failures(tmp_path: Path) -> None:
    candidate_absent_rows = _identity_risk_board_rows()
    for row in candidate_absent_rows:
        if row.get("type") == "CANDIDATES" and row.get("frame_index") in (4, 5):
            row["payload"]["candidates"] = [
                candidate
                for candidate in row["payload"]["candidates"]
                if not str(candidate["candidate_id"]).startswith("background_")
            ]
            row["payload"]["candidates"].append(
                _candidate(
                    f"detector_only_{row['frame_index']}",
                    row["frame_index"],
                    (0.54, 0.70),
                    half_ratio=0.01,
                )
            )
    candidate_trace = tmp_path / "candidate-absent.jsonl"
    pair_trace = tmp_path / "pair-ambiguous.jsonl"
    event_trace = tmp_path / "event-detection.jsonl"
    empty_score = tmp_path / "empty-score.jsonl"
    _write_jsonl(candidate_trace, candidate_absent_rows)
    _write_jsonl(pair_trace, _identity_risk_board_rows())
    _write_jsonl(
        event_trace,
        make_trace_rows_for_separate_overlap_merged_split(identity_state="IDENTITY_HOLD"),
    )
    _write_jsonl(empty_score, [])

    (candidate_replay,) = replay_binary_merge_events(candidate_trace, event_limit=1)
    (pair_replay,) = replay_binary_merge_events(pair_trace, event_limit=1)
    (event_replay,) = replay_binary_merge_events(event_trace, event_limit=1)
    (candidate_score,) = score_binary_merge_events((candidate_replay,), empty_score, candidate_trace)
    (event_score,) = score_binary_merge_events((event_replay,), empty_score, event_trace)

    assert candidate_replay.decision_reason == "candidate_absent"
    assert pair_replay.diagnostics["decisions"][0]["reason"] == "pair_ambiguous"
    assert event_replay.decision_reason == "premerge_identity_untrusted"
    assert candidate_score.outcome is BinaryEventOutcome.EVENT_DETECTION_FAILURE
    assert event_score.outcome.value == "event_detection_failure"


def test_identity_risk_runtime_is_invariant_to_post_hoc_gt(tmp_path: Path) -> None:
    rows = _identity_risk_board_rows()
    trace_path = tmp_path / "trace.jsonl"
    left_gt_path = tmp_path / "left-gt.jsonl"
    right_gt_path = tmp_path / "right-gt.jsonl"
    _write_jsonl(trace_path, rows)
    _write_jsonl(left_gt_path, [{"solver_frame_index": 5, "target_x": 168.0, "target_y": 100.0}])
    _write_jsonl(right_gt_path, [{"solver_frame_index": 5, "target_x": 232.0, "target_y": 100.0}])

    before = replay_binary_merge_events(trace_path, event_limit=1)
    assert len(before) == 1
    left_score = score_binary_merge_events(before, left_gt_path, trace_path)
    after = replay_binary_merge_events(trace_path, event_limit=1)
    right_score = score_binary_merge_events(after, right_gt_path, trace_path)

    assert json.dumps([asdict(row) for row in before], sort_keys=True) == json.dumps(
        [asdict(row) for row in after],
        sort_keys=True,
    )
    assert left_score[0].target_candidate_id == "target_child_5"
    assert right_score[0].target_candidate_id == "background_child_5"
    assert left_score[0].outcome is BinaryEventOutcome.LATE_RECOVERY
    assert right_score[0].outcome is BinaryEventOutcome.WRONG_SWITCH


def test_child_evidence_uses_premerge_motion_not_parent_center() -> None:
    target = _runtime_candidate("target_child", 1, (100.0, 65.0))
    background = _runtime_candidate("background_child", 1, (125.0, 60.0))
    anchor = _runtime_candidate("anchor_after", 1, (45.0, 30.0))
    profile = BackgroundFlowProfile((0.025, 0.0), 0.0, 1, 0, "available")

    expected = build_child_evidence(
        event=_event(parent_bbox=(85.0, 45.0, 140.0, 75.0)),
        child=target,
        other_child=background,
        context_candidates=(anchor,),
        flow_profile=profile,
        evidence={},
        frame_shape=FRAME_SHAPE,
    )
    moved_parent = build_child_evidence(
        event=_event(parent_bbox=(5.0, 5.0, 395.0, 195.0)),
        child=target,
        other_child=background,
        context_candidates=(anchor,),
        flow_profile=profile,
        evidence={},
        frame_shape=FRAME_SHAPE,
    )

    assert expected.target_motion_residual == pytest.approx(0.0)
    assert moved_parent.target_motion_residual == pytest.approx(expected.target_motion_residual)
    assert math.isnan(
        build_child_evidence(
            event=_event(),
            child=target,
            other_child=background,
            context_candidates=(anchor,),
            flow_profile=BackgroundFlowProfile(None, math.inf, 0, 1, "unavailable"),
            evidence={},
            frame_shape=FRAME_SHAPE,
        ).background_motion_residual
    )


def test_child_evidence_preserves_background_anchor_relation_and_role_decision() -> None:
    target = _runtime_candidate("target_child", 1, (100.0, 65.0), score=0.8)
    background = _runtime_candidate("background_child", 1, (125.0, 60.0), score=0.9)
    anchor = _runtime_candidate("anchor_after", 1, (45.0, 30.0))
    profile = BackgroundFlowProfile((0.025, 0.0), 0.0, 1, 0, "available")
    event = _event()

    target_evidence = build_child_evidence(
        event=event,
        child=target,
        other_child=background,
        context_candidates=(anchor,),
        flow_profile=profile,
        evidence={},
        frame_shape=FRAME_SHAPE,
    )
    background_evidence = build_child_evidence(
        event=event,
        child=background,
        other_child=target,
        context_candidates=(anchor,),
        flow_profile=profile,
        evidence={},
        frame_shape=FRAME_SHAPE,
    )
    decision = BinaryMergeIdentityResolver().evaluate(
        event_id=event.event_id,
        child_a=target_evidence,
        child_b=background_evidence,
    )

    assert background_evidence.neighbor_relation_residual == pytest.approx(0.0)
    assert target_evidence.neighbor_relation_residual > background_evidence.neighbor_relation_residual
    assert decision.status is BinaryTransferStatus.RESOLVED
    assert decision.target_candidate_id == "target_child"


def test_preparation_profile_ignores_rows_at_or_after_event_premerge() -> None:
    past_rows = _preparation_rows()
    future_rows = _preparation_rows((3, 4, 5))
    for row in future_rows:
        if row["type"] != "CANDIDATES":
            continue
        for candidate in row["payload"]["candidates"]:
            candidate["center"][0] += 200.0
            candidate["bbox"][0] += 200.0
            candidate["bbox"][2] += 200.0

    past_profile = binary_merge_shadow._profile_from_preparation_rows(
        past_rows,
        FRAME_SHAPE,
        before_frame_index=3,
    )
    profile_with_future = binary_merge_shadow._profile_from_preparation_rows(
        past_rows + future_rows,
        FRAME_SHAPE,
        before_frame_index=3,
    )

    assert past_profile == profile_with_future
    assert past_profile.velocity_ratio == pytest.approx((0.01, 0.0))


def test_preparation_profile_excludes_each_trusted_target_candidate() -> None:
    rows: list[dict[str, object]] = []
    for frame_index in (0, 1):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"target_{frame_index}", frame_index, (0.50 + 0.01 * frame_index, 0.80)),
                _candidate(f"background_a_{frame_index}", frame_index, (0.10 + 0.01 * frame_index, 0.20)),
                _candidate(f"background_b_{frame_index}", frame_index, (0.70 + 0.01 * frame_index, 0.60)),
            ],
            (0.50 + 0.01 * frame_index, 0.80),
        )

    profile = binary_merge_shadow._profile_from_preparation_rows(
        rows,
        FRAME_SHAPE,
        before_frame_index=2,
    )

    assert not profile.available
    assert profile.reason == "insufficient_background_motion"


def test_replay_builds_profile_only_from_rows_before_each_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_rows = _shift_frame_indices(make_trace_rows_for_separate_overlap_merged_split(), 3)
    for row in event_rows:
        if row.get("type") == "CANDIDATES" and row.get("frame_index") == 5:
            row["payload"]["candidates"].append(_candidate("merge_context", 5, (0.15, 0.15)))
    future_rows: list[dict[str, object]] = []
    for frame_index in (8, 9):
        future_rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"future_target_{frame_index}", frame_index, (0.42, 0.50)),
                _candidate(f"future_background_{frame_index}", frame_index, (0.58, 0.50)),
                _candidate(f"future_anchor_a_{frame_index}", frame_index, (0.10, 0.15)),
                _candidate(f"future_anchor_b_{frame_index}", frame_index, (0.90, 0.85)),
            ],
            (0.42, 0.50),
        )
    base_rows = _preparation_rows() + event_rows
    base_trace_path = tmp_path / "base-trace.jsonl"
    future_trace_path = tmp_path / "future-trace.jsonl"
    _write_jsonl(base_trace_path, base_rows)
    _write_jsonl(future_trace_path, base_rows + future_rows)
    captured_frames: list[tuple[int, ...]] = []
    original_builder = binary_merge_shadow.build_background_flow_profile

    def capture_profile(
        frames: tuple[tuple[int, tuple[Candidate, ...]], ...],
        *,
        frame_shape: tuple[int, int],
    ) -> BackgroundFlowProfile:
        captured_frames.append(tuple(frame_index for frame_index, _candidates in frames))
        return original_builder(frames, frame_shape=frame_shape)

    monkeypatch.setattr(binary_merge_shadow, "build_background_flow_profile", capture_profile)

    base_replays = replay_binary_merge_events(base_trace_path, event_limit=1)
    future_replays = replay_binary_merge_events(future_trace_path, event_limit=1)

    assert len(base_replays) == len(future_replays) == 1
    assert len(captured_frames) == 2
    assert all(
        frame_index < replay.premerge_frame
        for replay, profile_frames in zip((base_replays[0], future_replays[0]), captured_frames)
        for frame_index in profile_frames
    )
    assert (
        base_replays[0].premerge_frame,
        base_replays[0].split_frame,
        base_replays[0].decision_frame,
        base_replays[0].selected_target_candidate_id,
        base_replays[0].selected_background_candidate_id,
        base_replays[0].decision_reason,
        base_replays[0].hold,
        base_replays[0].split_observations_evaluated,
    ) == (
        future_replays[0].premerge_frame,
        future_replays[0].split_frame,
        future_replays[0].decision_frame,
        future_replays[0].selected_target_candidate_id,
        future_replays[0].selected_background_candidate_id,
        future_replays[0].decision_reason,
        future_replays[0].hold,
        future_replays[0].split_observations_evaluated,
    )


def test_premerge_velocity_ignores_untrusted_hold_selection() -> None:
    rows: list[dict[str, object]] = []
    rows += _rows_for_frame(
        0,
        [
            _candidate("trusted_target_0", 0, (0.40, 0.50)),
            _candidate("trusted_background_0", 0, (0.65, 0.50)),
        ],
        (0.40, 0.50),
    )
    rows += _rows_for_frame(
        5,
        [
            _candidate("hold_selection", 5, (0.90, 0.50)),
            _candidate("hold_background", 5, (0.65, 0.50)),
        ],
        (0.90, 0.50),
        identity_state="IDENTITY_HOLD",
    )
    rows.append(
        {
            "type": "TEMPORAL_SELECTOR",
            "frame_index": 5,
            "payload": {
                "debug": {
                    "kinematic_wide_beam_debug": {
                        "reason": "white_anchor",
                        "point": [0.90 * FRAME_SHAPE[1], 0.50 * FRAME_SHAPE[0]],
                    }
                }
            },
        }
    )
    rows += _rows_for_frame(
        6,
        [
            _candidate("trusted_target_6", 6, (0.42, 0.50)),
            _candidate("trusted_background_6", 6, (0.65, 0.50)),
        ],
        (0.42, 0.50),
    )
    for frame_index in (7, 8):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"target_overlap_{frame_index}", frame_index, (0.455, 0.50), half_ratio=0.06),
                _candidate(f"background_overlap_{frame_index}", frame_index, (0.545, 0.50), half_ratio=0.06),
            ],
            (0.455, 0.50),
        )
    rows += _rows_for_frame(
        9,
        [
            _candidate("target_child", 9, (0.44, 0.50)),
            _candidate("background_child", 9, (0.58, 0.50)),
        ],
        (0.44, 0.50),
    )

    extraction = extract_binary_merge_events(rows)

    assert len(extraction.events) == 1
    assert extraction.events[0].premerge.frame_index == 6
    assert extraction.events[0].premerge.target_velocity == pytest.approx(
        (((0.42 - 0.40) * FRAME_SHAPE[1]) / 6.0, 0.0)
    )


def _two_frame_overlap_then_two_frame_split_rows() -> list[dict[str, object]]:
    rows = _preparation_rows(
        (-2, -1),
        target_start=0.42,
        target_step=0.0,
        background_step=0.0,
    )
    rows += _rows_for_frame(
        0,
        [
            _candidate("target_before", 0, (0.42, 0.50)),
            _candidate("background_before", 0, (0.58, 0.50)),
        ],
        (0.42, 0.50),
    )
    for frame_index in (1, 2):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"target_overlap_{frame_index}", frame_index, (0.455, 0.50), half_ratio=0.06),
                _candidate(f"background_overlap_{frame_index}", frame_index, (0.545, 0.50), half_ratio=0.06),
                _candidate(f"distractor_{frame_index}", frame_index, (0.24, 0.30)),
            ],
            (0.455, 0.50),
        )
    for frame_index in (3, 4):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"target_child_{frame_index}", frame_index, (0.42, 0.50)),
                _candidate(f"background_child_{frame_index}", frame_index, (0.58, 0.50)),
                _candidate(f"anchor_{frame_index}", frame_index, (0.24, 0.30)),
            ],
            (0.42, 0.50),
        )
    return rows


def _two_scoreable_event_rows() -> list[dict[str, object]]:
    rows = _two_frame_overlap_then_two_frame_split_rows()
    rows += _rows_for_frame(
        5,
        [
            _candidate("second_target_before", 5, (0.42, 0.50)),
            _candidate("second_background_before", 5, (0.58, 0.50)),
        ],
        (0.42, 0.50),
    )
    for frame_index in (6, 7):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"second_target_overlap_{frame_index}", frame_index, (0.455, 0.50), half_ratio=0.06),
                _candidate(f"second_background_overlap_{frame_index}", frame_index, (0.545, 0.50), half_ratio=0.06),
            ],
            (0.455, 0.50),
        )
    for frame_index in (8, 9):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"second_target_child_{frame_index}", frame_index, (0.42, 0.50)),
                _candidate(f"second_background_child_{frame_index}", frame_index, (0.58, 0.50)),
            ],
            (0.42, 0.50),
        )
    return rows


def test_binary_event_preserves_later_valid_split_observations_until_trace_end() -> None:
    extraction = extract_binary_merge_events(_two_frame_overlap_then_two_frame_split_rows())

    assert len(extraction.events) == 1
    assert extraction.events[0].event_id == 1
    assert tuple(row.frame_index for row in extraction.events[0].split_observations) == (3, 4)


def test_binary_event_requires_runtime_default_two_merge_confirmations() -> None:
    rows = _two_frame_overlap_then_two_frame_split_rows()
    rows = [row for row in rows if row["frame_index"] != 2]

    extraction = extract_binary_merge_events(rows)

    assert not extraction.events


def test_binary_event_finalizes_unresolved_prior_event_before_new_event_id() -> None:
    rows: list[dict[str, object]] = []
    rows += _rows_for_frame(
        0,
        [_candidate("target_before", 0, (0.42, 0.50)), _candidate("background_before", 0, (0.58, 0.50))],
        (0.42, 0.50),
    )
    for frame_index in (1, 2):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"target_merge_{frame_index}", frame_index, (0.455, 0.50), half_ratio=0.06),
                _candidate(f"background_merge_{frame_index}", frame_index, (0.545, 0.50), half_ratio=0.06),
            ],
            (0.455, 0.50),
        )
    rows += _rows_for_frame(
        3,
        [
            _candidate("first_unresolved_target", 3, (0.42, 0.50)),
            _candidate("first_unresolved_extra", 3, (0.49, 0.50)),
            _candidate("first_unresolved_background", 3, (0.58, 0.50)),
        ],
        (0.42, 0.50),
    )
    for frame_index in (4, 5):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"target_second_merge_{frame_index}", frame_index, (0.455, 0.50), half_ratio=0.06),
                _candidate(f"background_second_merge_{frame_index}", frame_index, (0.545, 0.50), half_ratio=0.06),
            ],
            (0.455, 0.50),
        )
    for frame_index in (6, 7):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"target_second_child_{frame_index}", frame_index, (0.42, 0.50)),
                _candidate(f"background_second_child_{frame_index}", frame_index, (0.58, 0.50)),
            ],
            (0.42, 0.50),
        )

    extraction = extract_binary_merge_events(rows)

    assert tuple(event.event_id for event in extraction.events) == (1, 2)
    assert not extraction.diagnostics


def test_second_event_uses_separate_frame_before_its_pending_confirmation() -> None:
    rows: list[dict[str, object]] = []
    rows += _rows_for_frame(
        0,
        [_candidate("first_target", 0, (0.42, 0.50)), _candidate("first_background", 0, (0.58, 0.50))],
        (0.42, 0.50),
    )
    for frame_index in (1, 2):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"first_merge_target_{frame_index}", frame_index, (0.455, 0.50), half_ratio=0.06),
                _candidate(f"first_merge_background_{frame_index}", frame_index, (0.545, 0.50), half_ratio=0.06),
            ],
            (0.455, 0.50),
        )
    rows += _rows_for_frame(
        3,
        [
            _candidate("second_premerge_target", 3, (0.42, 0.50)),
            _candidate("second_premerge_background", 3, (0.58, 0.50)),
        ],
        (0.42, 0.50),
    )
    for frame_index in (4, 5):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"second_merge_target_{frame_index}", frame_index, (0.455, 0.50), half_ratio=0.06),
                _candidate(f"second_merge_background_{frame_index}", frame_index, (0.545, 0.50), half_ratio=0.06),
            ],
            (0.455, 0.50),
        )
    for frame_index in (6, 7):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"second_child_target_{frame_index}", frame_index, (0.42, 0.50)),
                _candidate(f"second_child_background_{frame_index}", frame_index, (0.58, 0.50)),
            ],
            (0.42, 0.50),
        )

    extraction = extract_binary_merge_events(rows)
    second_event = next(event for event in extraction.events if event.event_id == 2)

    assert second_event.premerge.frame_index == 3
    assert second_event.premerge.target_candidate_id == "second_premerge_target"
    assert second_event.premerge.background_candidate_id == "second_premerge_background"


def test_binary_event_white_anchor_must_match_snapshot_target() -> None:
    rows = _two_frame_overlap_then_two_frame_split_rows()
    for row in rows:
        if row["frame_index"] == 0 and row["type"] == "IDENTITY_STATE":
            row["payload"] = {"state": "IDENTITY_HOLD"}
        if row["frame_index"] == 0 and row["type"] == "TARGET_SELECTION":
            row["payload"] = {"point": [0.58 * FRAME_SHAPE[1], 0.50 * FRAME_SHAPE[0]]}
    rows.append(
        {
            "type": "TEMPORAL_SELECTOR",
            "frame_index": 0,
            "payload": {
                "debug": {
                    "kinematic_wide_beam_debug": {"reason": "white_anchor", "point": [0.42 * FRAME_SHAPE[1], 0.50 * FRAME_SHAPE[0]]}
                }
            },
        }
    )

    extraction = extract_binary_merge_events(rows)

    assert not extraction.events
    assert any(row.reason == "premerge_identity_untrusted" for row in extraction.diagnostics)


def test_duplicate_collapse_merges_transitive_duplicate_component() -> None:
    parent = ((50.0, 50.0, 160.0, 100.0),)
    first = _runtime_candidate("first", 3, (80.0, 75.0), score=0.9)
    bridge = _runtime_candidate("bridge", 3, (85.0, 75.0), score=0.7)
    last = _runtime_candidate("last", 3, (90.0, 75.0), score=0.8)
    other = _runtime_candidate("other", 3, (140.0, 75.0), score=0.6)

    children, reason = collapse_physical_candidates((first, last, bridge, other), parent)

    assert reason == "available"
    assert children is not None
    assert tuple(child.candidate_id for child in children) == ("first", "other")


def test_neighbor_anchor_tie_is_unavailable() -> None:
    target = _runtime_candidate("target_child", 1, (100.0, 65.0))
    background = _runtime_candidate("background_child", 1, (125.0, 60.0))
    left = _runtime_candidate("left", 1, (44.0, 30.0))
    right = _runtime_candidate("right", 1, (46.0, 30.0))

    result = build_child_evidence(
        event=_event(),
        child=background,
        other_child=target,
        context_candidates=(left, right),
        flow_profile=BackgroundFlowProfile((0.025, 0.0), 0.0, 1, 0, "available"),
        evidence={},
        frame_shape=FRAME_SHAPE,
    )

    assert result.neighbor_relation_residual is None


def test_parent_center_does_not_change_final_role_decision() -> None:
    target = _runtime_candidate("target_child", 1, (100.0, 65.0), score=0.8)
    background = _runtime_candidate("background_child", 1, (125.0, 60.0), score=0.9)
    anchor = _runtime_candidate("anchor_after", 1, (45.0, 30.0))
    profile = BackgroundFlowProfile((0.025, 0.0), 0.0, 1, 0, "available")

    def decision_for(event: BinaryMergeEventWindow):
        return BinaryMergeIdentityResolver().evaluate(
            event_id=event.event_id,
            child_a=build_child_evidence(event=event, child=target, other_child=background, context_candidates=(anchor,), flow_profile=profile, evidence={}, frame_shape=FRAME_SHAPE),
            child_b=build_child_evidence(event=event, child=background, other_child=target, context_candidates=(anchor,), flow_profile=profile, evidence={}, frame_shape=FRAME_SHAPE),
        )

    expected = decision_for(_event(parent_bbox=(85.0, 45.0, 140.0, 75.0)))
    translated_parent = decision_for(_event(parent_bbox=(185.0, 45.0, 240.0, 75.0)))

    assert expected.status is BinaryTransferStatus.RESOLVED
    assert translated_parent.status is expected.status
    assert translated_parent.target_candidate_id == expected.target_candidate_id


def test_background_unavailable_produces_resolver_hold() -> None:
    target = _runtime_candidate("target_child", 1, (100.0, 65.0))
    background = _runtime_candidate("background_child", 1, (125.0, 60.0))
    unavailable = BackgroundFlowProfile(None, math.inf, 0, 1, "unavailable")
    event = _event()

    decision = BinaryMergeIdentityResolver().evaluate(
        event_id=event.event_id,
        child_a=build_child_evidence(event=event, child=target, other_child=background, context_candidates=(), flow_profile=unavailable, evidence={}, frame_shape=FRAME_SHAPE),
        child_b=build_child_evidence(event=event, child=background, other_child=target, context_candidates=(), flow_profile=unavailable, evidence={}, frame_shape=FRAME_SHAPE),
    )

    assert decision.status is BinaryTransferStatus.HOLD
    assert decision.reason == "invalid_evidence"


def test_same_event_id_keeps_first_physical_pair_hold_then_later_resolves() -> None:
    event = _event()
    profile = BackgroundFlowProfile((0.025, 0.0), 0.0, 1, 0, "available")

    def resolve(left: Candidate, right: Candidate):
        return BinaryMergeIdentityResolver().evaluate(
            event_id=event.event_id,
            child_a=build_child_evidence(event=event, child=left, other_child=right, context_candidates=(), flow_profile=profile, evidence={}, frame_shape=FRAME_SHAPE),
            child_b=build_child_evidence(event=event, child=right, other_child=left, context_candidates=(), flow_profile=profile, evidence={}, frame_shape=FRAME_SHAPE),
        )

    first = resolve(
        _runtime_candidate("first_left", 1, (112.0, 60.0), half_size=4.0),
        _runtime_candidate("first_right", 1, (114.0, 70.0), half_size=4.0),
    )
    later = resolve(
        _runtime_candidate("later_target", 1, (100.0, 65.0), half_size=4.0),
        _runtime_candidate("later_background", 1, (125.0, 60.0), half_size=4.0),
    )

    assert first.event_id == later.event_id == event.event_id
    assert first.status is BinaryTransferStatus.HOLD
    assert later.status is BinaryTransferStatus.RESOLVED
    assert later.target_candidate_id == "later_target"


def test_event_replay_stays_byte_equivalent_when_post_hoc_gt_changes(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    target_score_path = tmp_path / "target-score.jsonl"
    background_score_path = tmp_path / "background-score.jsonl"
    _write_jsonl(trace_path, make_trace_rows_for_separate_overlap_merged_split())
    _write_jsonl(
        target_score_path,
        [{"solver_frame_index": 4, "target_x": 168.0, "target_y": 100.0}],
    )
    _write_jsonl(
        background_score_path,
        [{"solver_frame_index": 4, "target_x": 232.0, "target_y": 100.0}],
    )

    before_scoring = replay_binary_merge_events(trace_path)
    target_scores = score_binary_merge_events(before_scoring, target_score_path, trace_path)
    after_scoring = replay_binary_merge_events(trace_path)
    background_scores = score_binary_merge_events(after_scoring, background_score_path, trace_path)

    assert json.dumps([asdict(row) for row in before_scoring], sort_keys=True) == json.dumps(
        [asdict(row) for row in after_scoring],
        sort_keys=True,
    )
    assert target_scores[0].outcome is BinaryEventOutcome.CORRECT_TRANSFER
    assert background_scores[0].outcome is BinaryEventOutcome.WRONG_SWITCH


def test_event_replay_stops_after_the_first_resolved_split_observation(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    _write_jsonl(trace_path, _two_frame_overlap_then_two_frame_split_rows())

    (replay,) = replay_binary_merge_events(trace_path)

    assert replay.split_frame == 3
    assert replay.decision_frame == 3
    assert replay.split_observations_evaluated == 1
    assert not replay.hold


def test_board_frame_shape_prefers_real_session_start_board_roi_schema() -> None:
    rows = [_session_start_row(height=538, width=460)]
    rows += make_trace_rows_for_separate_overlap_merged_split()
    for row in rows:
        if row.get("type") == "CANDIDATES":
            row["payload"]["frame_shape"] = [1, 1]

    assert _board_frame_shape(rows) == (538, 460)


def test_board_frame_shape_reads_real_session_start_without_candidate_frame_shape() -> None:
    rows = [_session_start_row(height=538, width=460)]
    rows += make_trace_rows_for_separate_overlap_merged_split()
    for row in rows:
        if row.get("type") == "CANDIDATES":
            row["payload"].pop("frame_shape")

    assert _board_frame_shape(rows) == (538, 460)


def test_event_replay_holds_after_all_ambiguous_split_observations(tmp_path: Path) -> None:
    rows: list[dict[str, object]] = []
    rows += _rows_for_frame(
        0,
        [_candidate("target_before", 0, (0.42, 0.50)), _candidate("background_before", 0, (0.58, 0.50))],
        (0.42, 0.50),
    )
    for frame_index in (1, 2):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"target_overlap_{frame_index}", frame_index, (0.455, 0.50), half_ratio=0.06),
                _candidate(f"background_overlap_{frame_index}", frame_index, (0.545, 0.50), half_ratio=0.06),
            ],
            (0.455, 0.50),
        )
    for frame_index in (3, 4):
        rows += _rows_for_frame(
            frame_index,
            [
                _candidate(f"target_child_{frame_index}", frame_index, (0.42, 0.50)),
                _candidate(f"background_child_{frame_index}", frame_index, (0.58, 0.50)),
            ],
            (0.42, 0.50),
        )
    trace_path = tmp_path / "trace.jsonl"
    _write_jsonl(trace_path, rows)

    (replay,) = replay_binary_merge_events(trace_path)

    assert replay.split_frame == 3
    assert replay.decision_frame is None
    assert replay.split_observations_evaluated == 2
    assert replay.hold
    assert set(replay.diagnostics["split_child_ids"][3]) == {
        "target_child_3",
        "background_child_3",
    }
    assert set(replay.diagnostics["split_child_ids"][4]) == {
        "target_child_4",
        "background_child_4",
    }


def test_scoring_associates_gt_only_with_replayed_physical_split_children(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    score_path = tmp_path / "score.jsonl"
    rows = make_trace_rows_for_separate_overlap_merged_split()
    for row in rows:
        if row.get("type") == "CANDIDATES" and row.get("frame_index") == 4:
            row["payload"]["candidates"].append(
                _candidate("duplicate_target", 4, (0.44, 0.50), score=0.7)
            )
    _write_jsonl(trace_path, rows)
    _write_jsonl(
        score_path,
        [{"solver_frame_index": 4, "target_x": 180.0, "target_y": 100.0}],
    )

    replay = BinaryEventReplay(
        event_id=1,
        premerge_frame=0,
        split_frame=4,
        decision_frame=4,
        split_observations_evaluated=1,
        selected_target_candidate_id="target_child",
        selected_background_candidate_id="background_child",
        decision_reason="binary_judges_agree",
        hold=False,
        diagnostics={
            "split_child_ids": {4: ("target_child", "background_child")},
            "physical_child_ids_by_frame": {4: ("target_child", "background_child")},
        },
    )
    (score,) = score_binary_merge_events((replay,), score_path, trace_path)

    assert score.target_candidate_id == "target_child"
    assert score.outcome is BinaryEventOutcome.CORRECT_TRANSFER


def test_extraction_diagnostics_remain_scored_event_rows(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    score_path = tmp_path / "score.jsonl"
    _write_jsonl(
        trace_path,
        make_trace_rows_for_separate_overlap_merged_split(identity_state="IDENTITY_HOLD"),
    )
    _write_jsonl(
        score_path,
        [{"solver_frame_index": 3, "target_x": 168.0, "target_y": 100.0}],
    )

    (replay,) = replay_binary_merge_events(trace_path)
    (score,) = score_binary_merge_events((replay,), score_path, trace_path)

    assert replay.selected_target_candidate_id is None
    assert replay.selected_background_candidate_id is None
    assert score.outcome is BinaryEventOutcome.EVENT_DETECTION_FAILURE


def test_event_summary_and_markdown_are_compact_and_event_scoped() -> None:
    scores = (
        BinaryEventScore(1, BinaryEventOutcome.CORRECT_TRANSFER, "a", "a", 0.0, "correct"),
        BinaryEventScore(2, BinaryEventOutcome.WRONG_SWITCH, "a", "b", 0.5, "wrong"),
        BinaryEventScore(3, BinaryEventOutcome.SAFE_HOLD, "a", None, None, "hold"),
        BinaryEventScore(4, BinaryEventOutcome.LATE_RECOVERY, "a", "a", 1.0, "late"),
        BinaryEventScore(5, BinaryEventOutcome.TARGET_NOT_IN_CANDIDATES, None, "a", None, "absent"),
        BinaryEventScore(6, BinaryEventOutcome.EVENT_DETECTION_FAILURE, None, None, None, "detection"),
        BinaryEventScore(7, BinaryEventOutcome.DUPLICATE_DETECTION_UNRESOLVED, None, None, None, "duplicate"),
    )
    replay = BinaryEventReplay(
        event_id=3,
        premerge_frame=10,
        split_frame=11,
        decision_frame=None,
        split_observations_evaluated=2,
        selected_target_candidate_id=None,
        selected_background_candidate_id=None,
        decision_reason="hypothesis_ambiguous",
        hold=True,
        diagnostics={
            "decisions": (
                {
                    "h1": {"target_candidate_id": "a", "background_candidate_id": "b", "target_cost": 1.0, "background_cost": 2.0, "support_groups": ("target_motion",)},
                    "h2": {"target_candidate_id": "b", "background_candidate_id": "a", "target_cost": 2.0, "background_cost": 1.0, "support_groups": ("background_motion",)},
                },
            ),
        },
    )

    summary = summarize_binary_merge_events(scores)
    markdown = render_binary_merge_event_markdown((replay,), scores)

    assert summary.total_events == 7
    assert summary.resolved_events == 3
    assert summary.wrong_switches == 1
    assert summary.median_normalized_recovery_delay == pytest.approx(0.5)
    assert "## Event 3" in markdown
    assert "- HOLD: hypothesis_ambiguous" in markdown
    assert "- H1: target=a" in markdown
    assert "- H2: target=b" in markdown
    assert "## Frame" not in markdown


def test_cli_dry_run_writes_one_event_with_runtime_and_post_hoc_diagnostics(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    score_path = tmp_path / "score.jsonl"
    output_path = tmp_path / "representative_event_001"
    _write_jsonl(trace_path, make_trace_rows_for_separate_overlap_merged_split())
    _write_jsonl(
        score_path,
        [{"solver_frame_index": 4, "target_x": 168.0, "target_y": 100.0}],
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "core.puzzle.binary_merge_shadow",
            "--trace",
            str(trace_path),
            "--score",
            str(score_path),
            "--output",
            str(output_path),
            "--event-limit",
            "1",
        ],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert {path.name for path in output_path.iterdir()} == {
        "binary_merge_events.jsonl",
        "binary_merge_validation.md",
    }
    event_rows = [
        json.loads(line)
        for line in (output_path / "binary_merge_events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(event_rows) == 1
    assert "mouse_action" not in json.dumps(event_rows[0], sort_keys=True)
    assert event_rows[0]["runtime_decision"]["reason"] == "binary_judges_agree"
    assert event_rows[0]["post_hoc_score"]["outcome"] == "correct_transfer"
    assert event_rows[0]["judge_diagnostics"]["decisions"]
    assert event_rows[0]["judge_diagnostics"]["decisions"][-1]["h1"]
    assert event_rows[0]["judge_diagnostics"]["decisions"][-1]["h2"]
    assert event_rows[0]["gate_verdict"] == "PASSED"
    assert event_rows[0]["failure_stage"] is None
    assert event_rows[0]["expand_allowed"] is True
    markdown = (output_path / "binary_merge_validation.md").read_text(encoding="utf-8")
    assert "- gate_verdict: PASSED" in markdown
    assert "- expand_allowed: true" in markdown


def test_event_limit_preserves_first_ambiguous_event_before_later_observations() -> None:
    extraction = extract_binary_merge_events(
        make_trace_rows_for_separate_overlap_merged_split(first_split_ambiguous=True),
        event_limit=1,
    )

    assert tuple(event.event_id for event in extraction.events) == (1,)
    assert not extraction.diagnostics


def test_replay_event_limit_does_not_resolve_second_scoreable_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace_path = tmp_path / "trace.jsonl"
    rows = _two_scoreable_event_rows()
    _write_jsonl(trace_path, rows)
    assert len(extract_binary_merge_events(rows).events) == 2
    resolver_calls: list[int] = []
    resolver_type = binary_merge_shadow.BinaryMergeIdentityResolver

    class ResolverSpy:
        def __init__(self) -> None:
            self._delegate = resolver_type()

        def evaluate(self, **kwargs: object) -> object:
            event_id = kwargs["event_id"]
            assert isinstance(event_id, int)
            resolver_calls.append(event_id)
            assert event_id == 1
            return self._delegate.evaluate(**kwargs)

    monkeypatch.setattr(binary_merge_shadow, "BinaryMergeIdentityResolver", ResolverSpy)

    replays = replay_binary_merge_events(trace_path, event_limit=1)

    assert len(replays) == 1
    assert replays[0].event_id == 1
    assert resolver_calls == [1]


def test_cli_failure_maps_pair_ambiguity_to_canonical_gate(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    score_path = tmp_path / "score.jsonl"
    output_path = tmp_path / "failed_event"
    _write_jsonl(
        trace_path,
        [
            row
            for row in _two_pair_split_rows()
            if row["frame_index"] != 4
        ],
    )
    _write_jsonl(score_path, [])

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "core.puzzle.binary_merge_shadow",
            "--trace",
            str(trace_path),
            "--score",
            str(score_path),
            "--output",
            str(output_path),
            "--event-limit",
            "1",
        ],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert {path.name for path in output_path.iterdir()} == {
        "binary_merge_events.jsonl",
        "binary_merge_validation.md",
    }
    event = json.loads((output_path / "binary_merge_events.jsonl").read_text(encoding="utf-8"))
    assert event["runtime_decision"]["reason"] == "pair_ambiguous"
    assert event["gate_verdict"] == "GATE_FAILED"
    assert event["failure_stage"] == "ambiguity"
    assert event["expand_allowed"] is False
    assert "mouse_action" not in json.dumps(event, sort_keys=True)
    markdown = (output_path / "binary_merge_validation.md").read_text(encoding="utf-8")
    assert "- gate_verdict: GATE_FAILED" in markdown
    assert "- failure_stage: ambiguity" in markdown
    assert "- expand_allowed: false" in markdown
