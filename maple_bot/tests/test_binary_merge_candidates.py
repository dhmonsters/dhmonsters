# 병합 사건의 지역 후보 쌍 정규화 계약을 검증한다.
from __future__ import annotations

from dataclasses import replace
from itertools import chain

import pytest

from core.puzzle.binary_merge_candidates import (
    CandidateLocalizationContext,
    localize_candidate_pairs,
)
from core.puzzle.models import Candidate


def _candidate(
    candidate_id: str,
    center: tuple[float, float],
    *,
    half_size: tuple[float, float] = (10.0, 10.0),
    score: float = 0.8,
) -> Candidate:
    return Candidate(
        candidate_id=candidate_id,
        frame_index=7,
        bbox=(
            center[0] - half_size[0],
            center[1] - half_size[1],
            center[0] + half_size[0],
            center[1] + half_size[1],
        ),
        center=center,
        score=score,
        source="test",
    )


def _context() -> CandidateLocalizationContext:
    return CandidateLocalizationContext(
        target_center=(100.0, 100.0),
        background_center=(140.0, 100.0),
        target_bbox=(90.0, 90.0, 110.0, 110.0),
        background_bbox=(130.0, 90.0, 150.0, 110.0),
        parent_bboxes=((88.0, 88.0, 152.0, 112.0),),
        uncertainty_ratio=0.25,
    )


def _board_distractors() -> tuple[Candidate, ...]:
    return tuple(
        _candidate(
            f"distractor-{index:02d}",
            (20.0 + 30.0 * (index % 14), 20.0 if index < 14 else 180.0),
            score=0.99,
        )
        for index in range(28)
    )


def _pair_ids(result: object) -> tuple[tuple[str, str], ...]:
    pairs = getattr(result, "pairs")
    return tuple(
        tuple(cluster.candidate.candidate_id for cluster in pair.clusters)
        for pair in pairs
    )


def test_localizer_ignores_board_distractors_and_returns_the_event_local_pair() -> None:
    target = _candidate("target", (100.0, 100.0))
    background = _candidate("background", (140.0, 100.0))

    result = localize_candidate_pairs((target, background, *_board_distractors()), _context())

    assert result.reason == "available"
    assert _pair_ids(result) == (("background", "target"),)


def test_localizer_collapses_duplicate_proposals_for_each_physical_child() -> None:
    candidates = (
        _candidate("target-primary", (100.0, 100.0), score=0.9),
        _candidate("target-duplicate", (101.0, 100.0), score=0.7),
        _candidate("background-primary", (140.0, 100.0), score=0.8),
        _candidate("background-duplicate", (141.0, 100.0), score=0.6),
    )

    result = localize_candidate_pairs(candidates, _context())

    assert result.reason == "available"
    assert tuple(cluster.candidate.candidate_id for cluster in result.clusters) == (
        "background-primary",
        "target-primary",
    )
    assert tuple(member.candidate_id for member in result.clusters[0].members) == (
        "background-duplicate",
        "background-primary",
    )
    assert tuple(member.candidate_id for member in result.clusters[1].members) == (
        "target-duplicate",
        "target-primary",
    )


def test_localizer_keeps_nearby_distinct_shapes_in_separate_clusters() -> None:
    target = _candidate("target", (100.0, 100.0))
    nearby_tall_shape = _candidate("nearby-tall", (102.0, 100.0), half_size=(4.0, 18.0))
    background = _candidate("background", (140.0, 100.0))

    result = localize_candidate_pairs((target, nearby_tall_shape, background), _context())

    assert tuple(cluster.candidate.candidate_id for cluster in result.clusters) == (
        "background",
        "nearby-tall",
        "target",
    )


def test_localizer_returns_candidate_absent_when_only_one_event_candidate_remains() -> None:
    result = localize_candidate_pairs((_candidate("target", (100.0, 100.0)),), _context())

    assert result.clusters
    assert not result.pairs
    assert result.reason == "candidate_absent"


def test_localizer_preserves_multiple_nondominated_pairs_as_ambiguous() -> None:
    candidates = (
        _candidate("target-a", (100.0, 90.0)),
        _candidate("background-a", (140.0, 90.0)),
        _candidate("target-b", (100.0, 110.0)),
        _candidate("background-b", (140.0, 110.0)),
    )
    context = replace(
        _context(),
        target_center=(100.0, 90.0),
        background_center=(140.0, 110.0),
        target_bbox=(90.0, 80.0, 110.0, 100.0),
        background_bbox=(130.0, 100.0, 150.0, 120.0),
        parent_bboxes=((88.0, 78.0, 152.0, 102.0),),
    )

    result = localize_candidate_pairs(candidates, context)

    assert result.reason == "pair_ambiguous"
    assert len(result.pairs) >= 2


