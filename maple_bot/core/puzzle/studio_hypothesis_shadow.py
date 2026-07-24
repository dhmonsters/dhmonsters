# Studio trace를 재생해 시간축 가설 보관 전략의 정답 후보 보존율을 비교합니다.
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
from math import hypot, isfinite
from pathlib import Path
from statistics import median
from typing import Any, Sequence

from openpyxl import Workbook

from core.puzzle.hypothesis_challenge import HypothesisChallengeGuard
from core.puzzle.models import Candidate, CandidateEvidence
from core.puzzle.merge_split_relative import (
    CyclePhaseContext,
    MergeSplitDecision,
    MergeSplitRelativeResolver,
    StableCycleObservation,
)
from core.puzzle.persistent_evidence_quorum import (
    PersistentEvidenceQuorum,
    pairwise_persistent_margins,
)
from core.puzzle.planet_live import (
    _choose_kinematic_local_rigid_target,
    _choose_kinematic_wide_beam_target,
)
from core.vision.transparent_kinematic_shape import TransparentKinematicBeamTracker
from core.vision.transparent_puzzle_engine import BackgroundCatalog, PuzzleCandidate

from .studio_validation import _read_jsonl, _retained_hypothesis_points


@dataclass(frozen=True)
class HypothesisReplaySummary:
    total_frames: int
    candidate_center_frames: int
    recorded_hit_frames: int
    replay_hit_frames: int
    improved_frames: int
    regressed_frames: int
    recorded_hypothesis_generation_errors: int
    replay_hypothesis_generation_errors: int


@dataclass(frozen=True)
class HypothesisSelectionReplaySummary:
    total_frames: int
    recorded_passed_frames: int
    replay_passed_frames: int
    improved_frames: int
    regressed_frames: int
    changed_frames: int
    wide_selected_frames: int
    local_rigid_selected_frames: int


@dataclass(frozen=True)
class HypothesisVariant:
    name: str
    width: int
    branch: int
    diverse_first: bool


DEFAULT_VARIANTS = (
    HypothesisVariant("baseline", 16, 5, False),
    HypothesisVariant("branch8", 16, 8, False),
    HypothesisVariant("width24", 24, 5, False),
    HypothesisVariant("width24_branch8", 24, 8, False),
    HypothesisVariant("diverse", 16, 5, True),
    HypothesisVariant("diverse_branch8", 16, 8, True),
    HypothesisVariant("diverse_width18", 18, 5, True),
    HypothesisVariant("diverse_width20", 20, 5, True),
    HypothesisVariant("diverse_width24", 24, 5, True),
)


def replay_hypothesis_tracker(
    score_jsonl: str | Path,
    trace_jsonl: str | Path,
    *,
    width: int = 16,
    branch: int = 5,
    diverse_first: bool = False,
    pass_distance_px: float = 24.0,
) -> HypothesisReplaySummary:
    return _replay_rows(
        _read_jsonl(Path(score_jsonl)),
        _read_jsonl(Path(trace_jsonl)),
        width=width,
        branch=branch,
        diverse_first=diverse_first,
        pass_distance_px=pass_distance_px,
    )


