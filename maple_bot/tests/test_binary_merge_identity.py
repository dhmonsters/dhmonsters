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
    neighbor_relation_residual: float | None = 0.30,
    ancestry_residual: float = 0.20,
    shape_residual: float | None = 0.30,
    yolo_shortfall: float | None = 0.0,
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


def test_neighbor_relation_scores_only_the_assigned_background_child() -> None:
    resolver = BinaryMergeIdentityResolver()
    control = resolver.evaluate(
        event_id=18,
        child_a=_evidence(
            "target",
            target_motion_residual=0.10,
            background_motion_residual=2.0,
            neighbor_relation_residual=2.0,
        ),
        child_b=_evidence(
            "background",
            target_motion_residual=2.0,
            background_motion_residual=0.10,
            neighbor_relation_residual=2.0,
        ),
    )

    decision = resolver.evaluate(
        event_id=18,
        child_a=_evidence(
            "target",
            target_motion_residual=0.10,
            background_motion_residual=2.0,
            neighbor_relation_residual=2.0,
        ),
        child_b=_evidence(
            "background",
            target_motion_residual=2.0,
            background_motion_residual=0.10,
            neighbor_relation_residual=0.05,
        ),
    )

    assert decision.status is BinaryTransferStatus.RESOLVED
    assert decision.target_candidate_id == "target"
    assert "neighbor_relation" in decision.debug["h1"].support_groups
    assert "neighbor_relation" not in decision.debug["h2"].support_groups
    assert decision.debug["h1"].total_cost < control.debug["h1"].total_cost
    assert decision.debug["h1"].target_cost == pytest.approx(control.debug["h1"].target_cost)
    assert decision.debug["h1"].background_cost < control.debug["h1"].background_cost
    assert decision.debug["h2"].total_cost == pytest.approx(control.debug["h2"].total_cost)


def test_neighbor_relation_cannot_replace_required_motion_support() -> None:
    decision = BinaryMergeIdentityResolver().evaluate(
        event_id=19,
        child_a=_evidence(
            "target_like",
            target_motion_residual=0.50,
            background_motion_residual=0.50,
            neighbor_relation_residual=2.0,
        ),
        child_b=_evidence(
            "background_like",
            target_motion_residual=0.50,
            background_motion_residual=0.50,
            neighbor_relation_residual=0.05,
        ),
    )

    assert decision.status is BinaryTransferStatus.HOLD
    assert decision.reason == "judge_disagreement"


def test_low_yolo_cannot_override_agreeing_motion_judges() -> None:
    resolver = BinaryMergeIdentityResolver()
    control = resolver.evaluate(
        event_id=10,
        child_a=_evidence("a", target_motion_residual=0.10, background_motion_residual=2.0),
        child_b=_evidence("b", target_motion_residual=2.0, background_motion_residual=0.10),
    )

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
    assert decision.debug["h1"].total_cost > control.debug["h1"].total_cost


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


def test_shape_and_yolo_change_cost_without_creating_motion_support() -> None:
    resolver = BinaryMergeIdentityResolver()
    control = resolver.evaluate(
        event_id=14,
        child_a=_evidence(
            "a",
            target_motion_residual=0.20,
            background_motion_residual=2.0,
            neighbor_relation_residual=0.0,
            shape_residual=0.0,
            yolo_shortfall=0.0,
            uncertainty=0.05,
        ),
        child_b=_evidence(
            "b",
            target_motion_residual=2.0,
            background_motion_residual=0.20,
            neighbor_relation_residual=0.0,
            shape_residual=0.0,
            yolo_shortfall=0.0,
            uncertainty=0.05,
        ),
    )
    decision = resolver.evaluate(
        event_id=14,
        child_a=_evidence(
            "a",
            target_motion_residual=0.20,
            background_motion_residual=2.0,
            neighbor_relation_residual=0.0,
            shape_residual=0.40,
            yolo_shortfall=0.30,
            uncertainty=0.05,
        ),
        child_b=_evidence(
            "b",
            target_motion_residual=2.0,
            background_motion_residual=0.20,
            neighbor_relation_residual=0.0,
            shape_residual=0.10,
            yolo_shortfall=0.10,
            uncertainty=0.05,
        ),
    )

    assert decision.status is BinaryTransferStatus.RESOLVED
    assert decision.target_candidate_id == "a"
    assert decision.debug["h1"].total_cost > control.debug["h1"].total_cost
    assert decision.normalized_margin != control.normalized_margin
    assert decision.debug["h1"].support_groups == control.debug["h1"].support_groups
    assert decision.debug["h2"].support_groups == control.debug["h2"].support_groups


