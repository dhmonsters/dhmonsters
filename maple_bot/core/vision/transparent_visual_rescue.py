# 투명 퍼즐 후보의 주기차분 흔적을 이용해 live rescue 후보를 생성합니다.
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Sequence, Tuple

import cv2
import numpy as np


Point = Tuple[float, float]
Candidate = Tuple[float, float, float, float, float]


@dataclass(frozen=True)
class VisualRescueDecision:
    point: Optional[Point]
    available: bool
    source: str
    period: Optional[int]
    visual_best: float
    debug: dict


@dataclass(frozen=True)
class _Hypothesis:
    score: float
    last: Point
    velocity: Point


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _normalize_candidates(candidates: Sequence[Sequence[float]]) -> list[Candidate]:
    out = []
    for candidate in candidates:
        if len(candidate) < 2:
            continue
        score = float(candidate[2]) if len(candidate) >= 3 else 0.0
        width = float(candidate[3]) if len(candidate) >= 4 else 24.0
        height = float(candidate[4]) if len(candidate) >= 5 else 24.0
        out.append((float(candidate[0]), float(candidate[1]), score, width, height))
    return out


def _rank_to_ten(values: Sequence[float], *, high_is_better: bool = True) -> list[float]:
    if not values:
        return []
    numeric = [float(value) for value in values]
    if len(numeric) == 1:
        return [10.0]
    if max(numeric) - min(numeric) <= 1e-6:
        return [0.0 for _value in numeric]
    order = sorted(range(len(numeric)), key=lambda index: numeric[index], reverse=high_is_better)
    scores = [0.0 for _value in numeric]
    denom = max(1, len(numeric) - 1)
    for rank, index in enumerate(order):
        scores[index] = 10.0 * (denom - rank) / denom
    return scores


def _local_residual_center_mean(
    diff: np.ndarray,
    point: Point,
    *,
    inner_radius: int,
) -> float:
    if diff.size == 0:
        return 0.0
    height, width = diff.shape[:2]
    cx = int(round(float(point[0])))
    cy = int(round(float(point[1])))
    radius = max(1, int(inner_radius))
    x1 = max(0, cx - radius)
    x2 = min(width, cx + radius + 1)
    y1 = max(0, cy - radius)
    y2 = min(height, cy + radius + 1)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    patch = diff[y1:y2, x1:x2].astype(np.float32, copy=False)
    yy, xx = np.ogrid[y1:y2, x1:x2]
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2
    if not np.any(mask):
        return 0.0
    return float(np.mean(patch[mask]))


def visual_rank_scores_for_candidates(
    diff: np.ndarray,
    candidates: Sequence[Sequence[float]],
    *,
    inner_radius: int = 6,
    outer_radius: int = 16,
) -> list[float]:
    del outer_radius
    normalized = _normalize_candidates(candidates)
    values = [
        _local_residual_center_mean(
            diff,
            (candidate[0], candidate[1]),
            inner_radius=inner_radius,
        )
        for candidate in normalized
    ]
    return _rank_to_ten(values, high_is_better=True)


def visual_box_points_for_candidates(
    diff: np.ndarray,
    candidates: Sequence[Sequence[float]],
    *,
    inner_radius: int = 6,
    grid_scale: Sequence[float] = (-0.5, 0.0, 0.5),
) -> list[Point]:
    normalized = _normalize_candidates(candidates)
    out: list[Point] = []
    for candidate in normalized:
        cx, cy, _score, width, height = candidate
        half_w = max(0.0, float(width) / 2.0)
        half_h = max(0.0, float(height) / 2.0)
        points = [
            (
                float(cx) + half_w * float(x_scale),
                float(cy) + half_h * float(y_scale),
            )
            for x_scale in grid_scale
            for y_scale in grid_scale
        ]
        out.append(max(
            points,
            key=lambda point: _local_residual_center_mean(
                diff,
                point,
                inner_radius=inner_radius,
            ),
        ))
    return out