def replay_hypothesis_selection(
    score_jsonl: str | Path,
    trace_jsonl: str | Path,
    *,
    width: int = 24,
    branch: int = 5,
    diverse_first: bool = True,
    pass_distance_px: float = 24.0,
    judge_hypothesis_limit: int | None = None,
    challenge_confirm_frames: int | None = None,
    challenge_max_step_px: float = 90.0,
    protect_incumbent_sources: tuple[str, ...] = (),
    persistent_evidence_quorum: bool = False,
    merge_split_relative: bool = False,
    _details: list[dict[str, object]] | None = None,
) -> HypothesisSelectionReplaySummary:
    score_rows = _read_jsonl(Path(score_jsonl))
    trace_rows = _read_jsonl(Path(trace_jsonl))
    scores = {
        frame_index: row
        for row in score_rows
        if (frame_index := _optional_int(row.get("solver_frame_index"))) is not None
    }
    events = _events_by_frame(trace_rows)
    candidate_frames = sorted(
        {
            frame_index
            for frame_index, event_type in events
            if event_type == "CANDIDATES"
            or (merge_split_relative and event_type == "TEMPORAL_SELECTOR")
        }
    )
    tracker = TransparentKinematicBeamTracker(
        width=width,
        branch=branch,
        cost_decay=1.0,
        acceleration_weight=0.5,
        yolo_penalty_weight=0.0,
        diverse_first=diverse_first,
    )
    challenge_guard = (
        HypothesisChallengeGuard(
            confirm_frames=challenge_confirm_frames,
            max_step_px=challenge_max_step_px,
        )
        if challenge_confirm_frames is not None else None
    )
    persistent_guard = (
        PersistentEvidenceQuorum(required_positive_groups=("local_rigid",))
        if persistent_evidence_quorum else None
    )
    merge_resolver = MergeSplitRelativeResolver() if merge_split_relative else None
    merge_guard = (
        PersistentEvidenceQuorum(
            support_groups=(
                "background_relative_identity",
                "background_motion",
                "anchor_shape_identity",
            ),
            required_groups=2,
            required_observations=3,
            required_positive_groups=("background_relative_identity",),
        )
        if merge_split_relative else None
    )
    frame_shape = _board_frame_shape(trace_rows)
    cycle_frame_shape = _cycle_board_frame_shape(trace_rows)
    catalog: BackgroundCatalog | None = None
    catalog_period: int | None = None
    catalog_period_score: float | None = None
    prior_period: int | None = None
    cycle_evidence_reason = "not_started"
    local_lag_evidence_reason = "period_unavailable"
    period_recurrence_comparisons = 0
    cycle_observation_started = False
    was_white = False
    episode_observations: dict[int, tuple[_FrozenCycleObservation, ...]] = {}
    phase_observations: dict[int, tuple[_FrozenCycleObservation, ...]] = {}
    cycle_tracks: _StableCycleTracks | None = None
    stable_cycle_track_count = 0
    stable_cycle_track_ids: tuple[str, ...] = ()
    stable_cycle_excluded_counts: dict[str, int] = {}
    stable_cycle_exclusion_reasons: dict[str, str] = {}
    stable_cycle_frame_shape_reason = "not_started"
    total_frames = 0
    recorded_passed_frames = 0
    replay_passed_frames = 0
    improved_frames = 0
    regressed_frames = 0
    changed_frames = 0
    wide_selected_frames = 0
    local_rigid_selected_frames = 0
    anchor_shapes: list[tuple[float, float]] = []

    for frame_index in candidate_frames:
        candidate_payload = events.get((frame_index, "CANDIDATES"), {})
        temporal_payload = events.get((frame_index, "TEMPORAL_SELECTOR"), {})
        candidates = _candidate_models(frame_index, candidate_payload)
        candidate_rows = [
            row
            for candidate in candidate_payload.get("candidates", [])
            if isinstance(candidate, dict) and (row := _candidate_row(candidate)) is not None
        ]
        wide_debug = _wide_debug(temporal_payload)
        anchor = _point(wide_debug.get("point")) if wide_debug.get("reason") == "white_anchor" else None
        new_white_episode = bool(
            merge_split_relative and anchor is not None and not was_white
        )
        if new_white_episode:
            tracker.reset()
            if challenge_guard is not None:
                challenge_guard.reset()
            if persistent_guard is not None:
                persistent_guard.reset()
            if merge_resolver is not None:
                merge_resolver.reset()
            if merge_guard is not None:
                merge_guard.reset()
            anchor_shapes.clear()
        if anchor is not None and candidates:
            anchor_candidate = min(candidates, key=lambda candidate: _distance(candidate.center, anchor))
            anchor_shapes.append(_candidate_shape(anchor_candidate))
        phase_context: CyclePhaseContext | None = None
        current_phase_observations: tuple[_FrozenCycleObservation, ...] = ()
        observed_local_lag: int | None = None
        catalog_candidates = list(candidates)
        if merge_split_relative:
            if anchor is not None and not was_white:
                if catalog_period is not None:
                    prior_period = catalog_period
                catalog_period = None
                catalog_period_score = None
                catalog = None
                episode_observations = {}
                phase_observations = {}
                period_recurrence_comparisons = 0
                cycle_tracks = _StableCycleTracks(frame_shape=cycle_frame_shape)
                stable_cycle_track_count = 0
                stable_cycle_track_ids = ()
                stable_cycle_excluded_counts = {}
                stable_cycle_exclusion_reasons = {}
                stable_cycle_frame_shape_reason = cycle_tracks.frame_shape_reason
            if anchor is not None and catalog_candidates:
                white_candidate = min(
                    catalog_candidates,
                    key=lambda candidate: _distance(candidate.center, anchor),
                )
                catalog_candidates = [
                    candidate
                    for candidate in catalog_candidates
                    if candidate.candidate_id != white_candidate.candidate_id
                ]
            if was_white and anchor is None and cycle_tracks is not None:
                episode_observations = cycle_tracks.freeze()
                phase_observations = dict(episode_observations)
                stable_cycle_track_ids = cycle_tracks.frozen_track_ids
                stable_cycle_track_count = len(stable_cycle_track_ids)
                stable_cycle_excluded_counts = cycle_tracks.excluded_counts
                stable_cycle_exclusion_reasons = cycle_tracks.exclusion_reasons
                stable_cycle_frame_shape_reason = cycle_tracks.frame_shape_reason
                if stable_cycle_track_count >= _MIN_CYCLE_ASSOCIATIONS:
                    catalog = BackgroundCatalog()
                    for observed_frame, observed_candidates in episode_observations.items():
                        catalog.add_frame(
                            observed_frame,
                            _frozen_catalog_candidates(observed_candidates),
                        )
                    observed_period, observed_score, period_reason, comparison_count = (
                        _observed_episode_period(catalog, episode_observations)
                    )
                else:
                    observed_period = None
                    observed_score = None
                    period_reason = cycle_tracks.period_failure_reason
                    comparison_count = 0
                period_recurrence_comparisons = comparison_count
                if observed_period is not None:
                    catalog_period = observed_period
                    catalog_period_score = observed_score
                    cycle_evidence_reason = "observed_period"
                    prior_period = None
                elif prior_period is not None:
                    cycle_evidence_reason = (
                        "inactive_prior_period_insufficient_episode_evidence"
                        if period_reason == "period_association_incomplete"
                        else f"inactive_prior_period_{period_reason}"
                    )
                else:
                    cycle_evidence_reason = (
                        period_reason
                        if period_reason.startswith("period_association_")
                        else "period_unavailable"
                    )
                if observed_period is None:
                    local_lag_evidence_reason = (
                        "insufficient_episode_evidence"
                        if period_reason == "period_association_incomplete"
                        else period_reason
                    )
                was_white = False
            if cycle_tracks is not None:
                cycle_tracks.update(frame_index, catalog_candidates)
                stable_cycle_excluded_counts = cycle_tracks.excluded_counts
                stable_cycle_exclusion_reasons = cycle_tracks.exclusion_reasons
            if anchor is not None:
                was_white = True
                cycle_observation_started = True
                cycle_evidence_reason = "preparing_white_anchor"
                local_lag_evidence_reason = "preparing_white_anchor"
            elif catalog is not None and cycle_tracks is not None:
                phase_frame, frozen_failure = cycle_tracks.frozen_observation(frame_index)
                if phase_frame is None:
                    local_lag_evidence_reason = f"frozen_survivor_{frozen_failure}"
                else:
                    current_phase_observations = phase_frame
                    catalog.add_frame(
                        frame_index,
                        _frozen_catalog_candidates(phase_frame),
                    )
                    phase_observations[frame_index] = phase_frame

            if catalog is not None and catalog_period is not None:
                phase_frame, frozen_failure = cycle_tracks.frozen_observation(frame_index) if cycle_tracks is not None else (None, "missing")
                if phase_frame is None:
                    local_lag_evidence_reason = f"frozen_survivor_{frozen_failure}"
                else:
                    current_phase_observations = phase_frame
                    ranked_local_lags = catalog.local_lag_scores(
                        frame_index,
                        catalog_period,
                    )
                    candidate_lag = (
                        ranked_local_lags[0][0]
                        if ranked_local_lags
                        else catalog_period
                    )
                    local_ok, local_reason = _local_lag_temporal_support(
                        phase_observations,
                        frame_index,
                        candidate_lag,
                    )
                    if local_ok:
                        observed_local_lag = candidate_lag
                        local_lag_evidence_reason = "observed_local_lag"
                    else:
                        local_lag_evidence_reason = (
                            "local_lag_cardinality"
                            if local_reason == "association_cardinality"
                            else (
                                f"local_lag_temporal_{local_reason}"
                                if local_reason != "association_incomplete"
                                else "insufficient_local_lag_evidence"
                            )
                        )
            if catalog_period is not None and observed_local_lag is not None:
                reference_frame = frame_index - observed_local_lag
                reference_phase_observations = phase_observations.get(
                    reference_frame,
                    (),
                )
                phase_context = CyclePhaseContext(
                    period=catalog_period,
                    local_lag=observed_local_lag,
                    period_score=catalog_period_score,
                    observation_started=True,
                    reference_observations=_resolver_cycle_observations(
                        reference_frame,
                        reference_phase_observations,
                    ),
                    current_observations=_resolver_cycle_observations(
                        frame_index,
                        current_phase_observations,
                    ),
                )
            elif cycle_observation_started:
                phase_context = CyclePhaseContext(
                    period=catalog_period,
                    local_lag=None,
                    period_score=catalog_period_score,
                    observation_started=True,
                )
        tracker.update(candidate_rows, white_anchor=anchor)
        hypothesis_points = tracker.hypothesis_points
        if judge_hypothesis_limit is not None:
            judge_points = hypothesis_points[:max(1, int(judge_hypothesis_limit))]
        else:
            judge_points = hypothesis_points

        score = None
        target = None
        if not merge_split_relative:
            score = scores.get(frame_index)
            target = _target_point(score)
        target_selection = events.get((frame_index, "TARGET_SELECTION"), {})
        recorded_point = _point(target_selection.get("point"))
        if recorded_point is None or (
            not merge_split_relative and (score is None or target is None)
        ):
            continue

        replay_point = recorded_point
        replay_source = str(target_selection.get("source", "recorded"))
        challenge_debug: dict[str, object] = {}
        persistent_debug: dict[str, object] = {}
        merge_decision: MergeSplitDecision | None = None
        merge_quorum_debug: dict[str, object] = {}
        wide_gate: dict[str, object] = {}
        local_rigid_gate: dict[str, object] = {}
        evidence = _evidence_models(events.get((frame_index, "EVIDENCE"), {}))
        identity_payload = events.get((frame_index, "IDENTITY_STATE"), {})
        identity_state = str(identity_payload.get("state", ""))
        wide_gate_payload = target_selection.get("kinematic_wide_beam_gate")
        if isinstance(wide_gate_payload, dict):
            base_point = _point(wide_gate_payload.get("base_point"))
        else:
            base_point = None
        if base_point is not None and candidates and evidence:
            replay_source = "pre_wide"
            replay_point, wide_gate = _choose_kinematic_wide_beam_target(
                base_point=base_point,
                hypothesis_points=judge_points,
                candidates=candidates,
                evidence=evidence,
                identity_state=identity_state,
                frame_shape=frame_shape,
            )
            replay_point, local_rigid_gate = _choose_kinematic_local_rigid_target(
                base_point=replay_point,
                hypothesis_points=judge_points,
                candidates=candidates,
                evidence=evidence,
                identity_state=identity_state,
            )
            wide_selected_frames += int(bool(wide_gate.get("selected")))
            local_rigid_selected_frames += int(bool(local_rigid_gate.get("selected")))
            if bool(local_rigid_gate.get("selected")):
                replay_source = "kinematic_local_rigid"
            elif bool(wide_gate.get("selected")):
                replay_source = "kinematic_wide_beam"

        if replay_point is None:
            replay_point = recorded_point
        if challenge_guard is not None:
            challenger_point = replay_point
            replay_point, challenge_debug = challenge_guard.update(
                incumbent_point=recorded_point,
                challenger_point=challenger_point,
                protect_incumbent=str(target_selection.get("source", "")) in protect_incumbent_sources,
            )
            if not bool(challenge_debug.get("selected")):
                replay_source = str(target_selection.get("source", "recorded"))
        if persistent_guard is not None:
            baseline_replay_point = replay_point
            baseline_replay_source = replay_source
            preferred_challenger = (
                baseline_replay_point
                if baseline_replay_point is not None
                and _distance(baseline_replay_point, recorded_point) > 1e-6
                else None
            )
            challenger_point, group_margins, challenger_debug = _persistent_challenger(
                incumbent_point=recorded_point,
                hypothesis_points=judge_points,
                candidates=candidates,
                evidence=evidence,
                preferred_point=preferred_challenger,
                anchor_shape=_median_anchor_shape(anchor_shapes),
                frame_shape=frame_shape,
            )
            persistent_point, persistent_debug = persistent_guard.update(
                incumbent_point=recorded_point,
                challenger_point=challenger_point,
                stable_scale_px=_stable_candidate_scale(candidates),
                group_margins=group_margins,
                protect_incumbent=str(target_selection.get("source", ""))
                in protect_incumbent_sources,
            )
            persistent_debug = {**persistent_debug, "challenger": challenger_debug}
            if bool(persistent_debug.get("selected")):
                replay_point = persistent_point
                replay_source = "persistent_evidence_quorum"
            else:
                replay_point = baseline_replay_point
                replay_source = baseline_replay_source
        if merge_resolver is not None:
            baseline_replay_point = replay_point
            baseline_replay_source = replay_source
            merge_decision = merge_resolver.update(
                incumbent_point=replay_point,
                candidates=candidates,
                evidence=evidence,
                stable_area=_stable_target_area(
                    candidates,
                    incumbent_point=replay_point,
                    anchor_shapes=anchor_shapes,
                ),
                frame_shape=frame_shape,
                frame_index=frame_index,
                phase_context=phase_context,
                identity_state=identity_state,
            )
            challenger_point = merge_decision.target_point
            group_margins = _merge_split_group_margins(
                incumbent_point=baseline_replay_point,
                decision=merge_decision,
                candidates=candidates,
                evidence=evidence,
                anchor_shape=_median_anchor_shape(anchor_shapes),
                frame_shape=frame_shape,
            )
            merge_point, merge_quorum_debug = merge_guard.update(
                incumbent_point=baseline_replay_point,
                challenger_point=challenger_point,
                stable_scale_px=_stable_candidate_scale(candidates),
                group_margins=group_margins,
                protect_incumbent=(
                    anchor is not None
                    or str(target_selection.get("source", ""))
                    in protect_incumbent_sources
                ),
            )
            if bool(merge_quorum_debug.get("selected")):
                replay_point = merge_point
                replay_source = "merge_split_relative"
            else:
                replay_point = baseline_replay_point
                replay_source = baseline_replay_source
        if replay_point is None:
            replay_point = recorded_point
        if merge_split_relative:
            score = scores.get(frame_index)
            target = _target_point(score)
        if score is None or target is None:
            continue
        recorded_passed = _distance(recorded_point, target) <= pass_distance_px
        replay_passed = _distance(replay_point, target) <= pass_distance_px
        total_frames += 1
        recorded_passed_frames += int(recorded_passed)
        replay_passed_frames += int(replay_passed)
        improved_frames += int(replay_passed and not recorded_passed)
        regressed_frames += int(recorded_passed and not replay_passed)
        changed_frames += int(_distance(recorded_point, replay_point) > 1e-6)
        if _details is not None:
            replay_rank = (
                min(range(len(judge_points)), key=lambda index: _distance(judge_points[index], replay_point))
                if judge_points else None
            )
            detail: dict[str, object] = {
                "frame_index": frame_index,
                "target_point": [target[0], target[1]],
                "recorded_point": [recorded_point[0], recorded_point[1]],
                "replay_point": [replay_point[0], replay_point[1]],
                "recorded_passed": recorded_passed,
                "replay_passed": replay_passed,
                "improved": replay_passed and not recorded_passed,
                "regressed": recorded_passed and not replay_passed,
                "changed": _distance(recorded_point, replay_point) > 1e-6,
                "recorded_source": str(target_selection.get("source", "")),
                "replay_source": replay_source,
                "identity_state": identity_state,
                "candidate_count": len(candidates),
                "hypothesis_count": len(hypothesis_points),
                "judge_hypothesis_count": len(judge_points),
                "replay_hypothesis_rank": replay_rank,
                "wide_gate": dict(wide_gate),
                "local_rigid_gate": dict(local_rigid_gate),
                "challenge_guard": dict(challenge_debug),
                "persistent_evidence_quorum": dict(persistent_debug),
            }
            if merge_decision is not None:
                merge_debug = merge_decision.debug
                local_lag = observed_local_lag
                phase_qualified = bool(
                    phase_context is not None and phase_context.phase_qualified
                )
                qualified_anchor_count = (
                    merge_debug.get("qualified_anchor_count")
                    if phase_qualified
                    else None
                )
                detail["merge_split_relative"] = {
                    **merge_debug,
                    "state": merge_decision.state.name,
                    "reason": merge_decision.reason,
                    "background_candidate_id": merge_decision.background_candidate_id,
                    "target_candidate_id": merge_decision.target_candidate_id,
                    "relative_margin": merge_decision.relative_margin,
                    "quorum": dict(merge_quorum_debug),
                    "period": catalog_period,
                    "period_score": catalog_period_score,
                    "local_lag": local_lag,
                    "reference_frame": (
                        frame_index - local_lag if local_lag is not None else None
                    ),
                    "cycle_evidence_reason": cycle_evidence_reason,
                    "local_lag_evidence_reason": local_lag_evidence_reason,
                    "period_recurrence_comparisons": period_recurrence_comparisons,
                    "raw_candidate_count": len(candidates),
                    "stable_cycle_track_count": stable_cycle_track_count,
                    "stable_cycle_track_ids": stable_cycle_track_ids,
                    "stable_cycle_excluded_counts": stable_cycle_excluded_counts,
                    "stable_cycle_exclusion_reasons": stable_cycle_exclusion_reasons,
                    "stable_cycle_frame_shape_reason": stable_cycle_frame_shape_reason,
                    "cycle_input": {
                        "frame_index": frame_index,
                        "candidate_count": len(candidates),
                        "catalog_candidate_count": len(catalog_candidates),
                        "white_anchor_observed": anchor is not None,
                    },
                    "phase_qualified": phase_qualified,
                    "phase_context_active": phase_qualified,
                    "qualified_anchor_count": qualified_anchor_count,
                    "merge_event_id": merge_debug.get("event_id"),
                    "merge_event_context": {
                        "event_id": merge_debug.get("event_id"),
                        "fingerprint_mode": merge_debug.get("fingerprint_mode"),
                        "phase_reference_frame": merge_debug.get(
                            "phase_reference_frame"
                        ),
                    },
                    "selected_split_child_ids": tuple(
                        merge_debug.get("split_child_pair_ids", ())
                    ),
                    "selected_child_ids": tuple(
                        candidate_id
                        for candidate_id in (
                            merge_decision.background_candidate_id,
                            merge_decision.target_candidate_id,
                        )
                        if candidate_id is not None
                    ),
                    "hold_reason": (
                        merge_decision.reason
                        if merge_decision.target_candidate_id is None
                        else None
                    ),
                }
            _details.append(detail)

    return HypothesisSelectionReplaySummary(
        total_frames=total_frames,
        recorded_passed_frames=recorded_passed_frames,
        replay_passed_frames=replay_passed_frames,
        improved_frames=improved_frames,
        regressed_frames=regressed_frames,
        changed_frames=changed_frames,
        wide_selected_frames=wide_selected_frames,
        local_rigid_selected_frames=local_rigid_selected_frames,
    )


