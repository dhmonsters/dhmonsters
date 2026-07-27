# 이진 병합 뒤 타겟과 배경 역할의 신분 전달을 판별한다.
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite


class BinaryTransferStatus(str, Enum):
    RESOLVED = "resolved"
    HOLD = "hold"


@dataclass(frozen=True)
class BinaryRoleEvidence:
    candidate_id: str
    target_motion_residual: float
    background_motion_residual: float
    neighbor_relation_residual: float | None
    ancestry_residual: float
    shape_residual: float | None
    yolo_shortfall: float | None
    uncertainty: float


@dataclass(frozen=True)
class BinaryHypothesis:
    name: str
    target_candidate_id: str
    background_candidate_id: str
    target_cost: float
    background_cost: float
    support_groups: tuple[str, ...]

    @property
    def total_cost(self) -> float:
        return self.target_cost + self.background_cost


@dataclass(frozen=True)
class BinaryTransferDecision:
    event_id: int
    status: BinaryTransferStatus
    target_candidate_id: str | None
    background_candidate_id: str | None
    selected_hypothesis: str | None
    normalized_margin: float
    reason: str
    debug: dict[str, object]


class BinaryMergeIdentityResolver:
    def evaluate(
        self,
        *,
        event_id: int,
        child_a: BinaryRoleEvidence,
        child_b: BinaryRoleEvidence,
    ) -> BinaryTransferDecision:
        invalid_reason = self._invalid_reason(child_a, child_b)
        if invalid_reason is not None:
            return self._hold(event_id, 0.0, invalid_reason)

        h1 = self._hypothesis("h1", child_a, child_b)
        h2 = self._hypothesis("h2", child_b, child_a)
        required = {"target_motion", "background_motion"}
        supported = [row for row in (h1, h2) if required.issubset(row.support_groups)]
        if len(supported) != 1:
            best, runner_up = sorted((h1, h2), key=lambda row: row.total_cost)
            margin = self._normalized_margin(best, runner_up)
            return self._hold(event_id, margin, "judge_disagreement", h1, h2)

        best = supported[0]
        runner_up = h2 if best is h1 else h1
        margin = self._normalized_margin(best, runner_up)

        required_margin = max(0.0, child_a.uncertainty, child_b.uncertainty)
        if margin <= required_margin:
            return self._hold(event_id, margin, "hypothesis_ambiguous", h1, h2)

        return BinaryTransferDecision(
            event_id=event_id,
            status=BinaryTransferStatus.RESOLVED,
            target_candidate_id=best.target_candidate_id,
            background_candidate_id=best.background_candidate_id,
            selected_hypothesis=best.name,
            normalized_margin=margin,
            reason="binary_judges_agree",
            debug={"h1": h1, "h2": h2},
        )

    def _hypothesis(
        self,
        name: str,
        target: BinaryRoleEvidence,
        background: BinaryRoleEvidence,
    ) -> BinaryHypothesis:
        uncertainty = max(target.uncertainty, background.uncertainty)
        support_groups = []
        if target.target_motion_residual + uncertainty < background.target_motion_residual:
            support_groups.append("target_motion")
        if background.background_motion_residual + uncertainty < target.background_motion_residual:
            support_groups.append("background_motion")
        if target.ancestry_residual + uncertainty < background.ancestry_residual:
            support_groups.append("ancestry")
        if self._has_optional_pair(target.neighbor_relation_residual, background.neighbor_relation_residual):
            if background.neighbor_relation_residual + uncertainty < target.neighbor_relation_residual:
                support_groups.append("neighbor_relation")

        target_cost = (
            target.target_motion_residual
            + target.ancestry_residual
            + self._target_optional_penalty(target, background)
        )
        background_cost = (
            background.background_motion_residual
            + background.ancestry_residual
            + self._background_optional_penalty(target, background)
        )
        return BinaryHypothesis(
            name=name,
            target_candidate_id=target.candidate_id,
            background_candidate_id=background.candidate_id,
            target_cost=target_cost,
            background_cost=background_cost,
            support_groups=tuple(support_groups),
        )

    @staticmethod
    def _invalid_reason(
        child_a: BinaryRoleEvidence,
        child_b: BinaryRoleEvidence,
    ) -> str | None:
        if not isinstance(child_a, BinaryRoleEvidence) or not isinstance(child_b, BinaryRoleEvidence):
            return "invalid_evidence"
        if not isinstance(child_a.candidate_id, str) or not child_a.candidate_id:
            return "invalid_evidence"
        if not isinstance(child_b.candidate_id, str) or not child_b.candidate_id:
            return "invalid_evidence"
        if child_a.candidate_id == child_b.candidate_id:
            return "duplicate_candidate_identity"

        required_values = (
            child_a.target_motion_residual,
            child_a.background_motion_residual,
            child_a.ancestry_residual,
            child_a.uncertainty,
            child_b.target_motion_residual,
            child_b.background_motion_residual,
            child_b.ancestry_residual,
            child_b.uncertainty,
        )
        if any(not BinaryMergeIdentityResolver._is_nonnegative_finite(value) for value in required_values):
            return "invalid_evidence"
        return None

    @staticmethod
    def _normalized_margin(best: BinaryHypothesis, runner_up: BinaryHypothesis) -> float:
        scale = max(1.0, abs(best.total_cost), abs(runner_up.total_cost))
        return abs(runner_up.total_cost - best.total_cost) / scale

    @staticmethod
    def _target_optional_penalty(target: BinaryRoleEvidence, background: BinaryRoleEvidence) -> float:
        penalty = 0.0
        for target_value, background_value in (
            (target.shape_residual, background.shape_residual),
            (target.yolo_shortfall, background.yolo_shortfall),
        ):
            if BinaryMergeIdentityResolver._has_optional_pair(target_value, background_value):
                penalty += target_value
        return penalty

    @staticmethod
    def _background_optional_penalty(
        target: BinaryRoleEvidence,
        background: BinaryRoleEvidence,
    ) -> float:
        if BinaryMergeIdentityResolver._has_optional_pair(
            target.neighbor_relation_residual,
            background.neighbor_relation_residual,
        ):
            return float(background.neighbor_relation_residual)
        return 0.0

    @staticmethod
    def _has_optional_pair(target_value: float | None, background_value: float | None) -> bool:
        return (
            BinaryMergeIdentityResolver._is_nonnegative_finite(target_value)
            and BinaryMergeIdentityResolver._is_nonnegative_finite(background_value)
        )

    @staticmethod
    def _is_nonnegative_finite(value: object) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and isfinite(value)
            and value >= 0.0
        )

    @staticmethod
    def _hold(
        event_id: int,
        margin: float,
        reason: str,
        h1: BinaryHypothesis | None = None,
        h2: BinaryHypothesis | None = None,
    ) -> BinaryTransferDecision:
        debug = {name: hypothesis for name, hypothesis in (("h1", h1), ("h2", h2)) if hypothesis is not None}
        return BinaryTransferDecision(
            event_id=event_id,
            status=BinaryTransferStatus.HOLD,
            target_candidate_id=None,
            background_candidate_id=None,
            selected_hypothesis=None,
            normalized_margin=margin,
            reason=reason,
            debug=debug,
        )
