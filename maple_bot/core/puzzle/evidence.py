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

    def reset(self) -> None:
        pass

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


class LiveEvidenceJudges(EvidenceJudges):
    def __init__(
        self,
        *,
        match_radius_px: float = 95.0,
        motion_scale_px: float = 32.0,
        texture_scale: float = 1.0,
    ) -> None:
        super().__init__()
        self.match_radius_px = float(match_radius_px)
        self.motion_scale_px = float(motion_scale_px)
        self.texture_scale = float(texture_scale)
        self._prev_gray: np.ndarray | None = None
        self._prev_candidates: list[tuple[float, float]] = []

    def reset(self) -> None:
        self._prev_gray = None
        self._prev_candidates = []

    def score(
        self,
        candidates: Sequence[Candidate],
        packet: FramePacket,
    ) -> dict[str, CandidateEvidence]:
        base = super().score(candidates, packet)
        gray = _gray_frame(packet.board_frame)
        bg_shift = _phase_shift(self._prev_gray, gray)
        scored: dict[str, CandidateEvidence] = {}

        for candidate in candidates:
            motion = self._motion_values(candidate, bg_shift)
            local_rigid_residual = _local_rigid_residual(candidate, self._prev_gray, gray, bg_shift)
            texture_bg_score = _texture_bg_score(candidate, packet.board_frame, scale=self.texture_scale)
            bg_score = max(motion["bg_score"], texture_bg_score * 0.35)
            old = base[candidate.candidate_id]
            scored[candidate.candidate_id] = CandidateEvidence(
                candidate_id=old.candidate_id,
                bg_score=round(_clamp01(bg_score), 6),
                motion_divergence=round(_clamp01(motion["motion_divergence"]), 6),
                rigid_violation=round(_clamp01(motion["rigid_violation"]), 6),
                local_rigid_residual=round(_clamp01(local_rigid_residual), 6),
                phase_similarity=round(_clamp01(motion["phase_similarity"]), 6),
                texture_bg_score=round(_clamp01(texture_bg_score), 6),
                color_residual=old.color_residual,
                merge_likelihood=old.merge_likelihood,
                notes=old.notes + ("live:motion", "live:local_rigid", "live:texture"),
            )

        self._prev_gray = gray
        self._prev_candidates = [(float(candidate.center[0]), float(candidate.center[1])) for candidate in candidates]
        return scored

    def _motion_values(
        self,
        candidate: Candidate,
        bg_shift: tuple[float, float],
    ) -> dict[str, float]:
        if not self._prev_candidates:
            return {
                "bg_score": 0.0,
                "motion_divergence": 0.0,
                "rigid_violation": 0.0,
                "phase_similarity": 0.0,
            }

        match = _nearest_previous_snapshot(candidate, self._prev_candidates, bg_shift)
        if match is None or match[1] > self.match_radius_px:
            return {
                "bg_score": 0.0,
                "motion_divergence": 1.0,
                "rigid_violation": 1.0,
                "phase_similarity": 0.0,
            }

        _previous_center, distance_from_bg_flow = match
        divergence = _clamp01(distance_from_bg_flow / max(1.0, self.motion_scale_px))
        phase_similarity = _clamp01(1.0 - divergence)
        return {
            "bg_score": phase_similarity,
            "motion_divergence": divergence,
            "rigid_violation": divergence,
            "phase_similarity": phase_similarity,
        }


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
    if board_frame.ndim not in {2, 3}:
        return 0.0
    if board_frame.ndim == 3 and board_frame.shape[2] < 3:
        return 0.0

    crop = _candidate_crop(candidate, board_frame)
    if crop.size == 0:
        return 0.0

    ring = _candidate_ring(candidate, board_frame)
    color_delta = 0.0
    if board_frame.ndim == 3:
        channels = crop[:, :, :3].astype(float)
        channel_means = channels.mean(axis=(0, 1))
        color_delta = float(channel_means.max() - channel_means.min())

    brightness_delta = 0.0
    if ring.size > 0:
        crop_luma = _luma_values(crop)
        ring_luma = _luma_values(ring)
        if crop_luma.size > 0 and ring_luma.size > 0:
            brightness_delta = max(0.0, float(crop_luma.mean() - ring_luma.mean()))

    residual = max(color_delta, brightness_delta)
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