def replay_hypothesis_selection_details(
    score_jsonl: str | Path,
    trace_jsonl: str | Path,
    *,
    width: int = 24,
    branch: int = 5,
    diverse_first: bool = True,
    pass_distance_px: float = 24.0,
    judge_hypothesis_limit: int | None = None,
    challenge_confirm_frames: int | None = None,
    challenge_max_step_px: float = 90.0,
    protect_incumbent_sources: tuple[str, ...] = (),
    persistent_evidence_quorum: bool = False,
    merge_split_relative: bool = False,
) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    replay_hypothesis_selection(
        score_jsonl,
        trace_jsonl,
        width=width,
        branch=branch,
        diverse_first=diverse_first,
        pass_distance_px=pass_distance_px,
        judge_hypothesis_limit=judge_hypothesis_limit,
        challenge_confirm_frames=challenge_confirm_frames,
        challenge_max_step_px=challenge_max_step_px,
        protect_incumbent_sources=protect_incumbent_sources,
        persistent_evidence_quorum=persistent_evidence_quorum,
        merge_split_relative=merge_split_relative,
        _details=details,
    )
    return details


def _persistent_challenger(
    *,
    incumbent_point: tuple[float, float] | None,
    hypothesis_points: object,
    candidates: list[Candidate],
    evidence: dict[str, CandidateEvidence],
    preferred_point: tuple[float, float] | None = None,
    anchor_shape: tuple[float, float] | None = None,
    frame_shape: tuple[int, int] | None = None,
) -> tuple[tuple[float, float] | None, dict[str, float | None], dict[str, object]]:
    incumbent = _point(incumbent_point)
    if incumbent is None or not candidates:
        return None, {}, {"reason": "missing_incumbent_or_candidates"}
    if preferred_point is None and not isinstance(hypothesis_points, (list, tuple)):
        return None, {}, {"reason": "missing_hypotheses"}
    incumbent_candidate = min(candidates, key=lambda candidate: _distance(candidate.center, incumbent))
    incumbent_evidence = evidence.get(incumbent_candidate.candidate_id)
    if incumbent_evidence is None:
        return None, {}, {"reason": "missing_incumbent_evidence"}

    rows: list[
        tuple[int, float, tuple[float, float], Candidate, dict[str, float | None]]
    ] = []
    seen_candidate_ids: set[str] = set()
    point_values = (preferred_point,) if preferred_point is not None else hypothesis_points
    for value in point_values:
        point = _point(value)
        if point is None:
            continue
        candidate = min(candidates, key=lambda item: _distance(item.center, point))
        if candidate.candidate_id in seen_candidate_ids:
            continue
        seen_candidate_ids.add(candidate.candidate_id)
        if candidate.candidate_id == incumbent_candidate.candidate_id:
            continue
        challenger_evidence = evidence.get(candidate.candidate_id)
        if challenger_evidence is None:
            continue
        margins = pairwise_persistent_margins(
            incumbent_candidate=incumbent_candidate,
            challenger_candidate=candidate,
            incumbent_evidence=incumbent_evidence,
            challenger_evidence=challenger_evidence,
            candidate_pool=candidates,
            anchor_shape=anchor_shape,
            frame_shape=frame_shape,
        )
        observed = [float(value) for value in margins.values() if value is not None]
        if not observed:
            continue
        positive_count = sum(
            float(margins.get(group) or 0.0) > 0.0
            for group in (
                "background_motion",
                "local_rigid",
                "texture_background",
                "anchor_shape_identity",
            )
        )
        rows.append((positive_count, sum(observed), point, candidate, margins))
    if not rows:
        return None, {}, {"reason": "missing_challenger_evidence"}

    positive_count, net_margin, point, candidate, margins = max(rows, key=lambda row: row[:2])
    return point, margins, {
        "reason": "preferred_baseline_challenger" if preferred_point is not None else "best_persistent_quorum",
        "candidate_id": candidate.candidate_id,
        "point": point,
        "positive_group_count": positive_count,
        "net_margin": net_margin,
        "group_margins": dict(margins),
    }


