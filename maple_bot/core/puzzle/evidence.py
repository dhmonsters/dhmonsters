# 투명도형 퍼즐 후보마다 판단 근거 점수를 계산한다.
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from math import hypot

import numpy as np

from core.puzzle.models import Candidate, CandidateEvidence, FramePacket


EvidenceHook = Callable[[Candidate, FramePacket], float]
HOOK_FIELDS = {
    "bg_score",
    "motion_divergence",
    "rigid_violation",
    "phase_similarity",
    "texture_bg_score",
}


class EvidenceJudges:
    def __init__(self, hooks: Mapping[str, EvidenceHook] | None = None) -> None:
        self.hooks = dict(hooks or {})
        unknown = set(self.hooks) - HOOK_FIELDS
        if unknown:
            raise ValueError(f"unsupported evidence hook field: {sorted(unknown)[0]}")

    def score(
        self,
        candidates: Sequence[Candidate],
        packet: FramePacket,
    ) -> dict[str, CandidateEvidence]:
        merge_scores = _merge_likelihoods(candidates, packet.board_frame)
        return {
            candidate.candidate_id: self._score_one(candidate, packet, merge_scores[candidate.candidate_id])
            for candidate in candidates
        }

    def _score_one(
        self,
        candidate: Candidate,
        packet: FramePacket,
        merge_likelihood: float,
    ) -> CandidateEvidence:
        values = {field: 0.0 for field in HOOK_FIELDS}
        notes: list[str] = []
        for field, hook in self.hooks.items():
            values[field] = _clamp01(float(hook(candidate, packet)))
            notes.append(f"hook:{field}")

        return CandidateEvidence(
            candidate_id=candidate.candidate_id,
            bg_score=values["bg_score"],
            motion_divergence=values["motion_divergence"],
            rigid_violation=values["rigid_violation"],
            phase_similarity=values["phase_similarity"],
            texture_bg_score=values["texture_bg_score"],
            color_residual=_color_residual(candidate, packet.board_frame),
            merge_likelihood=merge_likelihood,
            notes=tuple(notes),
        )


def _merge_likelihoods(
    candidates: Sequence[Candidate],
    board_frame: object,
) -> dict[str, float]:
    board_area = _board_area(board_frame)
    scores: dict[str, float] = {}
    for candidate in candidates:
        nearest_distance = _nearest_distance(candidate, candidates)
        if nearest_distance is None:
            scores[candidate.candidate_id] = 0.0
            continue

        width, height = _candidate_size(candidate)
        diagonal = max(hypot(width, height), 1.0)
        proximity_score = _clamp01(1.0 - nearest_distance / diagonal)
        size_score = _clamp01((width * height) / (board_area * 0.04))
        scores[candidate.candidate_id] = round(proximity_score * size_score, 6)
    return scores


def _nearest_distance(
    candidate: Candidate,
    candidates: Sequence[Candidate],
) -> float | None:
    distances = [
        hypot(candidate.center[0] - other.center[0], candidate.center[1] - other.center[1])
        for other in candidates
        if other.candidate_id != candidate.candidate_id
    ]
    if not distances:
        return None
    return min(distances)


def _candidate_size(candidate: Candidate) -> tuple[float, float]:
    x1, y1, x2, y2 = candidate.bbox
    return max(0.0, x2 - x1), max(0.0, y2 - y1)


def _board_area(board_frame: object) -> float:
    if isinstance(board_frame, np.ndarray) and board_frame.ndim >= 2:
        return float(max(1, board_frame.shape[0] * board_frame.shape[1]))
    return 1.0


def _color_residual(candidate: Candidate, board_frame: object) -> float:
    if not isinstance(board_frame, np.ndarray):
        return 0.0
    if board_frame.ndim != 3 or board_frame.shape[2] < 3:
        return 0.0

    crop = _candidate_crop(candidate, board_frame)
    if crop.size == 0:
        return 0.0

    channels = crop[:, :, :3].astype(float)
    channel_means = channels.mean(axis=(0, 1))
    residual = float(channel_means.max() - channel_means.min())
    if residual <= 1.0:
        return 0.0
    return round(_clamp01(residual / 255.0), 6)


def _candidate_crop(candidate: Candidate, board_frame: np.ndarray) -> np.ndarray:
    height, width = board_frame.shape[:2]
    x1, y1, x2, y2 = candidate.bbox
    left = max(0, min(width, int(np.floor(x1))))
    top = max(0, min(height, int(np.floor(y1))))
    right = max(0, min(width, int(np.ceil(x2))))
    bottom = max(0, min(height, int(np.ceil(y2))))
    if right <= left or bottom <= top:
        return board_frame[0:0, 0:0]
    return board_frame[top:bottom, left:right]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
