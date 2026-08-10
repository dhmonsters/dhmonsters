# 투명도형 퍼즐 타겟 신분의 보류와 복원 상태를 관리한다.
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import hypot

from core.puzzle.models import Candidate, CandidateEvidence, IdentityDecision


YOLO_FULL_SCORE = 0.4
WHITE_BLOB_FULL_SCORE = 0.35
LOW_YOLO_COST_WEIGHT = 30.0
LOW_YOLO_CONFIDENCE_WEIGHT = 0.25
MERGE_COST_WEIGHT = 8.0
WHITE_BLOB_STRONG_FRAMES = 30
WHITE_BLOB_MID_FRAMES = 40
WHITE_BLOB_STRONG_WEIGHT = 0.70
WHITE_BLOB_MID_WEIGHT = 0.50
OVERLAP_PRESSURE_THRESHOLD = 0.25
OVERLAP_EVIDENCE_RADIUS = 90.0
OVERLAP_DISTANCE_CAP = 18.0
OVERLAP_DISTANCE_DISCOUNT = 0.5
OVERLAP_EVIDENCE_BOOST = 65.0
OVERLAP_SUPPORT_SCORE_FLOOR = 0.25
OVERLAP_SUPPORT_SCALE_FLOOR = 0.35
MOTION_RIGID_EVIDENCE_BOOST = 2.4