def _merge_split_group_margins(
    *,
    incumbent_point: tuple[float, float] | None,
    decision: MergeSplitDecision,
    candidates: list[Candidate],
    evidence: dict[str, CandidateEvidence],
    anchor_shape: tuple[float, float] | None,
    frame_shape: tuple[int, int] | None,
) -> dict[str, float | None]:
    if (
        incumbent_point is None
        or decision.target_point is None
        or decision.relative_margin is None
        or not candidates
    ):
        return {}
    incumbent_candidate = min(
        candidates,
        key=lambda candidate: _distance(candidate.center, incumbent_point),
    )
    challenger_candidate = min(
        candidates,
        key=lambda candidate: _distance(candidate.center, decision.target_point),
    )
    incumbent_evidence = evidence.get(incumbent_candidate.candidate_id)
    challenger_evidence = evidence.get(challenger_candidate.candidate_id)
    if incumbent_evidence is None or challenger_evidence is None:
        return {"background_relative_identity": decision.relative_margin}
    pairwise = pairwise_persistent_margins(
        incumbent_candidate=incumbent_candidate,
        challenger_candidate=challenger_candidate,
        incumbent_evidence=incumbent_evidence,
        challenger_evidence=challenger_evidence,
        candidate_pool=candidates,
        anchor_shape=anchor_shape,
        frame_shape=frame_shape,
    )
    return {
        "background_relative_identity": decision.relative_margin,
        "background_motion": pairwise.get("background_motion"),
        "anchor_shape_identity": pairwise.get("anchor_shape_identity"),
    }


def _stable_candidate_scale(candidates: list[Candidate]) -> float:
    diagonals = [
        hypot(candidate.bbox[2] - candidate.bbox[0], candidate.bbox[3] - candidate.bbox[1])
        for candidate in candidates
    ]
    return max(1.0, float(median(diagonals))) if diagonals else 1.0


def _stable_candidate_area(candidates: list[Candidate]) -> float:
    areas = [
        max(1.0, candidate.bbox[2] - candidate.bbox[0])
        * max(1.0, candidate.bbox[3] - candidate.bbox[1])
        for candidate in candidates
    ]
    return max(1.0, float(median(areas))) if areas else 1.0


def _stable_target_area(
    candidates: list[Candidate],
    *,
    incumbent_point: tuple[float, float] | None,
    anchor_shapes: list[tuple[float, float]],
) -> float:
    anchor_shape = _median_anchor_shape(anchor_shapes)
    if anchor_shape is not None:
        return max(1.0, float(anchor_shape[0]))
    if incumbent_point is not None and candidates:
        nearest = min(
            candidates,
            key=lambda candidate: _distance(candidate.center, incumbent_point),
        )
        return _candidate_shape(nearest)[0]
    return _stable_candidate_area(candidates)


def _candidate_shape(candidate: Candidate) -> tuple[float, float]:
    width = max(1.0, candidate.bbox[2] - candidate.bbox[0])
    height = max(1.0, candidate.bbox[3] - candidate.bbox[1])
    return width * height, width / height


_CYCLE_ASSOCIATION_QUALITY_LIMIT = 0.75
_CYCLE_ASSOCIATION_AMBIGUITY_MARGIN = 0.15
_MAX_CYCLE_LOOP_RESIDUAL = 0.25
_TRACK_ASSOCIATION_QUALITY_LIMIT = 1.5
_MIN_CYCLE_ASSOCIATIONS = 3
_MIN_CYCLE_COVERAGE = 0.95
_MAX_CYCLE_GAP_RATIO = 0.05


@dataclass
class _StableCycleTrack:
    track_id: str
    observations: dict[int, Candidate]
    excluded_reason: str | None = None


@dataclass(frozen=True)
class _FrozenCycleObservation:
    track_id: str
    candidate: PuzzleCandidate
    candidate_id: str | None = None


class _StableCycleTracks:
    """백색 준비 구간에서만 안정 배경 후보를 고정하는 좁은 증거 수집기."""

    def __init__(self, *, frame_shape: tuple[int, int] | None) -> None:
        self._frame_shape = frame_shape
        self._tracks: dict[str, _StableCycleTrack] = {}
        self._frozen_track_ids: tuple[str, ...] = ()
        self._frozen = False
        self._next_track_number = 1
        self._episode_start: int | None = None
        self._episode_end: int | None = None

    @property
    def frame_shape_reason(self) -> str:
        return "observed" if _valid_cycle_frame_shape(self._frame_shape) else "frame_shape_unavailable"

    @property
    def frozen_track_ids(self) -> tuple[str, ...]:
        return self._frozen_track_ids

    @property
    def exclusion_reasons(self) -> dict[str, str]:
        return {
            track_id: track.excluded_reason
            for track_id, track in self._tracks.items()
            if track.excluded_reason is not None
        }

    @property
    def excluded_counts(self) -> dict[str, int]:
        return dict(Counter(self.exclusion_reasons.values()))

    @property
    def period_failure_reason(self) -> str:
        if self.frame_shape_reason != "observed":
            return self.frame_shape_reason
        reasons = tuple(self.exclusion_reasons.values())
        if any(
            reason in {
                "association_ambiguous",
                "association_crossing",
                "association_disagreement",
                "association_permutation",
            }
            for reason in reasons
        ):
            return "period_association_ambiguous"
        if "association_quality" in reasons:
            return "period_association_quality"
        if any(
            reason in {
                "association_missing",
                "association_unassigned",
                "cycle_clipped",
                "cycle_coverage",
                "cycle_gap",
            }
            for reason in reasons
        ):
            return "period_association_incomplete"
        return "insufficient_stable_cycle_tracks"

    def update(self, frame_index: int, candidates: Sequence[Candidate]) -> None:
        self._record_episode_frame(frame_index)
        if self.frame_shape_reason != "observed":
            return
        if not self._tracks:
            for candidate in candidates:
                self._start_track(frame_index, candidate)
            return

        candidate_rows = list(candidates)
        active_tracks = {
            track_id: track
            for track_id, track in self._tracks.items()
            if track.excluded_reason is None
            and (not self._frozen or track_id in self._frozen_track_ids)
        }
        assignments, rejected, blocked_indexes = _global_track_assignment(
            active_tracks,
            candidate_rows,
            _track_position_quality,
        )
        predicted: dict[str, int] = {}
        for left_track_id, left_index in assignments.items():
            for right_track_id, right_index in assignments.items():
                if left_track_id >= right_track_id:
                    continue
                if _track_segments_cross(
                    active_tracks[left_track_id],
                    candidate_rows[left_index],
                    active_tracks[right_track_id],
                    candidate_rows[right_index],
                ):
                    rejected[left_track_id] = "association_crossing"
                    rejected[right_track_id] = "association_crossing"
                    blocked_indexes.update((left_index, right_index))
        predicted_tracks = {
            track_id: track
            for track_id, track in active_tracks.items()
            if len(track.observations) >= 2
            and track_id in assignments
            and track_id not in rejected
        }
        if predicted_tracks:
            predicted_indexes = tuple(range(len(candidate_rows)))
            if self._frozen:
                predicted_indexes = tuple(
                    sorted(
                        {
                            candidate_index
                            for track_id, candidate_index in assignments.items()
                            if track_id in predicted_tracks
                        }
                    )
                )
            predicted_candidates = [
                candidate_rows[candidate_index]
                for candidate_index in predicted_indexes
            ]
            predicted, predicted_rejected, predicted_blocked = _global_track_assignment(
                predicted_tracks,
                predicted_candidates,
                _track_prediction_quality,
            )
            predicted = {
                track_id: predicted_indexes[candidate_index]
                for track_id, candidate_index in predicted.items()
            }
            rejected.update(predicted_rejected)
            blocked_indexes.update(
                predicted_indexes[candidate_index]
                for candidate_index in predicted_blocked
            )
            for track_id, candidate_index in predicted.items():
                current_index = assignments.get(track_id)
                if current_index is not None and current_index != candidate_index:
                    rejected[track_id] = "association_permutation"
                    blocked_indexes.update((current_index, candidate_index))
                    for other_track_id, other_index in assignments.items():
                        if other_index == candidate_index:
                            rejected[other_track_id] = "association_permutation"
                            blocked_indexes.add(other_index)
            for left_track_id, left_index in predicted.items():
                for right_track_id, right_index in predicted.items():
                    if left_track_id >= right_track_id:
                        continue
                    if _track_segments_cross(
                        predicted_tracks[left_track_id],
                        candidate_rows[left_index],
                        predicted_tracks[right_track_id],
                        candidate_rows[right_index],
                    ):
                        rejected.setdefault(left_track_id, "association_crossing")
                        rejected.setdefault(right_track_id, "association_crossing")
                        blocked_indexes.update((left_index, right_index))

        for track_id in rejected:
            candidate_index = assignments.get(track_id)
            if candidate_index is not None:
                blocked_indexes.add(candidate_index)
            candidate_index = predicted.get(track_id)
            if candidate_index is not None:
                blocked_indexes.add(candidate_index)

        accepted_assignments = {
            track_id: candidate_index
            for track_id, candidate_index in assignments.items()
            if track_id not in rejected
            and not _cycle_candidate_clipped(candidate_rows[candidate_index], self._frame_shape)
        }
        for track_id, candidate_index in assignments.items():
            if _cycle_candidate_clipped(candidate_rows[candidate_index], self._frame_shape):
                rejected[track_id] = "cycle_clipped"
                blocked_indexes.add(candidate_index)
        for track_id, track in active_tracks.items():
            if track_id in accepted_assignments:
                continue
            track.excluded_reason = rejected.get(track_id, "association_missing")
        for track_id, candidate_index in accepted_assignments.items():
            self._tracks[track_id].observations[frame_index] = candidate_rows[candidate_index]

        matched_indexes = set(accepted_assignments.values())
        if not self._frozen:
            for candidate_index, candidate in enumerate(candidate_rows):
                if candidate_index not in matched_indexes and candidate_index not in blocked_indexes:
                    self._start_track(frame_index, candidate)

    def freeze(self) -> dict[int, tuple[_FrozenCycleObservation, ...]]:
        if self._frozen:
            return self._frozen_observations()
        if self.frame_shape_reason != "observed":
            self._frozen = True
            return {}
        episode_frames = self._episode_frames()
        for track in self._tracks.values():
            if track.excluded_reason is not None:
                continue
            coverage = sum(
                frame_index in track.observations for frame_index in episode_frames
            ) / max(1, len(episode_frames))
            largest_gap = _largest_cycle_track_gap(episode_frames, track.observations)
            if coverage < _MIN_CYCLE_COVERAGE:
                track.excluded_reason = "cycle_coverage"
            elif largest_gap / max(1, len(episode_frames)) > _MAX_CYCLE_GAP_RATIO:
                track.excluded_reason = "cycle_gap"
        self._frozen_track_ids = tuple(
            track_id
            for track_id, track in self._tracks.items()
            if track.excluded_reason is None
        )
        self._frozen = True
        return self._frozen_observations()

    def _record_episode_frame(self, frame_index: int) -> None:
        if self._episode_start is None:
            self._episode_start = frame_index
        self._episode_end = frame_index

    def _episode_frames(self) -> tuple[int, ...]:
        if self._episode_start is None or self._episode_end is None:
            return ()
        return tuple(range(self._episode_start, self._episode_end + 1))

    def frozen_observation(
        self,
        frame_index: int,
    ) -> tuple[tuple[_FrozenCycleObservation, ...] | None, str]:
        if not self._frozen_track_ids:
            return None, "missing"
        observations: list[_FrozenCycleObservation] = []
        for track_id in self._frozen_track_ids:
            track = self._tracks[track_id]
            if track.excluded_reason is not None:
                return None, _frozen_failure_reason(track.excluded_reason)
            candidate = track.observations.get(frame_index)
            if candidate is None:
                return None, "missing"
            observations.append(
                _FrozenCycleObservation(
                    track_id,
                    _catalog_candidate(candidate),
                    candidate.candidate_id,
                )
            )
        return tuple(observations), "observed"

    def _start_track(self, frame_index: int, candidate: Candidate) -> None:
        track_id = f"cycle-track-{self._next_track_number}"
        self._next_track_number += 1
        self._tracks[track_id] = _StableCycleTrack(
            track_id=track_id,
            observations={frame_index: candidate},
            excluded_reason=(
                "cycle_clipped"
                if _cycle_candidate_clipped(candidate, self._frame_shape)
                else None
            ),
        )

    def _frozen_observations(self) -> dict[int, tuple[_FrozenCycleObservation, ...]]:
        if not self._frozen_track_ids:
            return {}
        shared_frames = sorted(
            set.intersection(
                *[
                    set(self._tracks[track_id].observations)
                    for track_id in self._frozen_track_ids
                ]
            )
        )
        return {
            frame_index: tuple(
                _FrozenCycleObservation(
                    track_id,
                    _catalog_candidate(self._tracks[track_id].observations[frame_index]),
                    self._tracks[track_id].observations[frame_index].candidate_id,
                )
                for track_id in self._frozen_track_ids
            )
            for frame_index in shared_frames
        }