class VisualBeamTracker:
    def __init__(
        self,
        *,
        max_candidates: int = 24,
        keep: int = 32,
        branch: int = 12,
        track_prediction_gate: float = 45.0,
        track_snap_gate: float = 30.0,
        rescue_prediction_gate: float = 260.0,
        velocity_alpha: float = 0.55,
        continuity_weight: float = 6.0,
        track_weight: float = 1.0,
        detection_weight: float = 0.0,
        visual_weight: float = 1.0,
        jump_penalty_weight: float = 0.03,
    ):
        self.max_candidates = max(1, int(max_candidates))
        self.keep = max(1, int(keep))
        self.branch = max(1, int(branch))
        self.track_prediction_gate = float(track_prediction_gate)
        self.track_snap_gate = float(track_snap_gate)
        self.rescue_prediction_gate = float(rescue_prediction_gate)
        self.velocity_alpha = float(velocity_alpha)
        self.continuity_weight = float(continuity_weight)
        self.track_weight = float(track_weight)
        self.detection_weight = float(detection_weight)
        self.visual_weight = float(visual_weight)
        self.jump_penalty_weight = float(jump_penalty_weight)
        self._hypotheses: list[_Hypothesis] = []

    def reset(self, point: Optional[Point] = None) -> None:
        self._hypotheses = []
        if point is not None:
            self._hypotheses.append(
                _Hypothesis(0.0, (float(point[0]), float(point[1])), (0.0, 0.0))
            )

    def update(
        self,
        candidates: Sequence[Sequence[float]],
        *,
        visual_scores: Sequence[float] | None = None,
        track_point: Optional[Point] = None,
    ) -> VisualRescueDecision:
        indexed = [
            (index, candidate)
            for index, candidate in enumerate(_normalize_candidates(candidates))
        ]
        indexed.sort(key=lambda item: item[1][2], reverse=True)
        points = [
            ((candidate[0], candidate[1]), candidate[2], original_index)
            for original_index, candidate in indexed[: self.max_candidates]
        ]
        if not points:
            return VisualRescueDecision(None, False, "no_candidates", None, 0.0, {})

        visual = list(visual_scores or [])
        track = None if track_point is None else (float(track_point[0]), float(track_point[1]))
        if not self._hypotheses:
            seed = (
                min((point for point, _score, _index in points), key=lambda point: _dist(point, track))
                if track is not None
                else points[0][0]
            )
            self._hypotheses = [_Hypothesis(0.0, seed, (0.0, 0.0))]
            return VisualRescueDecision(seed, bool(visual), "visual_beam_init", None, 0.0, {})

        expanded: list[_Hypothesis] = []
        best_visual = 0.0
        for hyp in self._hypotheses:
            pred = (hyp.last[0] + hyp.velocity[0], hyp.last[1] + hyp.velocity[1])
            track_reliable = track is not None and _dist(track, pred) <= self.track_prediction_gate
            scored = []
            for point, det_score, original_index in points:
                pred_dist = _dist(point, pred)
                continuity = max(
                    0.0,
                    1.0 - pred_dist / max(self.rescue_prediction_gate, 1e-6),
                ) * self.continuity_weight
                track_bonus = 0.0
                if track_reliable and track is not None:
                    track_dist = _dist(point, track)
                    track_bonus = max(
                        0.0,
                        1.0 - track_dist / max(self.track_snap_gate, 1e-6),
                    ) * self.track_weight
                visual_score = float(visual[original_index]) if 0 <= original_index < len(visual) else 0.0
                best_visual = max(best_visual, visual_score)
                local_score = (
                    continuity
                    + track_bonus
                    + self.detection_weight * float(det_score)
                    + self.visual_weight * visual_score
                    - self.jump_penalty_weight * pred_dist
                )
                scored.append((local_score, point))

            scored.sort(key=lambda item: item[0], reverse=True)
            for local_score, point in scored[: self.branch]:
                measured = (point[0] - hyp.last[0], point[1] - hyp.last[1])
                alpha = self.velocity_alpha
                velocity = (
                    alpha * hyp.velocity[0] + (1.0 - alpha) * measured[0],
                    alpha * hyp.velocity[1] + (1.0 - alpha) * measured[1],
                )
                expanded.append(
                    _Hypothesis(hyp.score + local_score, point, velocity)
                )

        self._hypotheses = sorted(expanded, key=lambda hyp: hyp.score, reverse=True)[: self.keep]
        best = self._hypotheses[0]
        return VisualRescueDecision(
            best.last,
            bool(visual),
            "visual_beam",
            None,
            best_visual,
            {"hypotheses": len(self._hypotheses)},
        )