class IdentityTracker:
    def __init__(
        self,
        *,
        jump_distance: float = 40.0,
        merge_threshold: float = 0.65,
        max_hold_frames: int = 4,
        reacquire_distance: float = 45.0,
        release_reacquire_distance: float = 85.0,
        color_fade_frames: int = WHITE_BLOB_MID_FRAMES,
        overlap_switch_penalty: float = 20.0,
    ) -> None:
        if jump_distance <= 0.0:
            raise ValueError("jump_distance must be positive")
        if not 0.0 <= merge_threshold <= 1.0:
            raise ValueError("merge_threshold must be between 0 and 1")
        if max_hold_frames <= 0:
            raise ValueError("max_hold_frames must be positive")
        if reacquire_distance <= 0.0:
            raise ValueError("reacquire_distance must be positive")
        if release_reacquire_distance <= 0.0:
            raise ValueError("release_reacquire_distance must be positive")
        if color_fade_frames < 0:
            raise ValueError("color_fade_frames must not be negative")
        if overlap_switch_penalty < 0.0:
            raise ValueError("overlap_switch_penalty must not be negative")

        self.jump_distance = float(jump_distance)
        self.merge_threshold = float(merge_threshold)
        self.max_hold_frames = int(max_hold_frames)
        self.reacquire_distance = float(reacquire_distance)
        self.release_reacquire_distance = float(release_reacquire_distance)
        self.color_fade_frames = int(color_fade_frames)
        self.overlap_switch_penalty = float(overlap_switch_penalty)
        self.state = "LOST"
        self.last_point: tuple[float, float] | None = None
        self.last_candidate_id: str | None = None
        self.last_frame_index: int | None = None
        self.identity_start_frame_index: int | None = None
        self.velocity: tuple[float, float] = (0.0, 0.0)
        self.hold_frames = 0
        self._last_ranking_debug: list[dict[str, object]] = []

    def reset(self) -> None:
        self.state = "LOST"
        self.last_point = None
        self.last_candidate_id = None
        self.last_frame_index = None
        self.identity_start_frame_index = None
        self.velocity = (0.0, 0.0)
        self.hold_frames = 0
        self._last_ranking_debug = []

    def update(
        self,
        *,
        frame_index: int,
        candidates: Sequence[Candidate],
        evidence: Mapping[str, CandidateEvidence],
        white_anchor: tuple[float, float] | None = None,
    ) -> IdentityDecision:
        self._last_ranking_debug = []
        if white_anchor is not None:
            self.state = "INIT_VISIBLE"
            self.last_point = white_anchor
            self.last_candidate_id = None
            self.last_frame_index = frame_index
            if self.identity_start_frame_index is None:
                self.identity_start_frame_index = frame_index
            self.velocity = (0.0, 0.0)
            self.hold_frames = 0
            return self._decision(1.0, "white_anchor", debug={"anchor": white_anchor})

        if self.last_point is None:
            if not candidates:
                self.state = "LOST"
                return IdentityDecision("LOST", None, None, 0.0, "no_identity", 0, {})
            if self.identity_start_frame_index is None:
                self.identity_start_frame_index = frame_index
            visible_candidate = max(
                (
                    candidate
                    for candidate in candidates
                    if candidate.source == "white_anchor" and candidate.score >= YOLO_FULL_SCORE
                ),
                key=lambda candidate: candidate.score,
                default=None,
            )
            if visible_candidate is not None:
                self._accept_candidate(frame_index, visible_candidate)
                self.state = "TRACK_CONFIDENT"
                self.hold_frames = 0
                return self._decision(
                    visible_candidate.score,
                    "cold_start_white_candidate",
                    debug={"candidate": visible_candidate.candidate_id},
                )
            best, best_evidence, distance = self._best_candidate(
                candidates,
                evidence,
                candidates[0].center,
                frame_index=frame_index,
            )
            self._accept_candidate(frame_index, best)
            self.state = "TRACK_CONFIDENT"
            return self._decision(
                _confidence(best, best_evidence, distance, self.jump_distance),
                "cold_start_candidate",
                debug={"distance": distance, "color_weight": self._color_weight(frame_index)},
            )

        predicted = self._predicted_point()
        if not candidates:
            return self._hold_or_lost("hold_no_candidates", frame_index, predicted)

        best, best_evidence, distance = self._best_candidate(
            candidates,
            evidence,
            predicted,
            frame_index=frame_index,
        )
        if self.state in {"OCCLUSION_SUSPECTED", "IDENTITY_HOLD"}:
            distance_to_last = _distance(best.center, self.last_point)
            local_reacquire = distance <= self.reacquire_distance
            broad_release = (
                self.hold_frames >= 2
                and distance_to_last <= self.release_reacquire_distance
            )
            if (
                (local_reacquire or broad_release)
                and best_evidence.merge_likelihood < self.merge_threshold
            ):
                self._accept_candidate(frame_index, best)
                self.state = "REACQUIRE"
                self.hold_frames = 0
                return self._decision(
                    _confidence(best, best_evidence, distance, self.reacquire_distance),
                    "reacquired",
                    debug={
                        "distance": distance,
                        "distance_to_last": distance_to_last,
                        "candidate": best.candidate_id,
                        "color_weight": self._color_weight(frame_index),
                    },
                )
            return self._hold_or_lost("hold_ambiguous_candidate", frame_index, predicted)

        if distance > self.jump_distance or best_evidence.merge_likelihood >= self.merge_threshold:
            self.state = "OCCLUSION_SUSPECTED"
            self.hold_frames = 1
            return self._decision(
                0.35,
                "occlusion_suspected",
                debug={
                    "distance": distance,
                    "candidate": best.candidate_id,
                    "merge_likelihood": best_evidence.merge_likelihood,
                },
            )

        self._accept_candidate(frame_index, best)
        self.state = "TRACK_CONFIDENT"
        self.hold_frames = 0
        return self._decision(
            _confidence(best, best_evidence, distance, self.jump_distance),
            "candidate_continuity",
            debug={"distance": distance, "candidate": best.candidate_id, "color_weight": self._color_weight(frame_index)},
        )

    def _best_candidate(
        self,
        candidates: Sequence[Candidate],
        evidence: Mapping[str, CandidateEvidence],
        predicted: tuple[float, float],
        *,
        frame_index: int,
    ) -> tuple[Candidate, CandidateEvidence, float]:
        ranked = []
        color_weight = self._color_weight(frame_index)
        for candidate in candidates:
            item_evidence = evidence.get(candidate.candidate_id, CandidateEvidence(candidate.candidate_id))
            distance = _distance(candidate.center, predicted)
            parts = _candidate_cost_parts(
                candidate,
                item_evidence,
                distance,
                color_weight=color_weight,
                overlap_switch_penalty=self.overlap_switch_penalty,
            )
            total_cost = sum(parts.values())
            share_total = sum(abs(value) for value in parts.values())
            shares = {
                name: (abs(value) / share_total * 100.0 if share_total > 0.0 else 0.0)
                for name, value in parts.items()
            }
            ranked.append(
                (
                    total_cost,
                    candidate,
                    item_evidence,
                    distance,
                    {
                        "candidate_id": candidate.candidate_id,
                        "center": [float(candidate.center[0]), float(candidate.center[1])],
                        "score": float(candidate.score),
                        "distance": float(distance),
                        "total_cost": float(total_cost),
                        "cost_parts": {name: float(value) for name, value in parts.items()},
                        "judge_shares": {name: float(value) for name, value in shares.items()},
                    },
                )
            )
        ranked.sort(key=lambda item: item[0])
        self._last_ranking_debug = [item[4] for item in ranked[:5]]
        _, candidate, item_evidence, distance, _debug = ranked[0]
        return candidate, item_evidence, distance

    def _accept_candidate(self, frame_index: int, candidate: Candidate) -> None:
        if self.last_point is not None:
            self.velocity = (
                candidate.center[0] - self.last_point[0],
                candidate.center[1] - self.last_point[1],
            )
        self.last_point = candidate.center
        self.last_candidate_id = candidate.candidate_id
        self.last_frame_index = frame_index

    def _hold_or_lost(
        self,
        reason: str,
        frame_index: int,
        predicted: tuple[float, float],
    ) -> IdentityDecision:
        self.hold_frames += 1
        self.last_frame_index = frame_index
        if self.hold_frames > self.max_hold_frames:
            self.state = "LOST"
            self.last_point = None
            self.last_candidate_id = None
            return IdentityDecision("LOST", None, None, 0.0, "hold_limit_exceeded", self.hold_frames, {})

        self.state = "IDENTITY_HOLD"
        return self._decision(
            0.25,
            reason,
            debug={"predicted": predicted, "velocity": self.velocity},
        )

    def _predicted_point(self) -> tuple[float, float]:
        if self.last_point is None:
            return (0.0, 0.0)
        return (self.last_point[0] + self.velocity[0], self.last_point[1] + self.velocity[1])

    def _color_weight(self, frame_index: int) -> float:
        if self.color_fade_frames <= 0:
            return 0.0
        if self.identity_start_frame_index is None:
            return 0.0
        elapsed = max(0, frame_index - self.identity_start_frame_index)
        strong_frames = min(WHITE_BLOB_STRONG_FRAMES, self.color_fade_frames)
        if elapsed <= strong_frames:
            return WHITE_BLOB_STRONG_WEIGHT
        if elapsed <= self.color_fade_frames:
            return WHITE_BLOB_MID_WEIGHT
        return 0.0

    def _decision(
        self,
        confidence: float,
        reason: str,
        *,
        debug: dict[str, object],
    ) -> IdentityDecision:
        if self._last_ranking_debug:
            debug = {**debug, "ranking": list(self._last_ranking_debug)}
        return IdentityDecision(
            state=self.state,
            point=self.last_point,
            candidate_id=self.last_candidate_id,
            confidence=max(0.0, min(1.0, confidence)),
            reason=reason,
            hold_frames=self.hold_frames,
            debug=debug,
        )