def _global_track_assignment(
    tracks: dict[str, _StableCycleTrack],
    candidates: Sequence[Candidate],
    quality_for: Any,
) -> tuple[dict[str, int], dict[str, str], set[int]]:
    track_ids = tuple(sorted(tracks))
    if not track_ids:
        return {}, {}, set()

    candidate_count = len(candidates)
    unmatched_cost = _TRACK_ASSOCIATION_QUALITY_LIMIT + 1.0
    forbidden_cost = unmatched_cost * max(4.0, float(len(track_ids) + 1))
    qualities = tuple(
        tuple(float(quality_for(tracks[track_id], candidate)) for candidate in candidates)
        for track_id in track_ids
    )
    costs: list[list[float]] = []
    for track_index, row in enumerate(qualities):
        candidate_costs = [
            quality if quality <= _TRACK_ASSOCIATION_QUALITY_LIMIT else forbidden_cost
            for quality in row
        ]
        dummy_costs = [forbidden_cost] * len(track_ids)
        dummy_costs[track_index] = unmatched_cost
        costs.append(candidate_costs + dummy_costs)

    best = _minimum_cost_row_assignment(costs)
    if best is None:
        return (
            {},
            {track_id: "association_missing" for track_id in track_ids},
            set(),
        )
    best_cost, best_columns = best
    matched_count = sum(column < candidate_count for column in best_columns)

    alternatives: list[tuple[float, tuple[int, ...]]] = []
    for track_index, selected_column in enumerate(best_columns):
        alternative_costs = [row[:] for row in costs]
        alternative_costs[track_index][selected_column] = forbidden_cost
        alternative = _minimum_cost_row_assignment(alternative_costs)
        if alternative is not None:
            alternatives.append(alternative)
    rejected: dict[str, str] = {}
    blocked_indexes: set[int] = set()
    near_alternatives = tuple(
        alternative
        for alternative in alternatives
        if (alternative[0] - best_cost) / max(1, matched_count)
        <= _CYCLE_ASSOCIATION_AMBIGUITY_MARGIN
    )
    ambiguous_track_indexes = {
        track_index
        for _alternative_cost, alternative_columns in near_alternatives
        for track_index, (best_column, alternative_column) in enumerate(
            zip(best_columns, alternative_columns)
        )
        if best_column != alternative_column
    }
    for track_index in ambiguous_track_indexes:
        rejected[track_ids[track_index]] = "association_ambiguous"
        related_columns = {best_columns[track_index]}
        related_columns.update(
            columns[track_index]
            for _cost, columns in near_alternatives
        )
        blocked_indexes.update(
            column for column in related_columns if column < candidate_count
        )

    assignments: dict[str, int] = {}
    for track_index, (track_id, column) in enumerate(zip(track_ids, best_columns)):
        if track_index in ambiguous_track_indexes:
            continue
        if column < candidate_count:
            assignments[track_id] = column
            continue
        row = qualities[track_index]
        rejected[track_id] = (
            "association_unassigned"
            if any(
                quality <= _TRACK_ASSOCIATION_QUALITY_LIMIT
                for quality in row
            )
            else ("association_quality" if candidates else "association_missing")
        )
    return assignments, rejected, blocked_indexes


def _minimum_cost_row_assignment(
    costs: Sequence[Sequence[float]],
) -> tuple[float, tuple[int, ...]] | None:
    row_count = len(costs)
    if row_count == 0:
        return 0.0, ()
    column_count = len(costs[0])
    if column_count < row_count or any(len(row) != column_count for row in costs):
        return None

    row_potential = [0.0] * (row_count + 1)
    column_potential = [0.0] * (column_count + 1)
    column_owner = [0] * (column_count + 1)
    predecessor = [0] * (column_count + 1)
    for row_index in range(1, row_count + 1):
        column_owner[0] = row_index
        minimum = [float("inf")] * (column_count + 1)
        used = [False] * (column_count + 1)
        current_column = 0
        while True:
            used[current_column] = True
            current_row = column_owner[current_column]
            delta = float("inf")
            next_column = 0
            for column_index in range(1, column_count + 1):
                if used[column_index]:
                    continue
                reduced = (
                    float(costs[current_row - 1][column_index - 1])
                    - row_potential[current_row]
                    - column_potential[column_index]
                )
                if reduced < minimum[column_index]:
                    minimum[column_index] = reduced
                    predecessor[column_index] = current_column
                if minimum[column_index] < delta:
                    delta = minimum[column_index]
                    next_column = column_index
            if not isfinite(delta):
                return None
            for column_index in range(column_count + 1):
                if used[column_index]:
                    row_potential[column_owner[column_index]] += delta
                    column_potential[column_index] -= delta
                else:
                    minimum[column_index] -= delta
            current_column = next_column
            if column_owner[current_column] == 0:
                break
        while True:
            previous_column = predecessor[current_column]
            column_owner[current_column] = column_owner[previous_column]
            current_column = previous_column
            if current_column == 0:
                break

    assignment = [-1] * row_count
    for column_index in range(1, column_count + 1):
        owner = column_owner[column_index]
        if owner != 0:
            assignment[owner - 1] = column_index - 1
    if any(column < 0 for column in assignment):
        return None
    total_cost = sum(
        float(costs[row_index][column])
        for row_index, column in enumerate(assignment)
    )
    return total_cost, tuple(assignment)


def _track_position_quality(track: _StableCycleTrack, candidate: Candidate) -> float:
    previous = track.observations[max(track.observations)]
    return _cycle_association_quality(
        _catalog_candidate(previous),
        _catalog_candidate(candidate),
    )


def _track_prediction_quality(track: _StableCycleTrack, candidate: Candidate) -> float:
    observed_frames = sorted(track.observations)
    previous = track.observations[observed_frames[-2]]
    current = track.observations[observed_frames[-1]]
    predicted = _predicted_cycle_position(
        _catalog_candidate(previous),
        _catalog_candidate(current),
    )
    current_model = _catalog_candidate(current)
    candidate_model = _catalog_candidate(candidate)
    scale = max(1.0, hypot(current_model.w, current_model.h, candidate_model.w, candidate_model.h))
    position_residual = hypot(
        predicted[0] - candidate_model.cx,
        predicted[1] - candidate_model.cy,
    ) / scale
    shape_residual = max(
        abs(current_model.w - candidate_model.w) / max(1.0, current_model.w, candidate_model.w),
        abs(current_model.h - candidate_model.h) / max(1.0, current_model.h, candidate_model.h),
    )
    return position_residual + shape_residual