def test_localizer_is_deterministic_when_candidate_input_order_changes() -> None:
    candidates = (
        _candidate("target", (100.0, 100.0)),
        _candidate("background", (140.0, 100.0)),
        _candidate("target-duplicate", (101.0, 100.0), score=0.7),
        _candidate("background-duplicate", (141.0, 100.0), score=0.6),
    )

    forward = localize_candidate_pairs(candidates, _context())
    reverse = localize_candidate_pairs(tuple(reversed(candidates)), _context())

    assert forward == reverse


def test_localizer_ignores_high_score_yolo_candidate_outside_parent_region() -> None:
    local_children = (
        _candidate("target", (100.0, 100.0)),
        _candidate("background", (140.0, 100.0)),
    )
    outside_yolo = _candidate("outside-yolo", (360.0, 240.0), score=1.0)

    baseline = localize_candidate_pairs(local_children, _context())
    with_outside_yolo = localize_candidate_pairs(
        tuple(chain(local_children, (outside_yolo,))),
        _context(),
    )

    assert with_outside_yolo == baseline


def test_localizer_uses_median_role_diagonal_to_exclude_asymmetric_boundary_distractor() -> None:
    target = _candidate("target", (100.0, 100.0))
    background = _candidate("background", (140.0, 100.0), half_size=(100.0, 100.0))
    boundary_distractor = _candidate("boundary-distractor", (350.0, 100.0), score=0.99)
    context = replace(
        _context(),
        background_bbox=(40.0, 0.0, 240.0, 200.0),
        parent_bboxes=((40.0, 0.0, 360.0, 200.0),),
    )

    result = localize_candidate_pairs((target, background, boundary_distractor), context)

    assert tuple(cluster.candidate.candidate_id for cluster in result.clusters) == (
        "background",
        "target",
    )


def test_localizer_does_not_expand_parent_region_when_parent_union_only_grows() -> None:
    candidates = (
        _candidate("target", (100.0, 100.0)),
        _candidate("parent-edge", (170.0, 100.0)),
    )
    compact_context = replace(_context(), parent_bboxes=((90.0, 90.0, 140.0, 110.0),))
    expanded_context = replace(_context(), parent_bboxes=((30.0, 90.0, 140.0, 110.0),))

    compact = localize_candidate_pairs(candidates, compact_context)
    expanded = localize_candidate_pairs(candidates, expanded_context)

    assert compact == expanded
    assert tuple(cluster.candidate.candidate_id for cluster in expanded.clusters) == ("target",)
    assert expanded.reason == "candidate_absent"


def test_localizer_rejects_parent_residual_when_parent_union_only_grows() -> None:
    candidates = (
        _candidate("target", (100.0, 100.0)),
        _candidate("parent-edge", (150.0, 100.0)),
    )
    compact_context = replace(_context(), parent_bboxes=((90.0, 90.0, 140.0, 110.0),))
    expanded_context = replace(_context(), parent_bboxes=((20.0, 90.0, 140.0, 110.0),))

    compact = localize_candidate_pairs(candidates, compact_context)
    expanded = localize_candidate_pairs(candidates, expanded_context)

    assert compact.reason == "available"
    assert expanded.reason == "candidate_absent"


def test_localizer_preserves_the_exact_nondominated_pair_set_for_three_clusters() -> None:
    candidates = (
        _candidate("target", (100.0, 100.0)),
        _candidate("middle", (120.0, 100.0)),
        _candidate("background", (140.0, 100.0)),
    )
    context = replace(_context(), parent_bboxes=((105.0, 60.0, 135.0, 140.0),))

    result = localize_candidate_pairs(candidates, context)

    assert result.reason == "pair_ambiguous"
    assert _pair_ids(result) == (
        ("background", "middle"),
        ("middle", "target"),
    )


def test_localizer_uses_elapsed_role_prediction_and_motion_uncertainty() -> None:
    context = CandidateLocalizationContext(
        target_center=(100.0, 100.0),
        background_center=(140.0, 100.0),
        target_bbox=(90.0, 90.0, 110.0, 110.0),
        background_bbox=(130.0, 90.0, 150.0, 110.0),
        parent_bboxes=((165.0, 88.0, 232.0, 112.0),),
        uncertainty_ratio=0.25,
        target_velocity=(6.0, 0.0),
        background_velocity=(8.0, 0.0),
        elapsed_observations=5,
        motion_uncertainty_ratio=0.05,
    )
    candidates = (
        _candidate("target-child", (170.0, 100.0)),
        _candidate("background-child", (220.0, 100.0)),
        _candidate("static-target-distractor", (100.0, 100.0)),
        _candidate("static-background-distractor", (140.0, 100.0)),
    )

    result = localize_candidate_pairs(candidates, context)

    assert result.reason == "available"
    assert result.effective_uncertainty_ratio == pytest.approx(0.50)
    assert _pair_ids(result) == (("background-child", "target-child"),)