def _candidate_cost(
    candidate: Candidate,
    evidence: CandidateEvidence,
    distance: float,
    *,
    color_weight: float = 1.0,
    overlap_switch_penalty: float = 0.0,
) -> float:
    return sum(_candidate_cost_parts(candidate, evidence, distance, color_weight=color_weight, overlap_switch_penalty=overlap_switch_penalty).values())


def candidate_cost_judge_shares(
    candidate: Candidate,
    evidence: CandidateEvidence,
    distance: float,
    *,
    color_weight: float = 1.0,
    overlap_switch_penalty: float = 0.0,
) -> dict[str, float]:
    parts = _candidate_cost_parts(
        candidate,
        evidence,
        distance,
        color_weight=color_weight,
        overlap_switch_penalty=overlap_switch_penalty,
    )
    total = sum(abs(value) for value in parts.values())
    if total <= 0.0:
        return {name: 0.0 for name in parts}
    return {name: abs(value) / total * 100.0 for name, value in parts.items()}


def _candidate_cost_parts(
    candidate: Candidate,
    evidence: CandidateEvidence,
    distance: float,
    *,
    color_weight: float = 1.0,
    overlap_switch_penalty: float = 0.0,
) -> dict[str, float]:
    bg_score = evidence.bg_score
    motion_divergence = evidence.motion_divergence
    rigid_violation = evidence.rigid_violation
    phase_similarity = evidence.phase_similarity
    texture_bg_score = evidence.texture_bg_score
    color_residual = _full_score_cap(evidence.color_residual, WHITE_BLOB_FULL_SCORE)
    merge_likelihood = evidence.merge_likelihood
    overlap_pressure = _overlap_pressure(evidence)
    local_overlap_pressure = overlap_pressure if distance <= OVERLAP_EVIDENCE_RADIUS else 0.0
    boosted_motion = motion_divergence * MOTION_RIGID_EVIDENCE_BOOST
    boosted_rigid = rigid_violation * MOTION_RIGID_EVIDENCE_BOOST
    support_scale = 1.0
    if local_overlap_pressure >= OVERLAP_PRESSURE_THRESHOLD:
        support_scale = _overlap_support_scale(candidate.score)
        boosted_motion *= support_scale
        boosted_rigid *= support_scale
    target_support = boosted_motion + boosted_rigid + color_residual * color_weight
    evidence_weight = 10.0 + local_overlap_pressure * OVERLAP_EVIDENCE_BOOST
    distance_cost = distance
    background_cost = bg_score + texture_bg_score + phase_similarity
    if local_overlap_pressure >= OVERLAP_PRESSURE_THRESHOLD and target_support > background_cost:
        distance_cost = min(distance, OVERLAP_DISTANCE_CAP) * (1.0 - local_overlap_pressure * OVERLAP_DISTANCE_DISCOUNT)
    low_yolo_cost = max(0.0, YOLO_FULL_SCORE - candidate.score) * LOW_YOLO_COST_WEIGHT
    merge_cost = merge_likelihood * (MERGE_COST_WEIGHT + overlap_switch_penalty)
    return {
        "continuity": distance_cost,
        "yolo": low_yolo_cost,
        "overlap": merge_cost,
        "background": bg_score * evidence_weight,
        "phase": phase_similarity * evidence_weight,
        "texture": texture_bg_score * evidence_weight,
        "motion": -boosted_motion * evidence_weight,
        "rigid": -boosted_rigid * evidence_weight,
        "white_blob": -(color_residual * color_weight) * evidence_weight,
    }