def _track_segments_cross(
    left_track: _StableCycleTrack,
    left_candidate: Candidate,
    right_track: _StableCycleTrack,
    right_candidate: Candidate,
) -> bool:
    left_start = left_track.observations[max(left_track.observations)].center
    right_start = right_track.observations[max(right_track.observations)].center
    return _segments_properly_intersect(
        left_start,
        left_candidate.center,
        right_start,
        right_candidate.center,
    )


def _segments_properly_intersect(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
) -> bool:
    def orientation(
        origin: tuple[float, float],
        left: tuple[float, float],
        right: tuple[float, float],
    ) -> float:
        return (
            (left[0] - origin[0]) * (right[1] - origin[1])
            - (left[1] - origin[1]) * (right[0] - origin[0])
        )

    first_left = orientation(first_start, first_end, second_start)
    first_right = orientation(first_start, first_end, second_end)
    second_left = orientation(second_start, second_end, first_start)
    second_right = orientation(second_start, second_end, first_end)
    if first_left * first_right < 0.0 and second_left * second_right < 0.0:
        return True

    def on_segment(
        start: tuple[float, float],
        end: tuple[float, float],
        point: tuple[float, float],
    ) -> bool:
        return (
            min(start[0], end[0]) <= point[0] <= max(start[0], end[0])
            and min(start[1], end[1]) <= point[1] <= max(start[1], end[1])
        )

    return bool(
        (first_left == 0.0 and on_segment(first_start, first_end, second_start))
        or (first_right == 0.0 and on_segment(first_start, first_end, second_end))
        or (second_left == 0.0 and on_segment(second_start, second_end, first_start))
        or (second_right == 0.0 and on_segment(second_start, second_end, first_end))
    )


def _valid_cycle_frame_shape(frame_shape: tuple[int, int] | None) -> bool:
    return bool(
        isinstance(frame_shape, tuple)
        and len(frame_shape) == 2
        and type(frame_shape[0]) is int
        and type(frame_shape[1]) is int
        and frame_shape[0] > 0
        and frame_shape[1] > 0
    )


def _catalog_candidate(candidate: Candidate) -> PuzzleCandidate:
    return PuzzleCandidate(
        cx=candidate.center[0],
        cy=candidate.center[1],
        score=candidate.score,
        w=max(1.0, candidate.bbox[2] - candidate.bbox[0]),
        h=max(1.0, candidate.bbox[3] - candidate.bbox[1]),
    )


def _frozen_catalog_candidates(
    observations: Sequence[_FrozenCycleObservation],
) -> tuple[PuzzleCandidate, ...]:
    return tuple(observation.candidate for observation in observations)


def _resolver_cycle_observations(
    frame_index: int,
    observations: Sequence[_FrozenCycleObservation],
) -> tuple[StableCycleObservation, ...]:
    rows: list[StableCycleObservation] = []
    for observation in observations:
        candidate = observation.candidate
        rows.append(
            StableCycleObservation(
                track_id=observation.track_id,
                frame_index=int(frame_index),
                candidate_id=(
                    observation.candidate_id
                    or f"{observation.track_id}@{int(frame_index)}"
                ),
                point=(candidate.cx, candidate.cy),
                bbox=(
                    candidate.cx - candidate.w / 2.0,
                    candidate.cy - candidate.h / 2.0,
                    candidate.cx + candidate.w / 2.0,
                    candidate.cy + candidate.h / 2.0,
                ),
            )
        )
    return tuple(rows)


def _cycle_candidate_clipped(
    candidate: Candidate,
    frame_shape: tuple[int, int] | None,
) -> bool:
    if frame_shape is None:
        return False
    height, width = frame_shape
    x1, y1, x2, y2 = candidate.bbox
    shape_scale = max(1e-6, x2 - x1, y2 - y1)
    safe_margin = 0.5 * shape_scale
    return (
        x1 < safe_margin
        or y1 < safe_margin
        or float(width) - x2 < safe_margin
        or float(height) - y2 < safe_margin
    )


def _largest_cycle_track_gap(
    observed_frames: Sequence[int],
    observations: dict[int, Candidate],
) -> int:
    largest_gap = 0
    current_gap = 0
    for frame_index in observed_frames:
        if frame_index in observations:
            largest_gap = max(largest_gap, current_gap)
            current_gap = 0
        else:
            current_gap += 1
    return max(largest_gap, current_gap)


def _frozen_failure_reason(excluded_reason: str) -> str:
    if excluded_reason == "cycle_clipped":
        return "clipped"
    if excluded_reason in {"association_ambiguous", "association_crossing"}:
        return "ambiguous"
    return "missing"


def _catalog_candidates(candidates: Sequence[Candidate]) -> tuple[PuzzleCandidate, ...]:
    return tuple(_catalog_candidate(candidate) for candidate in candidates)


def _observed_episode_period(
    catalog: BackgroundCatalog | None,
    observations: dict[int, tuple[_FrozenCycleObservation, ...]],
) -> tuple[int | None, float | None, str, int]:
    observed_frames = sorted(observations)
    if catalog is None or len(observed_frames) < 2:
        return None, None, "insufficient_episode_evidence", 0
    first_frame = observed_frames[0]
    last_frame = observed_frames[-1]
    if last_frame - first_frame < 2:
        return None, None, "insufficient_episode_evidence", 0
    accepted: list[tuple[float, int, int, float]] = []
    failures: list[str] = []
    for period in range(2, last_frame - first_frame + 1):
        observed_period, score = catalog.estimate_period(
            prep_end=last_frame,
            min_lag=period,
            max_lag=period,
        )
        if observed_period != period or not isfinite(score):
            continue
        supported, reason, comparisons = _period_recurrence_support(
            observations,
            period,
        )
        if supported:
            recurrence_residual = _period_recurrence_residual(
                observations,
                period,
            )
            if recurrence_residual is None:
                continue
            if recurrence_residual > _MAX_CYCLE_LOOP_RESIDUAL:
                failures.append("period_loop_residual")
                continue
            accepted.append(
                (recurrence_residual, period, comparisons, float(score))
            )
        else:
            failures.append(reason)
    if accepted:
        accepted.sort()
        best_residual, period, comparisons, catalog_score = accepted[0]
        alternatives = [
            row
            for row in accepted[1:]
            if not (row[1] > period and row[1] % period == 0)
        ]
        if (
            alternatives
            and alternatives[0][0] - best_residual
            <= _CYCLE_ASSOCIATION_AMBIGUITY_MARGIN
        ):
            return None, None, "period_recurrence_ambiguous", 0
        return period, catalog_score, "observed_period", comparisons
    if "period_association_ambiguous" in failures:
        return None, None, "period_association_ambiguous", 0
    if "period_association_permutation" in failures:
        return None, None, "period_association_permutation", 0
    if "period_loop_residual" in failures:
        return None, None, "period_loop_residual", 0
    if "period_association_quality" in failures:
        return None, None, "period_association_quality", 0
    if "period_association_incomplete" in failures:
        return None, None, "period_association_incomplete", 0
    if failures:
        return None, None, "period_association_quality", 0
    return None, None, "insufficient_episode_evidence", 0


def _period_recurrence_support(
    observations: dict[int, tuple[_FrozenCycleObservation, ...]],
    period: int,
) -> tuple[bool, str, int]:
    failures: list[str] = []
    observed_pair = False
    comparisons = 0
    for reference_frame in sorted(observations):
        reference = observations.get(reference_frame)
        current = observations.get(reference_frame + period)
        if reference is None or current is None:
            continue
        observed_pair = True
        current_ok, current_reason, _assignment = _frozen_track_assignment(
            reference,
            current,
        )
        if current_ok:
            comparisons += 1
        else:
            failures.append(current_reason)
    if not observed_pair:
        return False, "period_association_incomplete", 0
    if "ambiguous" in failures:
        return False, "period_association_ambiguous", 0
    if "cardinality" in failures:
        return False, "period_association_incomplete", 0
    if "incomplete" in failures:
        return False, "period_association_incomplete", 0
    if "permutation" in failures:
        return False, "period_association_permutation", 0
    if not failures:
        return True, "observed_period", comparisons
    return False, "period_association_quality", 0


def _period_recurrence_residual(
    observations: dict[int, tuple[_FrozenCycleObservation, ...]],
    period: int,
) -> float | None:
    residuals: list[float] = []
    for reference_frame in sorted(observations):
        reference = observations.get(reference_frame)
        current = observations.get(reference_frame + period)
        residual = _frozen_pair_residual(reference, current)
        if residual is not None:
            residuals.append(residual)
    return float(median(residuals)) if residuals else None


def _local_lag_temporal_support(
    observations: dict[int, tuple[_FrozenCycleObservation, ...]],
    frame_index: int,
    lag: int,
) -> tuple[bool, str]:
    reference = observations.get(frame_index - lag)
    current = observations.get(frame_index)
    current_ok, current_reason, _assignment = _frozen_track_assignment(
        reference,
        current,
    )
    if not current_ok:
        return False, f"association_{current_reason}"
    selected_residual = _frozen_pair_residual(reference, current)
    if selected_residual is None:
        return False, "association_incomplete"
    if selected_residual > _MAX_CYCLE_LOOP_RESIDUAL:
        return False, "loop_residual"

    alternatives: list[tuple[float, int]] = []
    earliest_frame = min(observations, default=frame_index)
    for alternative_lag in range(2, frame_index - earliest_frame + 1):
        if alternative_lag == lag or (
            alternative_lag > lag and alternative_lag % lag == 0
        ):
            continue
        alternative_reference = observations.get(frame_index - alternative_lag)
        alternative_residual = _frozen_pair_residual(
            alternative_reference,
            current,
        )
        if alternative_residual is not None:
            alternatives.append((alternative_residual, alternative_lag))
    if (
        alternatives
        and min(alternatives)[0] - selected_residual
        <= _CYCLE_ASSOCIATION_AMBIGUITY_MARGIN
    ):
        return False, "nonunique_recurrence"
    return True, "observed"


