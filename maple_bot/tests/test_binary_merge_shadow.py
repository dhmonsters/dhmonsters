# 런타임 추적 기반 이진 병합 사건 추출과 자식 증거 계산을 검증합니다.
from __future__ import annotations

import math

import pytest

from core.puzzle.binary_merge_background import BackgroundFlowProfile
from core.puzzle.binary_merge_identity import BinaryMergeIdentityResolver, BinaryTransferStatus
from core.puzzle.binary_merge_shadow import (
    BinaryMergeEventWindow,
    BinaryPremergeSnapshot,
    BackgroundRelationSnapshot,
    build_child_evidence,
    extract_binary_merge_events,
)
from core.puzzle.models import Candidate


FRAME_SHAPE = (200, 400)


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


def make_trace_rows_for_separate_overlap_merged_split(
    *,
    parent_center_ratio: tuple[float, float] = (0.50, 0.50),
    first_split_ambiguous: bool = False,
    identity_state: str = "TRACK_CONFIDENT",
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
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
            _candidate("target_overlap", 1, (0.46, 0.50), half_ratio=0.06),
            _candidate("background_overlap", 1, (0.54, 0.50), half_ratio=0.06),
            _candidate("anchor_overlap", 1, (0.24, 0.30)),
        ],
        (0.46, 0.50),
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

    assert extraction.events[0].merge_frame_indices == (1, 2)
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