def _gray_frame(board_frame: object) -> np.ndarray | None:
    if not isinstance(board_frame, np.ndarray):
        return None
    if board_frame.ndim == 2:
        return board_frame.astype(np.float32)
    if board_frame.ndim == 3 and board_frame.shape[2] >= 3:
        return board_frame[:, :, :3].mean(axis=2).astype(np.float32)
    return None


def _phase_shift(previous: np.ndarray | None, current: np.ndarray | None) -> tuple[float, float]:
    if previous is None or current is None:
        return (0.0, 0.0)
    if previous.shape != current.shape or previous.size == 0:
        return (0.0, 0.0)
    try:
        cv2 = _cv2()
        shift, response = cv2.phaseCorrelate(previous, current)
    except Exception:
        return (0.0, 0.0)
    dx, dy = float(shift[0]), float(shift[1])
    response = float(response)
    if not np.isfinite(dx) or not np.isfinite(dy) or not np.isfinite(response):
        return (0.0, 0.0)
    if response < 0.05:
        return (0.0, 0.0)
    max_x = max(1.0, current.shape[1] * 0.25)
    max_y = max(1.0, current.shape[0] * 0.25)
    if abs(dx) > max_x or abs(dy) > max_y:
        return (0.0, 0.0)
    return (dx, dy)


def _nearest_previous_snapshot(
    candidate: Candidate,
    previous_candidates: Sequence[tuple[float, float]],
    bg_shift: tuple[float, float],
) -> tuple[tuple[float, float], float] | None:
    best: tuple[tuple[float, float], float] | None = None
    for previous in previous_candidates:
        predicted_x = previous[0] + bg_shift[0]
        predicted_y = previous[1] + bg_shift[1]
        distance = hypot(candidate.center[0] - predicted_x, candidate.center[1] - predicted_y)
        if best is None or distance < best[1]:
            best = (previous, distance)
    return best


def _local_rigid_residual(
    candidate: Candidate,
    previous_gray: np.ndarray | None,
    current_gray: np.ndarray | None,
    bg_shift: tuple[float, float],
) -> float:
    if previous_gray is None or current_gray is None:
        return 0.0
    if previous_gray.shape != current_gray.shape or previous_gray.ndim != 2:
        return 0.0

    height, width = current_gray.shape
    x1, y1, x2, y2 = candidate.bbox
    left = max(0, min(width, int(np.floor(x1))))
    top = max(0, min(height, int(np.floor(y1))))
    right = max(0, min(width, int(np.ceil(x2))))
    bottom = max(0, min(height, int(np.ceil(y2))))
    crop_width = right - left
    crop_height = bottom - top
    if crop_width < 6 or crop_height < 6:
        return 0.0

    previous_left = int(round(left - float(bg_shift[0])))
    previous_top = int(round(top - float(bg_shift[1])))
    previous_right = previous_left + crop_width
    previous_bottom = previous_top + crop_height
    if previous_left < 0 or previous_top < 0 or previous_right > width or previous_bottom > height:
        return 0.0

    current_crop = current_gray[top:bottom, left:right]
    previous_crop = previous_gray[previous_top:previous_bottom, previous_left:previous_right]
    return _normalized_patch_residual(previous_crop, current_crop)