def _frozen_pair_residual(
    reference: Sequence[_FrozenCycleObservation] | None,
    current: Sequence[_FrozenCycleObservation] | None,
) -> float | None:
    assignment_ok, _reason, _assignment = _frozen_track_assignment(
        reference,
        current,
    )
    if not assignment_ok or reference is None or current is None:
        return None
    reference_by_id = {
        observation.track_id: observation.candidate for observation in reference
    }
    current_by_id = {
        observation.track_id: observation.candidate for observation in current
    }
    return float(
        median(
            _cycle_association_quality(
                reference_by_id[track_id],
                current_by_id[track_id],
            )
            for track_id in reference_by_id
        )
    )


def _frozen_track_assignment(
    reference: Sequence[_FrozenCycleObservation] | None,
    current: Sequence[_FrozenCycleObservation] | None,
) -> tuple[bool, str, tuple[int, ...]]:
    if (
        not reference
        or not current
        or len(reference) < _MIN_CYCLE_ASSOCIATIONS
        or len(reference) != len(current)
    ):
        return False, "incomplete", ()
    reference_by_id = {observation.track_id: observation.candidate for observation in reference}
    current_by_id = {observation.track_id: observation.candidate for observation in current}
    if len(reference_by_id) != len(reference) or set(reference_by_id) != set(current_by_id):
        return False, "permutation", ()
    track_ids = tuple(observation.track_id for observation in reference)
    if tuple(observation.track_id for observation in current) != track_ids:
        return False, "permutation", ()
    for track_id in track_ids:
        if (
            _cycle_association_quality(
                reference_by_id[track_id],
                current_by_id[track_id],
            )
            > _CYCLE_ASSOCIATION_QUALITY_LIMIT
        ):
            return False, "quality", ()
    return True, "observed", tuple(range(len(track_ids)))


def _cycle_candidate_assignment(
    reference: Sequence[PuzzleCandidate] | None,
    current: Sequence[PuzzleCandidate] | None,
    *,
    require_equal_cardinality: bool = True,
) -> tuple[bool, str, float | None, tuple[int, ...]]:
    if not reference or not current or len(reference) < _MIN_CYCLE_ASSOCIATIONS:
        return False, "incomplete", None, ()
    if require_equal_cardinality and len(reference) != len(current):
        return False, "cardinality", None, ()
    if not require_equal_cardinality and len(current) < len(reference):
        return False, "incomplete", None, ()
    if _has_ambiguous_cycle_candidates(reference) or _has_ambiguous_cycle_candidates(
        current
    ):
        return False, "ambiguous", None, ()

    forward: list[int] = []
    forward_qualities: list[float] = []
    for candidate in reference:
        quality, index, ambiguous = _unique_cycle_match(candidate, current)
        if quality is None:
            return False, "quality", None, ()
        if ambiguous:
            return False, "ambiguous", quality, ()
        forward.append(index)
        forward_qualities.append(quality)
    if len(set(forward)) != len(forward):
        return False, "ambiguous", max(forward_qualities), ()

    reverse: list[int] = []
    for candidate in current:
        quality, index, ambiguous = _unique_cycle_match(candidate, reference)
        if quality is None:
            if require_equal_cardinality:
                return False, "quality", None, ()
            reverse.append(-1)
            continue
        if ambiguous:
            return False, "ambiguous", quality, ()
        reverse.append(index)
    if any(reverse[current_index] != reference_index for reference_index, current_index in enumerate(forward)):
        return False, "ambiguous", max(forward_qualities), ()
    return True, "observed", max(forward_qualities), tuple(forward)


def _has_ambiguous_cycle_candidates(candidates: Sequence[PuzzleCandidate]) -> bool:
    return any(
        _cycle_association_quality(left, right)
        <= _CYCLE_ASSOCIATION_AMBIGUITY_MARGIN
        for left_index, left in enumerate(candidates)
        for right in candidates[left_index + 1 :]
    )


def _unique_cycle_match(
    reference: PuzzleCandidate,
    candidates: Sequence[PuzzleCandidate],
) -> tuple[float | None, int, bool]:
    qualities = sorted(
        (_cycle_association_quality(reference, candidate), index)
        for index, candidate in enumerate(candidates)
    )
    best_quality, best_index = qualities[0]
    if best_quality > _CYCLE_ASSOCIATION_QUALITY_LIMIT:
        return None, best_index, False
    ambiguous = (
        len(qualities) > 1
        and qualities[1][0] <= _CYCLE_ASSOCIATION_QUALITY_LIMIT
        and qualities[1][0] - best_quality
        <= _CYCLE_ASSOCIATION_AMBIGUITY_MARGIN
    )
    return best_quality, best_index, ambiguous


def _temporal_assignment_consistent(
    previous: Sequence[PuzzleCandidate],
    current: Sequence[PuzzleCandidate],
    following: Sequence[PuzzleCandidate],
    previous_assignment: Sequence[int],
    following_assignment: Sequence[int],
) -> tuple[bool, str]:
    for previous_index, current_index in enumerate(previous_assignment):
        following_index = following_assignment[current_index]
        predicted = _predicted_cycle_position(
            previous[previous_index],
            current[current_index],
        )
        quality, predicted_index, ambiguous = _unique_predicted_match(
            predicted,
            current[current_index],
            following,
        )
        if quality is None:
            return False, "quality"
        if ambiguous:
            return False, "ambiguous"
        if predicted_index != following_index:
            return False, "permutation"
    return True, "observed"


def _predicted_cycle_position(
    previous: PuzzleCandidate,
    current: PuzzleCandidate,
) -> tuple[float, float]:
    return (
        2.0 * current.cx - previous.cx,
        2.0 * current.cy - previous.cy,
    )


def _unique_predicted_match(
    predicted: tuple[float, float],
    current: PuzzleCandidate,
    candidates: Sequence[PuzzleCandidate],
) -> tuple[float | None, int, bool]:
    scale = max(1.0, hypot(current.w, current.h))
    qualities = sorted(
        (
            hypot(predicted[0] - candidate.cx, predicted[1] - candidate.cy) / scale,
            index,
        )
        for index, candidate in enumerate(candidates)
    )
    best_quality, best_index = qualities[0]
    if best_quality > _CYCLE_ASSOCIATION_QUALITY_LIMIT:
        return None, best_index, False
    ambiguous = (
        len(qualities) > 1
        and qualities[1][0] <= _CYCLE_ASSOCIATION_QUALITY_LIMIT
        and qualities[1][0] - best_quality
        <= _CYCLE_ASSOCIATION_AMBIGUITY_MARGIN
    )
    return best_quality, best_index, ambiguous


def _cycle_association_quality(
    reference: PuzzleCandidate,
    current: PuzzleCandidate,
) -> float:
    reference_scale = hypot(reference.w, reference.h)
    current_scale = hypot(current.w, current.h)
    scale = max(1.0, reference_scale, current_scale)
    position_residual = hypot(reference.cx - current.cx, reference.cy - current.cy) / scale
    shape_residual = max(
        abs(reference.w - current.w) / max(1.0, reference.w, current.w),
        abs(reference.h - current.h) / max(1.0, reference.h, current.h),
    )
    return position_residual + shape_residual


def _median_anchor_shape(
    anchor_shapes: list[tuple[float, float]],
) -> tuple[float, float] | None:
    if not anchor_shapes:
        return None
    return (
        float(median(shape[0] for shape in anchor_shapes)),
        float(median(shape[1] for shape in anchor_shapes)),
    )


def sweep_hypothesis_suite(
    suite_root: str | Path,
    output_dir: str | Path,
    *,
    pass_distance_px: float = 24.0,
    variants: tuple[HypothesisVariant, ...] = DEFAULT_VARIANTS,
) -> dict[str, object]:
    root = Path(suite_root)
    seed_rows: list[dict[str, object]] = []
    for seed_dir in sorted(root.glob("seed_[0-9][0-9]")):
        score_path = next(seed_dir.rglob("score.jsonl"), None)
        trace_path = next(seed_dir.rglob("trace.jsonl"), None)
        if score_path is None or trace_path is None:
            continue
        score_rows = _read_jsonl(score_path)
        trace_rows = _read_jsonl(trace_path)
        for variant in variants:
            summary = _replay_rows(
                score_rows,
                trace_rows,
                width=variant.width,
                branch=variant.branch,
                diverse_first=variant.diverse_first,
                pass_distance_px=pass_distance_px,
            )
            seed_rows.append({
                "seed": seed_dir.name,
                "variant": variant.name,
                "width": variant.width,
                "branch": variant.branch,
                "diverse_first": variant.diverse_first,
                **asdict(summary),
            })

    variant_rows: list[dict[str, object]] = []
    for variant in variants:
        rows = [row for row in seed_rows if row["variant"] == variant.name]
        variant_rows.append({
            "variant": variant.name,
            "width": variant.width,
            "branch": variant.branch,
            "diverse_first": variant.diverse_first,
            **{
                field: sum(int(row[field]) for row in rows)
                for field in HypothesisReplaySummary.__dataclass_fields__
            },
        })

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "studio_hypothesis_shadow.md"
    xlsx_path = output / "studio_hypothesis_shadow.xlsx"
    report_path.write_text(_render_report(variant_rows, seed_rows), encoding="utf-8")
    _write_xlsx(xlsx_path, variant_rows, seed_rows)
    return {
        "variants": variant_rows,
        "seeds": seed_rows,
        "report_path": report_path,
        "xlsx_path": xlsx_path,
    }


