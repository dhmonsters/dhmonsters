# 이진 병합 역할 가설 판별기의 공개 결정 계약을 검증한다.
from __future__ import annotations

import math

import pytest

from core.puzzle.binary_merge_identity import (
    BinaryMergeIdentityResolver,
    BinaryRoleEvidence,
    BinaryTransferStatus,
)


def _evidence(
    candidate_id: str,
    *,
    target_motion_residual: float,
    background_motion_residual: float,
    neighbor_relation_residual: float = 0.30,
    ancestry_residual: float = 0.20,
    shape_residual: float = 0.30,
    yolo_shortfall: float = 0.0,
    uncertainty: float = 0.10,
) -> BinaryRoleEvidence:
    return BinaryRoleEvidence(
        candidate_id=candidate_id,
        target_motion_residual=target_motion_residual,
        background_motion_residual=background_motion_residual,
        neighbor_relation_residual=neighbor_relation_residual,
        ancestry_residual=ancestry_residual,
        shape_residual=shape_residual,
        yolo_shortfall=yolo_shortfall,
        uncertainty=uncertainty,
    )


def test_agreed_background_and_target_judges_transfer_identity() -> None:
    resolver = BinaryMergeIdentityResolver()

    decision = resolver.evaluate(
        event_id=7,
        child_a=_evidence(
            "a",
            target_motion_residual=0.25,
            background_motion_residual=2.20,
            neighbor_relation_residual=1.80,
            ancestry_residual=0.20,
            shape_residual=0.30,
            yolo_shortfall=0.0,
            uncertainty=0.10,
        ),
        child_b=_evidence(
            "b",
            target_motion_residual=2.10,
            background_motion_residual=0.20,
            neighbor_relation_residual=0.30,
            ancestry_residual=0.25,
            shape_residual=0.35,
            yolo_shortfall=0.0,
            uncertainty=0.10,
        ),
    )

    assert decision.status is BinaryTransferStatus.RESOLVED
    assert decision.target_candidate_id == "a"
    assert decision.background_candidate_id == "b"


def test_conflicting_judges_hold_instead_of_switching() -> None:
    resolver = BinaryMergeIdentityResolver()

    decision = resolver.evaluate(
        event_id=8,
        child_a=_evidence(
            "a",
            target_motion_residual=0.30,
            background_motion_residual=0.40,
            neighbor_relation_residual=0.35,
            ancestry_residual=0.20,
            shape_residual=0.25,
            yolo_shortfall=0.0,
            uncertainty=0.10,
        ),
        child_b=_evidence(
            "b",
            target_motion_residual=1.50,
            background_motion_residual=1.60,
            neighbor_relation_residual=1.40,
            ancestry_residual=0.20,
            shape_residual=0.25,
            yolo_shortfall=0.0,
            uncertainty=0.10,
        ),
    )

    assert decision.status is BinaryTransferStatus.HOLD
    assert decision.target_candidate_id is None
    assert decision.reason == "judge_disagreement"


def test_swapping_children_preserves_physical_role_assignment() -> None:
    resolver = BinaryMergeIdentityResolver()
    target = _evidence("target", target_motion_residual=0.10, background_motion_residual=2.0)
    background = _evidence("background", target_motion_residual=2.0, background_motion_residual=0.10)

    original = resolver.evaluate(event_id=9, child_a=target, child_b=background)
    swapped = resolver.evaluate(event_id=9, child_a=background, child_b=target)

    assert original.status is BinaryTransferStatus.RESOLVED
    assert swapped.status is BinaryTransferStatus.RESOLVED
    assert original.target_candidate_id == swapped.target_candidate_id == "target"
    assert original.background_candidate_id == swapped.background_candidate_id == "background"


def test_low_yolo_cannot_override_agreeing_motion_judges() -> None:
    resolver = BinaryMergeIdentityResolver()

    decision = resolver.evaluate(
        event_id=10,
        child_a=_evidence(
            "a",
            target_motion_residual=0.10,
            background_motion_residual=2.0,
            yolo_shortfall=100.0,
        ),
        child_b=_evidence(
            "b",
            target_motion_residual=2.0,
            background_motion_residual=0.10,
            yolo_shortfall=0.0,
        ),
    )

    assert decision.status is BinaryTransferStatus.RESOLVED
    assert decision.target_candidate_id == "a"
    assert decision.background_candidate_id == "b"


def test_equal_motion_residuals_hold_as_ambiguous() -> None:
    resolver = BinaryMergeIdentityResolver()

    decision = resolver.evaluate(
        event_id=11,
        child_a=_evidence("a", target_motion_residual=0.50, background_motion_residual=0.50),
        child_b=_evidence("b", target_motion_residual=0.50, background_motion_residual=0.50),
    )

    assert decision.status is BinaryTransferStatus.HOLD
    assert decision.reason == "judge_disagreement"


@pytest.mark.parametrize("ancestry_residual", (None, math.nan))
def test_missing_or_non_finite_required_residual_holds_as_invalid_evidence(
    ancestry_residual: float | None,
) -> None:
    resolver = BinaryMergeIdentityResolver()

    decision = resolver.evaluate(
        event_id=12,
        child_a=_evidence(
            "a",
            target_motion_residual=0.10,
            background_motion_residual=2.0,
            ancestry_residual=ancestry_residual,
        ),
        child_b=_evidence("b", target_motion_residual=2.0, background_motion_residual=0.10),
    )

    assert decision.status is BinaryTransferStatus.HOLD
    assert decision.reason == "invalid_evidence"


def test_duplicate_candidate_identity_holds() -> None:
    resolver = BinaryMergeIdentityResolver()

    decision = resolver.evaluate(
        event_id=13,
        child_a=_evidence("same", target_motion_residual=0.10, background_motion_residual=2.0),
        child_b=_evidence("same", target_motion_residual=2.0, background_motion_residual=0.10),
    )

    assert decision.status is BinaryTransferStatus.HOLD
    assert decision.reason == "duplicate_candidate_identity"