def _overlap_pressure(evidence: CandidateEvidence) -> float:
    background_pressure = (evidence.bg_score + evidence.phase_similarity) / 2.0
    target_motion_pressure = (evidence.motion_divergence + evidence.rigid_violation) / 2.0
    pressure = max(evidence.merge_likelihood * 2.0, background_pressure, target_motion_pressure)
    return max(0.0, min(1.0, pressure))


def _overlap_support_scale(score: float) -> float:
    if score >= YOLO_FULL_SCORE:
        return 1.0
    if score <= OVERLAP_SUPPORT_SCORE_FLOOR:
        return OVERLAP_SUPPORT_SCALE_FLOOR
    span = YOLO_FULL_SCORE - OVERLAP_SUPPORT_SCORE_FLOOR
    ratio = (score - OVERLAP_SUPPORT_SCORE_FLOOR) / span
    return OVERLAP_SUPPORT_SCALE_FLOOR + ratio * (1.0 - OVERLAP_SUPPORT_SCALE_FLOOR)


def _full_score_cap(value: float, threshold: float) -> float:
    value = max(0.0, min(1.0, float(value)))
    if value >= threshold:
        return 1.0
    return value


def _confidence(
    candidate: Candidate,
    evidence: CandidateEvidence,
    distance: float,
    distance_limit: float,
) -> float:
    distance_score = max(0.0, 1.0 - distance / max(distance_limit, 1.0))
    evidence_score = evidence.motion_divergence + evidence.rigid_violation - evidence.bg_score - evidence.merge_likelihood
    low_yolo_penalty = max(0.0, YOLO_FULL_SCORE - candidate.score) * LOW_YOLO_CONFIDENCE_WEIGHT
    return 0.55 + distance_score * 0.35 + evidence_score * 0.1 - low_yolo_penalty


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])
