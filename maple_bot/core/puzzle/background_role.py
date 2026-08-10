# 후보가 배경으로 설명되는 정도를 점수화하고 역할을 판정합니다.
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class BackgroundJudgeVector:
    candidate_id: str
    values: Mapping[str, float | None]
    target_jump_ratio: float
    detection_quality: float | None


@dataclass(frozen=True)
class BackgroundRoleProfile:
    weights: Mapping[str, float]
    saturation: Mapping[str, float]
    resolve_margin: float
    physical_jump_limit: float
    yolo_floor: float
    yolo_uncertainty_weight: float


@dataclass(frozen=True)
class BackgroundRoleDecision:
    target_candidate_id: str | None
    background_candidate_id: str | None
    status: str
    margin: float
    available_weight: float
    reason: str
    judge_contributions: Mapping[str, float]


def residual_to_similarity(residual: float | None, saturation: float) -> float | None:
    if not _is_finite_number(saturation) or saturation <= 0.0:
        raise ValueError("saturation must be a finite positive number")
    if not _is_finite_number(residual) or residual < 0.0:
        return None
    if residual >= saturation:
        return 0.0
    return 1.0 - residual / saturation


def decide_background_role(
    child_a: BackgroundJudgeVector,
    child_b: BackgroundJudgeVector,
    profile: BackgroundRoleProfile,
) -> BackgroundRoleDecision:
    _validate_profile(profile)
    _validate_candidate(child_a)
    _validate_candidate(child_b)
    if child_a.candidate_id == child_b.candidate_id:
        raise ValueError("candidate IDs must differ")

    common_judges = tuple(
        judge
        for judge, weight in profile.weights.items()
        if weight > 0.0
        and judge in child_a.values
        and judge in child_b.values
        and child_a.values[judge] is not None
        and child_b.values[judge] is not None
    )
    available_weight = sum(profile.weights[judge] for judge in common_judges)
    if available_weight <= 0.0:
        return BackgroundRoleDecision(
            None,
            None,
            "hold",
            0.0,
            0.0,
            "hold_no_background_evidence",
            {},
        )

    scores = {
        child_a.candidate_id: _score(child_a, profile, common_judges, available_weight),
        child_b.candidate_id: _score(child_b, profile, common_judges, available_weight),
    }
    jump_limited = {
        child_a.candidate_id: child_a.target_jump_ratio > profile.physical_jump_limit,
        child_b.candidate_id: child_b.target_jump_ratio > profile.physical_jump_limit,
    }
    if jump_limited[child_a.candidate_id] and jump_limited[child_b.candidate_id]:
        return _hold_decision(
            available_weight,
            abs(scores[child_a.candidate_id] - scores[child_b.candidate_id]),
            "hold_ambiguous_background",
        )
    forced_by_gate = jump_limited[child_a.candidate_id] != jump_limited[child_b.candidate_id]
    if jump_limited[child_a.candidate_id]:
        background, target = child_a, child_b
    elif jump_limited[child_b.candidate_id]:
        background, target = child_b, child_a
    elif scores[child_a.candidate_id] >= scores[child_b.candidate_id]:
        background, target = child_a, child_b
    else:
        background, target = child_b, child_a

    margin = abs(scores[child_a.candidate_id] - scores[child_b.candidate_id])
    required_margin = _required_margin(profile, child_a, child_b)
    if not forced_by_gate and margin <= required_margin:
        return BackgroundRoleDecision(
            None,
            None,
            "hold",
            margin,
            available_weight,
            "hold_ambiguous_background",
            {},
        )
    background_score = scores[background.candidate_id]
    judge_contributions = {
        judge: background.values[judge] * profile.weights[judge]
        / (background_score * available_weight)
        for judge in common_judges
    }
    return BackgroundRoleDecision(
        target.candidate_id,
        background.candidate_id,
        "resolved",
        margin,
        available_weight,
        "background_elimination",
        judge_contributions,
    )


def _score(
    candidate: BackgroundJudgeVector,
    profile: BackgroundRoleProfile,
    judges: tuple[str, ...],
    available_weight: float,
) -> float:
    return sum(candidate.values[judge] * profile.weights[judge] for judge in judges) / available_weight


def _required_margin(
    profile: BackgroundRoleProfile,
    child_a: BackgroundJudgeVector,
    child_b: BackgroundJudgeVector,
) -> float:
    shortfalls = []
    for candidate in (child_a, child_b):
        if candidate.detection_quality is not None and candidate.detection_quality < profile.yolo_floor:
            shortfalls.append((profile.yolo_floor - candidate.detection_quality) / profile.yolo_floor)
    return profile.resolve_margin + profile.yolo_uncertainty_weight * max(shortfalls, default=0.0)


def _validate_candidate(candidate: BackgroundJudgeVector) -> None:
    if not isinstance(candidate.candidate_id, str) or not candidate.candidate_id.strip():
        raise ValueError("candidate_id must be non-empty")
    if not _is_finite_number(candidate.target_jump_ratio) or candidate.target_jump_ratio < 0.0:
        raise ValueError("target_jump_ratio must be a finite non-negative number")
    if candidate.detection_quality is not None and (
        not _is_finite_number(candidate.detection_quality)
        or not 0.0 <= candidate.detection_quality <= 1.0
    ):
        raise ValueError("detection_quality must be between 0 and 1")
    for value in candidate.values.values():
        if value is not None and (
            not _is_finite_number(value) or not 0.0 <= value <= 1.0
        ):
            raise ValueError("judge values must be between 0 and 1")


def _validate_profile(profile: BackgroundRoleProfile) -> None:
    if not profile.weights or all(weight <= 0.0 for weight in profile.weights.values()):
        raise ValueError("profile must have at least one positive weight")
    for weight in profile.weights.values():
        if not _is_finite_number(weight) or weight < 0.0:
            raise ValueError("weights must be finite and non-negative")
    for saturation in profile.saturation.values():
        if not _is_finite_number(saturation) or saturation <= 0.0:
            raise ValueError("saturation must be finite and positive")
    for value in (
        profile.resolve_margin,
        profile.physical_jump_limit,
        profile.yolo_floor,
        profile.yolo_uncertainty_weight,
    ):
        if not _is_finite_number(value) or value < 0.0:
            raise ValueError("profile numbers must be finite and non-negative")
    if profile.yolo_floor > 1.0:
        raise ValueError("yolo_floor must be at most 1")


def _hold_decision(
    available_weight: float,
    margin: float,
    reason: str,
) -> BackgroundRoleDecision:
    return BackgroundRoleDecision(
        None,
        None,
        "hold",
        margin,
        available_weight,
        reason,
        {},
    )


def _is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)