def _replay_rows(
    score_rows: list[dict[str, Any]],
    trace_rows: list[dict[str, Any]],
    *,
    width: int,
    branch: int,
    diverse_first: bool,
    pass_distance_px: float,
) -> HypothesisReplaySummary:
    scores = {
        frame_index: row
        for row in score_rows
        if (frame_index := _optional_int(row.get("solver_frame_index"))) is not None
    }
    events = _events_by_frame(trace_rows)
    candidate_frames = sorted(
        frame_index
        for frame_index, event_type in events
        if event_type == "CANDIDATES"
    )
    tracker = TransparentKinematicBeamTracker(
        width=width,
        branch=branch,
        cost_decay=1.0,
        acceleration_weight=0.5,
        yolo_penalty_weight=0.0,
        diverse_first=diverse_first,
    )
    total_frames = 0
    candidate_center_frames = 0
    recorded_hit_frames = 0
    replay_hit_frames = 0
    improved_frames = 0
    regressed_frames = 0
    recorded_generation_errors = 0
    replay_generation_errors = 0

    for frame_index in candidate_frames:
        candidate_payload = events[(frame_index, "CANDIDATES")]
        temporal_payload = events.get((frame_index, "TEMPORAL_SELECTOR"), {})
        candidates = [
            row
            for candidate in candidate_payload.get("candidates", [])
            if isinstance(candidate, dict) and (row := _candidate_row(candidate)) is not None
        ]
        wide_debug = _wide_debug(temporal_payload)
        anchor = _point(wide_debug.get("point")) if wide_debug.get("reason") == "white_anchor" else None
        tracker.update(candidates, white_anchor=anchor)
        replay_points = tracker.hypothesis_points
        recorded_points = _retained_hypothesis_points(temporal_payload)
        score = scores.get(frame_index)
        target = _target_point(score)
        if score is None or target is None:
            continue
        total_frames += 1
        center_hit = any(_distance(candidate[:2], target) <= pass_distance_px for candidate in candidates)
        recorded_hit = any(_distance(point, target) <= pass_distance_px for point in recorded_points)
        replay_hit = any(_distance(point, target) <= pass_distance_px for point in replay_points)
        candidate_center_frames += int(center_hit)
        recorded_hit_frames += int(recorded_hit)
        replay_hit_frames += int(replay_hit)
        improved_frames += int(replay_hit and not recorded_hit)
        regressed_frames += int(recorded_hit and not replay_hit)
        failed = not bool(score.get("passed"))
        recorded_generation_errors += int(failed and center_hit and not recorded_hit)
        replay_generation_errors += int(failed and center_hit and not replay_hit)

    return HypothesisReplaySummary(
        total_frames=total_frames,
        candidate_center_frames=candidate_center_frames,
        recorded_hit_frames=recorded_hit_frames,
        replay_hit_frames=replay_hit_frames,
        improved_frames=improved_frames,
        regressed_frames=regressed_frames,
        recorded_hypothesis_generation_errors=recorded_generation_errors,
        replay_hypothesis_generation_errors=replay_generation_errors,
    )


def _events_by_frame(rows: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    events: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows:
        frame_index = _optional_int(row.get("frame_index"))
        payload = row.get("payload")
        if frame_index is not None and isinstance(payload, dict):
            events[(frame_index, str(row.get("type", "")))] = payload
    return events


def _candidate_row(candidate: dict[str, Any]) -> tuple[float, float, float, float, float] | None:
    center = _point(candidate.get("center"))
    if center is None:
        return None
    bbox = candidate.get("bbox")
    width = 24.0
    height = 24.0
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        try:
            width = max(1.0, float(bbox[2]) - float(bbox[0]))
            height = max(1.0, float(bbox[3]) - float(bbox[1]))
        except (TypeError, ValueError):
            pass
    return (center[0], center[1], _float(candidate.get("score")), width, height)


def _candidate_models(frame_index: int, payload: dict[str, Any]) -> list[Candidate]:
    candidates: list[Candidate] = []
    for row in payload.get("candidates", []):
        if not isinstance(row, dict):
            continue
        center = _point(row.get("center"))
        bbox = row.get("bbox")
        if center is None or not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            continue
        try:
            candidate_bbox = tuple(float(value) for value in bbox[:4])
        except (TypeError, ValueError):
            continue
        candidates.append(Candidate(
            candidate_id=str(row.get("candidate_id", "")),
            frame_index=frame_index,
            bbox=candidate_bbox,
            center=center,
            score=_float(row.get("score")),
            source=str(row.get("source", "")),
            class_name=str(row.get("class_name", "")),
        ))
    return candidates


def _evidence_models(payload: dict[str, Any]) -> dict[str, CandidateEvidence]:
    evidence: dict[str, CandidateEvidence] = {}
    for row in payload.get("evidence", []):
        if not isinstance(row, dict):
            continue
        candidate_id = str(row.get("candidate_id", ""))
        if not candidate_id:
            continue
        notes = row.get("notes")
        evidence[candidate_id] = CandidateEvidence(
            candidate_id=candidate_id,
            bg_score=_float(row.get("bg_score")),
            motion_divergence=_float(row.get("motion_divergence")),
            rigid_violation=_float(row.get("rigid_violation")),
            local_rigid_residual=_float(row.get("local_rigid_residual")),
            phase_similarity=_float(row.get("phase_similarity")),
            texture_bg_score=_float(row.get("texture_bg_score")),
            color_residual=_float(row.get("color_residual")),
            merge_likelihood=_float(row.get("merge_likelihood")),
            notes=tuple(str(note) for note in notes) if isinstance(notes, (list, tuple)) else (),
        )
    return evidence


def _board_frame_shape(rows: list[dict[str, Any]]) -> tuple[int, int] | None:
    for height, width in _board_frame_shape_values(rows):
        height = _optional_int(height)
        width = _optional_int(width)
        if height is not None and width is not None and height > 0 and width > 0:
            return (height, width)
    return None


def _cycle_board_frame_shape(rows: list[dict[str, Any]]) -> tuple[int, int] | None:
    values = _board_frame_shape_values(rows)
    if not values:
        return None
    height, width = values[0]
    if type(height) is int and type(width) is int and height > 0 and width > 0:
        return (height, width)
    return None


def _board_frame_shape_values(
    rows: list[dict[str, Any]],
) -> tuple[tuple[object, object], ...]:
    values: list[tuple[object, object]] = []
    for row in rows:
        if row.get("type") != "SESSION_START":
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        board_roi = payload.get("board_roi")
        if not isinstance(board_roi, dict):
            continue
        values.append((board_roi.get("h"), board_roi.get("w")))
    return tuple(values)


def _wide_debug(payload: dict[str, Any]) -> dict[str, Any]:
    debug = payload.get("debug")
    if not isinstance(debug, dict):
        return {}
    wide_debug = debug.get("kinematic_wide_beam_debug")
    return wide_debug if isinstance(wide_debug, dict) else {}


def _target_point(score: dict[str, Any] | None) -> tuple[float, float] | None:
    if score is None:
        return None
    return _point((score.get("target_x"), score.get("target_y")))


def _point(value: object) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return hypot(left[0] - right[0], left[1] - right[1])


def _optional_int(value: object) -> int | None:
    try:
        return int(value)
    except (OverflowError, TypeError, ValueError):
        return None


def _float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _render_report(
    variants: list[dict[str, object]],
    seeds: list[dict[str, object]],
) -> str:
    lines = [
        "# Studio 시간축 가설 보관 A/B",
        "",
        "|variant|width|branch|diverse|retained|improved|regressed|generation errors|",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in variants:
        lines.append(
            f"|{row['variant']}|{row['width']}|{row['branch']}|{row['diverse_first']}|"
            f"{row['replay_hit_frames']}|{row['improved_frames']}|{row['regressed_frames']}|"
            f"{row['replay_hypothesis_generation_errors']}|"
        )
    lines.extend(["", "## Seed별 결과", ""])
    for row in seeds:
        lines.append(
            f"- {row['seed']} / {row['variant']}: retained {row['replay_hit_frames']}, "
            f"improved {row['improved_frames']}, regressed {row['regressed_frames']}"
        )
    return "\n".join(lines) + "\n"


def _write_xlsx(
    path: Path,
    variants: list[dict[str, object]],
    seeds: list[dict[str, object]],
) -> None:
    workbook = Workbook()
    variant_sheet = workbook.active
    variant_sheet.title = "variants"
    variant_fields = list(variants[0]) if variants else ["variant"]
    variant_sheet.append(variant_fields)
    for row in variants:
        variant_sheet.append([row.get(field) for field in variant_fields])
    seed_sheet = workbook.create_sheet("seeds")
    seed_fields = list(seeds[0]) if seeds else ["seed"]
    seed_sheet.append(seed_fields)
    for row in seeds:
        seed_sheet.append([row.get(field) for field in seed_fields])
    workbook.save(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Studio 시간축 가설 보관 전략을 A/B 합니다.")
    parser.add_argument("--suite-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pass-distance-px", type=float, default=24.0)
    args = parser.parse_args(argv)
    result = sweep_hypothesis_suite(
        args.suite_root,
        args.output_dir,
        pass_distance_px=args.pass_distance_px,
    )
    print(json.dumps(result["variants"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