class TransparentVisualRescueTracker:
    def __init__(
        self,
        *,
        period_hint: Optional[int] = None,
        local_search: int = 8,
        inner_radius: int = 6,
    ):
        self.period_hint = None if period_hint is None else int(period_hint)
        self.local_search = int(local_search)
        self.inner_radius = int(inner_radius)
        self.beam = VisualBeamTracker()
        self.reset()

    def reset(self) -> None:
        self._frames: list[np.ndarray] = []
        self._candidate_sets: list[list[Candidate]] = []
        self._prep_end = 0
        self._period: Optional[int] = self.period_hint
        self.beam.reset()

    def update(
        self,
        gray_frame,
        candidates: Sequence[Sequence[float]],
        *,
        white_anchor: Optional[Point] = None,
        track_point: Optional[Point] = None,
    ) -> VisualRescueDecision:
        gray = self._gray(gray_frame)
        frame_index = len(self._frames)
        normalized = _normalize_candidates(candidates)
        visual_scores: list[float] = []
        if white_anchor is not None:
            self._prep_end = frame_index + 1
            self.beam.reset((float(white_anchor[0]), float(white_anchor[1])))

        period = self._period or self._estimate_period(normalized)
        if period is not None:
            self._period = int(period)
            source = self._source_frame(frame_index, int(period))
            if (
                source is not None
                and 0 <= source < len(self._frames)
                and self._frames[source].shape == gray.shape
            ):
                diff = np.abs(gray.astype(np.float32) - self._frames[source].astype(np.float32))
                visual_scores = visual_rank_scores_for_candidates(
                    diff,
                    normalized,
                    inner_radius=self.inner_radius,
                )

        decision = self.beam.update(
            normalized,
            visual_scores=visual_scores,
            track_point=track_point,
        )
        self._frames.append(gray)
        self._candidate_sets.append(normalized)
        return VisualRescueDecision(
            decision.point if visual_scores else None,
            bool(visual_scores),
            decision.source if visual_scores else "visual_not_ready",
            self._period,
            decision.visual_best,
            {
                **decision.debug,
                "frame": frame_index,
                "source_frame": self._source_frame(frame_index, self._period) if self._period else None,
                "prep_end": self._prep_end,
            },
        )

    def _source_frame(self, frame_index: int, period: Optional[int]) -> Optional[int]:
        if period is None or period <= 0:
            return None
        source = int(frame_index) - int(period)
        if source < 0:
            return None
        step = max(1, int(period))
        while source >= self._prep_end and source - step >= 0:
            source -= step
        return source

    def _estimate_period(self, current: Sequence[Candidate]) -> Optional[int]:
        if self.period_hint is not None:
            return self.period_hint
        if self._prep_end <= 0 or len(self._candidate_sets) < self._prep_end + 2:
            return None
        csets = self._candidate_sets + [list(current)]
        lo = max(2, self._prep_end - 24)
        hi = min(len(csets) - 1, self._prep_end + 24)
        best: tuple[float, int] | None = None
        for lag in range(lo, hi + 1):
            scores = []
            for frame in range(max(self._prep_end, lag), len(csets)):
                score = self._match_score(csets[frame - lag], csets[frame])
                if score is not None:
                    scores.append(score)
            if not scores:
                continue
            item = (float(np.median(scores)), int(lag))
            if best is None or item < best:
                best = item
        return None if best is None else best[1]

    def _match_score(
        self,
        reference: Sequence[Candidate],
        current: Sequence[Candidate],
    ) -> Optional[float]:
        if not reference or not current:
            return None
        pairs = []
        for ri, ref in enumerate(reference):
            for ci, cur in enumerate(current):
                distance = _dist((ref[0], ref[1]), (cur[0], cur[1]))
                if distance <= 120.0:
                    pairs.append((distance, ri, ci))
        pairs.sort(key=lambda item: item[0])
        used_ref = set()
        used_cur = set()
        distances = []
        for distance, ri, ci in pairs:
            if ri in used_ref or ci in used_cur:
                continue
            used_ref.add(ri)
            used_cur.add(ci)
            distances.append(distance)
        if not distances:
            return None
        distances.sort()
        keep = distances[: max(1, int(math.ceil(len(distances) * 0.75)))]
        return float(np.median(keep))

    @staticmethod
    def _gray(frame) -> np.ndarray:
        arr = np.asarray(frame)
        if arr.ndim == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
        return arr.astype(np.float32, copy=False)