@pytest.mark.parametrize(
    ("uncertainty", "expected_status"),
    (
        (0.09, BinaryTransferStatus.RESOLVED),
        (0.10, BinaryTransferStatus.HOLD),
        (0.11, BinaryTransferStatus.HOLD),
    ),
)
def test_uncertainty_margin_boundary_controls_resolved_status(
    uncertainty: float,
    expected_status: BinaryTransferStatus,
) -> None:
    resolver = BinaryMergeIdentityResolver()

    decision = resolver.evaluate(
        event_id=15,
        child_a=_evidence(
            "a",
            target_motion_residual=0.0,
            background_motion_residual=0.20,
            ancestry_residual=1.50,
            uncertainty=uncertainty,
        ),
        child_b=_evidence(
            "b",
            target_motion_residual=0.20,
            background_motion_residual=0.0,
            ancestry_residual=1.50,
            uncertainty=uncertainty,
        ),
    )

    assert decision.status is expected_status
    assert decision.normalized_margin == pytest.approx(0.10)
    if expected_status is BinaryTransferStatus.HOLD:
        assert decision.reason == "hypothesis_ambiguous"


@pytest.mark.parametrize("optional_field", ("neighbor_relation_residual", "shape_residual", "yolo_shortfall"))
@pytest.mark.parametrize("unavailable", (None, math.nan, math.inf))
@pytest.mark.parametrize("missing_child", ("a", "b"))
def test_unavailable_optional_evidence_is_skipped_without_zero_advantage(
    optional_field: str,
    unavailable: float | None,
    missing_child: str,
) -> None:
    resolver = BinaryMergeIdentityResolver()
    child_a_values: dict[str, float | None] = {optional_field: 0.80}
    child_b_values: dict[str, float | None] = {optional_field: 0.80}
    if missing_child == "a":
        child_a_values[optional_field] = unavailable
    else:
        child_b_values[optional_field] = unavailable

    decision = resolver.evaluate(
        event_id=16,
        child_a=_evidence("a", target_motion_residual=0.50, background_motion_residual=0.50, **child_a_values),
        child_b=_evidence("b", target_motion_residual=0.50, background_motion_residual=0.50, **child_b_values),
    )

    assert decision.debug["h1"].total_cost == decision.debug["h2"].total_cost
    assert "neighbor_relation" not in decision.debug["h1"].support_groups
    assert "neighbor_relation" not in decision.debug["h2"].support_groups


@pytest.mark.parametrize("child_name", ("a", "b"))
@pytest.mark.parametrize(
    "required_field",
    ("target_motion_residual", "background_motion_residual", "ancestry_residual", "uncertainty"),
)
@pytest.mark.parametrize("invalid_value", (None, math.nan, math.inf, -math.inf, -0.01))
def test_every_required_field_rejects_missing_nonfinite_and_negative_values(
    child_name: str,
    required_field: str,
    invalid_value: float | None,
) -> None:
    resolver = BinaryMergeIdentityResolver()
    child_a_values: dict[str, float | None] = {
        "target_motion_residual": 0.10,
        "background_motion_residual": 2.0,
    }
    child_b_values: dict[str, float | None] = {
        "target_motion_residual": 2.0,
        "background_motion_residual": 0.10,
    }
    if child_name == "a":
        child_a_values[required_field] = invalid_value
    else:
        child_b_values[required_field] = invalid_value

    decision = resolver.evaluate(
        event_id=17,
        child_a=_evidence("a", **child_a_values),
        child_b=_evidence("b", **child_b_values),
    )

    assert decision.status is BinaryTransferStatus.HOLD
    assert decision.reason == "invalid_evidence"