def _normalized_patch_residual(previous: np.ndarray, current: np.ndarray) -> float:
    if previous.shape != current.shape or previous.size == 0:
        return 0.0

    previous_norm = _normalize_patch(previous)
    current_norm = _normalize_patch(current)
    pixel_residual = float(np.mean(np.abs(previous_norm - current_norm))) / 2.0

    previous_dx = np.diff(previous_norm, axis=1)
    current_dx = np.diff(current_norm, axis=1)
    previous_dy = np.diff(previous_norm, axis=0)
    current_dy = np.diff(current_norm, axis=0)
    edge_residual = (
        float(np.mean(np.abs(previous_dx - current_dx)))
        + float(np.mean(np.abs(previous_dy - current_dy)))
    ) / 4.0
    return _clamp01(pixel_residual * 0.4 + edge_residual * 0.6)


def _normalize_patch(patch: np.ndarray) -> np.ndarray:
    values = patch.astype(np.float32)
    mean = float(values.mean())
    std = float(values.std())
    return (values - mean) / max(8.0, std)


def _texture_bg_score(candidate: Candidate, board_frame: object, *, scale: float) -> float:
    if not isinstance(board_frame, np.ndarray) or board_frame.ndim < 2:
        return 0.0
    crop = _candidate_crop(candidate, board_frame)
    ring = _candidate_ring(candidate, board_frame)
    if crop.size == 0 or ring.size == 0:
        return 0.0
    crop_values = _as_color_values(crop)
    ring_values = _as_color_values(ring)
    if crop_values.size == 0 or ring_values.size == 0:
        return 0.0
    mean_delta = float(np.abs(crop_values.mean(axis=0) - ring_values.mean(axis=0)).mean()) / 255.0
    std_delta = abs(float(crop_values.std()) - float(ring_values.std())) / 128.0
    penalty = (mean_delta * 0.7 + std_delta * 0.3) * max(0.01, float(scale))
    return _clamp01(1.0 - penalty)


def _candidate_ring(candidate: Candidate, board_frame: np.ndarray, *, pad: int = 8) -> np.ndarray:
    height, width = board_frame.shape[:2]
    x1, y1, x2, y2 = candidate.bbox
    left = max(0, min(width, int(np.floor(x1)) - pad))
    top = max(0, min(height, int(np.floor(y1)) - pad))
    right = max(0, min(width, int(np.ceil(x2)) + pad))
    bottom = max(0, min(height, int(np.ceil(y2)) + pad))
    inner_left = max(0, min(width, int(np.floor(x1))))
    inner_top = max(0, min(height, int(np.floor(y1))))
    inner_right = max(0, min(width, int(np.ceil(x2))))
    inner_bottom = max(0, min(height, int(np.ceil(y2))))
    if right <= left or bottom <= top:
        return board_frame[0:0, 0:0]

    outer = board_frame[top:bottom, left:right]
    mask = np.ones(outer.shape[:2], dtype=bool)
    rel_left = max(0, inner_left - left)
    rel_top = max(0, inner_top - top)
    rel_right = min(mask.shape[1], inner_right - left)
    rel_bottom = min(mask.shape[0], inner_bottom - top)
    if rel_right > rel_left and rel_bottom > rel_top:
        mask[rel_top:rel_bottom, rel_left:rel_right] = False
    return outer[mask]


def _as_color_values(values: np.ndarray) -> np.ndarray:
    if values.ndim == 1:
        return values.reshape(-1, 1).astype(float)
    if values.ndim == 2:
        if values.shape[1] in (3, 4):
            return values[:, : min(3, values.shape[1])].astype(float)
        return values.reshape(-1, 1).astype(float)
    if values.ndim == 3:
        return values[:, :, : min(3, values.shape[2])].reshape(-1, min(3, values.shape[2])).astype(float)
    return np.zeros((0, 1), dtype=float)


def _luma_values(values: np.ndarray) -> np.ndarray:
    if values.ndim == 2:
        return values.reshape(-1).astype(float)
    if values.ndim == 3:
        return values[:, :, : min(3, values.shape[2])].mean(axis=2).reshape(-1).astype(float)
    if values.ndim == 1:
        return values.astype(float)
    return np.zeros((0,), dtype=float)


def _cv2():
    import cv2

    return cv2


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
