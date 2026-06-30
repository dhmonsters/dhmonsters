# 투명도형 퍼즐 타겟 신분의 보류와 복원 상태를 관리한다.
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import hypot

from core.puzzle.models import Candidate, CandidateEvidence, IdentityDecision


YOLO_FULL_SCORE = 0.4
LOW_YOLO_COST_WEIGHT = 30.0
LOW_YOLO_CONFIDENCE_WEIGHT = 0.25
MERGE_COST_WEIGHT = 8.0


class IdentityTracker:
    def __init__(
        self,
        *,
        jump_distance: float = 40.0,
        merge_threshold: float = 0.65,
        max_hold_frames: int = 4,
        reacquire_distance: float = 45.0,
        release_reacquire_distance: float = 85.0,
        color_fade_frames: int = 20,
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

    def update(
        self,
        *,
        frame_index: int,
        candidates: Sequence[Candidate],
        evidence: Mapping[str, CandidateEvidence],
        white_anchor: tuple[float, float] | None = None,
    ) -> IdentityDecision:
        if white_anchor is not None:
            self.state = "INIT_VISIBLE"
            self.last_point = white_anchor
            self.last_candidate_id = None
            self.last_frame_index = frame_index
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
            if (
                (distance <= self.reacquire_distance or distance_to_last <= self.release_reacquire_distance)
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
            ranked.append(
                (
                    _candidate_cost(
                        candidate,
                        item_evidence,
                        distance,
                        color_weight=color_weight,
                        overlap_switch_penalty=self.overlap_switch_penalty,
                    ),
                    candidate,
                    item_evidence,
                    distance,
                )
            )
        ranked.sort(key=lambda item: item[0])
        _, candidate, item_evidence, distance = ranked[0]
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
        return max(0.0, min(1.0, 1.0 - elapsed / self.color_fade_frames))

    def _decision(
        self,
        confidence: float,
        reason: str,
        *,
        debug: dict[str, object],
    ) -> IdentityDecision:
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
    target_support = evidence.motion_divergence + evidence.rigid_violation + evidence.color_residual * color_weight
    background_cost = evidence.bg_score + evidence.texture_bg_score + evidence.phase_similarity
    low_yolo_cost = max(0.0, YOLO_FULL_SCORE - candidate.score) * LOW_YOLO_COST_WEIGHT
    merge_cost = evidence.merge_likelihood * (MERGE_COST_WEIGHT + overlap_switch_penalty)
    return distance + low_yolo_cost - target_support * 10.0 + background_cost * 10.0 + merge_cost


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
