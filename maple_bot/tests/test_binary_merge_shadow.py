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


def test_binary_event_ambiguous_first_split_keeps_same_event_for_later_pair() -> None:
    extraction = extract_binary_merge_events(
        make_trace_rows_for_separate_overlap_merged_split(first_split_ambiguous=True)
    )

    assert len(extraction.events) == 1
    assert extraction.events[0].event_id == 1
    assert extraction.events[0].split_observations[0].frame_index == 4
    assert any(row.reason == "duplicate_detection_unresolved" for row in extraction.diagnostics)


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
    rows = _preparation_rows() + event_rows + future_rows
    trace_path = tmp_path / "trace.jsonl"
    _write_jsonl(trace_path, rows)
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

    replays = replay_binary_merge_events(trace_path, event_limit=1)

    assert len(replays) == 1
    assert captured_frames
    assert all(frame_index < replays[0].premerge_frame for frame_index in captured_frames[0])


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

    assert tuple(event.event_id for event in extraction.events) == (2,)
    assert any(row.reason == "missing_split_children" for row in extraction.diagnostics)


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
    _write_jsonl(score_path, [])

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


def test_event_limit_stops_at_first_diagnostic_before_later_valid_event() -> None:
    extraction = extract_binary_merge_events(
        make_trace_rows_for_separate_overlap_merged_split(first_split_ambiguous=True),
        event_limit=1,
    )

    assert not extraction.events
    assert len(extraction.diagnostics) == 1
    assert extraction.diagnostics[0].reason == "duplicate_detection_unresolved"


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


def test_cli_failure_maps_duplicate_normalization_to_canonical_gate(tmp_path: Path) -> None:
    trace_path = tmp_path / "trace.jsonl"
    score_path = tmp_path / "score.jsonl"
    output_path = tmp_path / "failed_event"
    _write_jsonl(
        trace_path,
        make_trace_rows_for_separate_overlap_merged_split(first_split_ambiguous=True),
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
    assert event["judge_diagnostics"]["extraction_reason"] == "duplicate_detection_unresolved"
    assert event["gate_verdict"] == "GATE_FAILED"
    assert event["failure_stage"] == "candidate_normalization"
    assert event["expand_allowed"] is False
    assert "mouse_action" not in json.dumps(event, sort_keys=True)
    markdown = (output_path / "binary_merge_validation.md").read_text(encoding="utf-8")
    assert "- gate_verdict: GATE_FAILED" in markdown
    assert "- failure_stage: candidate_normalization" in markdown
    assert "- expand_allowed: false" in markdown
