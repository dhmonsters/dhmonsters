# 투명 도형 YOLO 박스 안에서 실제 추적점을 안정화하는 보정기입니다.
from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable, Optional, Sequence, Tuple

Point = Tuple[float, float]
Candidate = Tuple[float, float, float, float, float]


@dataclass(frozen=True)
class TransparentBoxDecision:
    point: Point
    mode: str
    candidate: Optional[Candidate]
    predicted: Optional[Point]
    innovation: float


class TransparentBoxSelector:
    """ByteTrack 중심점이 병합 박스 안에서 밀릴 때 박스 내부 예측점으로 보정한다."""

    def __init__(
        self,
        center_drift_gate: float = 28.0,
        max_repair_jump: float = 80.0,
        box_margin: float = 8.0,
        max_coast: int = 0,
        velocity_alpha: float = 1.0,
    ):
        self.center_drift_gate = float(center_drift_gate)
        self.max_repair_jump = float(max_repair_jump)
        self.box_margin = float(box_margin)
        self.max_coast = int(max_coast)
        self.velocity_alpha = float(max(0.0, min(1.0, velocity_alpha)))
        self.last: Optional[Point] = None
        self.vx = 0.0
        self.vy = 0.0
        self.coast_frames = 0

    def reset(self, point: Optional[Point] = None) -> None:
        self.last = None if point is None else (float(point[0]), float(point[1]))
        self.vx = 0.0
        self.vy = 0.0
        self.coast_frames = 0

    def update(
        self,
        candidates: Iterable[Sequence[float]],
        fallback_pos: Optional[Point],
        force_fallback: bool = False,
    ) -> Optional[TransparentBoxDecision]:
        cands = [self._normalize(c) for c in candidates if len(c) >= 2]
        fallback = self._point(fallback_pos)

        if self.last is None:
            if fallback is None:
                best = self._best_score(cands)
                if best is None:
                    return None
                fallback = (best[0], best[1])
            return self._commit(fallback, "init", self._nearest(cands, fallback), None, 0.0)

        pred = (self.last[0] + self.vx, self.last[1] + self.vy)
        if force_fallback and fallback is not None:
            return self._commit(fallback, "anchor", self._nearest(cands, fallback), pred,
                                self._distance(fallback, pred))

        selected = self._nearest(cands, fallback) if fallback is not None else None
        innovation = 0.0 if fallback is None else self._distance(fallback, pred)

        if selected is not None and self._contains(selected, pred, self.box_margin):
            repairable = fallback is None or (
                innovation > self.center_drift_gate
                and innovation <= self.max_repair_jump
            )
            if repairable:
                point = self._clamp(pred, selected)
                return self._commit(point, "box_pred", selected, pred, innovation)

        if fallback is not None and innovation <= self.center_drift_gate:
            return self._commit(fallback, "fallback", selected, pred, innovation)

        pred_box = self._containing_candidate(cands, pred)
        if pred_box is not None and fallback is None:
            point = self._clamp(pred, pred_box)
            return self._commit(point, "box_pred", pred_box, pred, innovation)

        if self.coast_frames < self.max_coast:
            return self._coast(pred, innovation)

        if fallback is not None:
            return self._commit(fallback, "fallback_far", selected, pred, innovation)
        return self._coast(pred, innovation)

    def _commit(
        self,
        point: Point,
        mode: str,
        candidate: Optional[Candidate],
        predicted: Optional[Point],
        innovation: float,
    ) -> TransparentBoxDecision:
        point = (float(point[0]), float(point[1]))
        if self.last is not None:
            mx = point[0] - self.last[0]
            my = point[1] - self.last[1]
            a = self.velocity_alpha
            self.vx = self.vx * (1.0 - a) + mx * a
            self.vy = self.vy * (1.0 - a) + my * a
        self.last = point
        self.coast_frames = 0
        return TransparentBoxDecision(point, mode, candidate, predicted, float(innovation))

    def _coast(self, pred: Point, innovation: float) -> TransparentBoxDecision:
        self.last = (float(pred[0]), float(pred[1]))
        self.coast_frames += 1
        return TransparentBoxDecision(self.last, "coast", None, pred, float(innovation))

    @staticmethod
    def _point(point: Optional[Point]) -> Optional[Point]:
        if point is None:
            return None
        return (float(point[0]), float(point[1]))

    @staticmethod
    def _normalize(cand: Sequence[float]) -> Candidate:
        cx = float(cand[0])
        cy = float(cand[1])
        score = float(cand[2]) if len(cand) > 2 else 0.0
        w = float(cand[3]) if len(cand) > 3 else 0.0
        h = float(cand[4]) if len(cand) > 4 else 0.0
        return (cx, cy, score, w, h)

    @staticmethod
    def _distance(a: Point, b: Point) -> float:
        return hypot(a[0] - b[0], a[1] - b[1])

    @staticmethod
    def _best_score(cands: Sequence[Candidate]) -> Optional[Candidate]:
        if not cands:
            return None
        return max(cands, key=lambda c: c[2])

    def _nearest(
        self,
        cands: Sequence[Candidate],
        point: Optional[Point],
    ) -> Optional[Candidate]:
        if not cands or point is None:
            return None
        return min(cands, key=lambda c: self._distance((c[0], c[1]), point))

    def _containing_candidate(
        self,
        cands: Sequence[Candidate],
        point: Point,
    ) -> Optional[Candidate]:
        containing = [c for c in cands if self._contains(c, point, self.box_margin)]
        if not containing:
            return None
        return min(containing, key=lambda c: self._distance((c[0], c[1]), point) - c[2] * 5.0)

    @staticmethod
    def _contains(cand: Candidate, point: Point, margin: float) -> bool:
        cx, cy, _score, w, h = cand
        if w <= 0.0 or h <= 0.0:
            return False
        return (
            cx - w / 2.0 - margin <= point[0] <= cx + w / 2.0 + margin
            and cy - h / 2.0 - margin <= point[1] <= cy + h / 2.0 + margin
        )

    @staticmethod
    def _clamp(point: Point, cand: Candidate) -> Point:
        cx, cy, _score, w, h = cand
        if w <= 0.0 or h <= 0.0:
            return point
        x1 = cx - w / 2.0
        x2 = cx + w / 2.0
        y1 = cy - h / 2.0
        y2 = cy + h / 2.0
        return (max(x1, min(x2, point[0])), max(y1, min(y2, point[1])))
