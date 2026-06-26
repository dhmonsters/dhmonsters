# 투명 도형 퍼즐 후보를 추적 상태로 변환하는 엔진입니다.
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Sequence, Tuple


Point = Tuple[float, float]


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _finite_size(candidate: "PuzzleCandidate") -> bool:
    return (
        math.isfinite(float(candidate.w))
        and math.isfinite(float(candidate.h))
        and float(candidate.w) > 0.0
        and float(candidate.h) > 0.0
    )


def internal_points(
    candidate: "PuzzleCandidate",
    grid_size: int = 5,
    shrink: float = 0.76,
) -> List[Point]:
    cx, cy = float(candidate.cx), float(candidate.cy)
    if not _finite_size(candidate) or grid_size <= 1:
        return [(cx, cy)]

    half_w = float(candidate.w) * float(shrink) / 2.0
    half_h = float(candidate.h) * float(shrink) / 2.0
    if grid_size == 3:
        xs = [cx - half_w, cx, cx + half_w]
        ys = [cy - half_h, cy, cy + half_h]
    else:
        step_x = 0.0 if grid_size <= 1 else (half_w * 2.0) / float(grid_size - 1)
        step_y = 0.0 if grid_size <= 1 else (half_h * 2.0) / float(grid_size - 1)
        xs = [cx - half_w + step_x * i for i in range(grid_size)]
        ys = [cy - half_h + step_y * i for i in range(grid_size)]
    return [(float(x), float(y)) for x in xs for y in ys]


@dataclass(frozen=True)
class PuzzleCandidate:
    cx: float
    cy: float
    score: float
    w: float = float("nan")
    h: float = float("nan")


def candidate_from_live_row(row: Sequence[float]) -> PuzzleCandidate:
    cx, cy, score, w, h = row[:5]
    return PuzzleCandidate(float(cx), float(cy), float(score), float(w), float(h))


@dataclass(frozen=True)
class PuzzleEngineInput:
    frame_index: int
    candidates: Sequence[PuzzleCandidate]
    white_anchor: Optional[Point] = None
    gray_frame: object | None = None


@dataclass(frozen=True)
class PuzzleEngineOutput:
    x: Optional[float]
    y: Optional[float]
    confidence: float
    candidate_index: Optional[int]
    state: str
    debug: Dict[str, object]


@dataclass(frozen=True)
class EngineConfig:
    max_candidate_jump: float = 115.0
    coast_frames: int = 12
    merged_min_size: float = 80.0
    use_background_catalog: bool = False
    catalog_white_exclusion: float = 45.0
    background_pos_tol: float = 10.0
    background_area_tol_pct: float = 6.0
    background_aspect_tol_pct: float = 6.0
    background_prediction_guard: float = 34.0
    period_search: int = 24
    local_lag_search: int = 8


class BackgroundCatalog:
    def __init__(self):
        self._frames: Dict[int, List[PuzzleCandidate]] = {}

    def add_frame(self, frame_index: int, candidates: Sequence[PuzzleCandidate]) -> None:
        self._frames[int(frame_index)] = list(candidates)

    def estimate_period(
        self,
        prep_end: int,
        min_lag: Optional[int] = None,
        max_lag: Optional[int] = None,
    ) -> Tuple[int, float]:
        if not self._frames:
            return int(prep_end), float("inf")

        max_frame = max(self._frames)
        lo = int(min_lag) if min_lag is not None else max(2, int(prep_end) - 24)
        hi = int(max_lag) if max_lag is not None else min(max_frame, int(prep_end) + 24)
        best: Optional[Tuple[float, int]] = None
        for lag in range(lo, hi + 1):
            score = self._lag_score(lag, int(prep_end))
            if score is None:
                continue
            item = (score, lag)
            if best is None or item < best:
                best = item
        if best is None:
            return int(prep_end), float("inf")
        score, lag = best
        return lag, score

    def expected_candidates(
        self,
        frame_index: int,
        period: int,
        local_search: int = 8,
    ) -> List[PuzzleCandidate]:
        lag = self._choose_local_lag(int(frame_index), int(period), int(local_search))
        return list(self._frames.get(int(frame_index) - lag, []))

    def _choose_local_lag(self, frame_index: int, period: int, search: int) -> int:
        lo = max(2, period - search)
        hi = min(frame_index, period + search)
        best: Optional[Tuple[float, int]] = None
        for lag in range(lo, hi + 1):
            score = self._match_score(
                self._frames.get(frame_index - lag, []),
                self._frames.get(frame_index, []),
            )
            if score is None:
                continue
            item = (score, lag)
            if best is None or item < best:
                best = item
        return best[1] if best is not None else period

    def _lag_score(self, lag: int, start: int) -> Optional[float]:
        scores = []
        for frame_index in sorted(self._frames):
            if frame_index < max(start, lag):
                continue
            score = self._match_score(
                self._frames.get(frame_index - lag, []),
                self._frames.get(frame_index, []),
            )
            if score is not None:
                scores.append(score)
        if not scores:
            return None
        scores.sort()
        return float(scores[len(scores) // 2])

    def _match_score(
        self,
        reference: Sequence[PuzzleCandidate],
        current: Sequence[PuzzleCandidate],
    ) -> Optional[float]:
        if not reference or not current:
            return None
        pairs = []
        for ri, ref in enumerate(reference):
            for ci, cur in enumerate(current):
                pairs.append((_dist((ref.cx, ref.cy), (cur.cx, cur.cy)), ri, ci))
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
        keep = distances[: max(1, math.ceil(len(distances) * 0.75))]
        return float(keep[len(keep) // 2])


class TransparentPuzzleEngine:
    def __init__(self, config: Optional[EngineConfig] = None):
        self._config = config or EngineConfig()
        self.reset()

    def reset(self) -> None:
        self._catalog = BackgroundCatalog()
        self._period: Optional[int] = None
        self._period_score: float = float("inf")
        self._prep_end: Optional[int] = None
        self._was_white = False
        self._last_point: Optional[Point] = None
        self._velocity: Point = (0.0, 0.0)
        self._coast_left = int(self._config.coast_frames)

    def update(self, inp: PuzzleEngineInput) -> PuzzleEngineOutput:
        frame_index = int(inp.frame_index)
        self._catalog.add_frame(
            frame_index,
            self._catalog_candidates(inp.candidates, inp.white_anchor),
        )
        if inp.white_anchor is not None:
            x, y = float(inp.white_anchor[0]), float(inp.white_anchor[1])
            self._last_point = (x, y)
            self._velocity = (0.0, 0.0)
            self._coast_left = int(self._config.coast_frames)
            self._was_white = True
            return PuzzleEngineOutput(
                x=x,
                y=y,
                confidence=1.0,
                candidate_index=None,
                state="white_anchor",
                debug={"frame_index": frame_index},
            )

        if not inp.candidates:
            if self._last_point is not None and self._coast_left > 0:
                return self._coast(frame_index, reason="no_candidates")
            return PuzzleEngineOutput(
                x=None,
                y=None,
                confidence=0.0,
                candidate_index=None,
                state="lost",
                debug={"frame_index": frame_index},
            )

        self._ensure_period(frame_index)
        active = self._active_candidates(frame_index, inp.candidates)
        selected = self._select_indexed_candidates(active)
        if selected is None:
            return self._coast(frame_index, reason="jump_gate")

        idx, candidate = selected
        cur, state = self._candidate_point(candidate)
        if self._last_point is not None:
            self._velocity = (
                cur[0] - self._last_point[0],
                cur[1] - self._last_point[1],
            )
        self._last_point = cur
        self._coast_left = int(self._config.coast_frames)
        return PuzzleEngineOutput(
            x=cur[0],
            y=cur[1],
            confidence=float(candidate.score),
            candidate_index=idx,
            state=state,
            debug={
                "frame_index": frame_index,
                "period": self._period,
                "period_score": self._period_score,
                "active_candidates": len(active),
                "total_candidates": len(inp.candidates),
            },
        )

    def _catalog_candidates(
        self,
        candidates: Sequence[PuzzleCandidate],
        white_anchor: Optional[Point],
    ) -> List[PuzzleCandidate]:
        if white_anchor is None:
            return list(candidates)
        return [
            candidate
            for candidate in candidates
            if _dist((candidate.cx, candidate.cy), white_anchor)
            > float(self._config.catalog_white_exclusion)
        ]

    def _ensure_period(self, frame_index: int) -> None:
        if not self._config.use_background_catalog:
            self._was_white = False
            return
        if self._period is not None:
            return
        if not self._was_white:
            return
        self._prep_end = int(frame_index)
        search = int(self._config.period_search)
        period, score = self._catalog.estimate_period(
            int(frame_index),
            min_lag=max(2, int(frame_index) - search),
            max_lag=int(frame_index),
        )
        self._period = int(period)
        self._period_score = float(score)
        self._was_white = False

    def _active_candidates(
        self,
        frame_index: int,
        candidates: Sequence[PuzzleCandidate],
    ) -> List[Tuple[int, PuzzleCandidate]]:
        indexed = list(enumerate(candidates))
        if not self._config.use_background_catalog:
            return indexed
        if self._period is None:
            return indexed
        expected = self._catalog.expected_candidates(
            int(frame_index),
            int(self._period),
            local_search=int(self._config.local_lag_search),
        )
        if not expected:
            return indexed

        pred = self._predicted_point()
        active = []
        for idx, candidate in indexed:
            if self._is_background_candidate(candidate, expected):
                if pred is None:
                    continue
                if _dist((candidate.cx, candidate.cy), pred) > float(self._config.background_prediction_guard):
                    continue
            active.append((idx, candidate))
        return active if active else indexed

    def _is_background_candidate(
        self,
        candidate: PuzzleCandidate,
        expected: Sequence[PuzzleCandidate],
    ) -> bool:
        for background in expected:
            if _dist((candidate.cx, candidate.cy), (background.cx, background.cy)) > float(self._config.background_pos_tol):
                continue
            if not self._shape_close(candidate, background):
                continue
            return True
        return False

    def _shape_close(self, candidate: PuzzleCandidate, expected: PuzzleCandidate) -> bool:
        area_delta = self._pct_delta(self._area(candidate), self._area(expected))
        aspect_delta = self._pct_delta(self._aspect(candidate), self._aspect(expected))
        return (
            area_delta <= float(self._config.background_area_tol_pct)
            and aspect_delta <= float(self._config.background_aspect_tol_pct)
        )

    @staticmethod
    def _area(candidate: PuzzleCandidate) -> float:
        if not _finite_size(candidate):
            return float("nan")
        return float(candidate.w) * float(candidate.h)

    @staticmethod
    def _aspect(candidate: PuzzleCandidate) -> float:
        if not _finite_size(candidate):
            return float("nan")
        return float(candidate.w) / max(float(candidate.h), 1e-6)

    @staticmethod
    def _pct_delta(a: float, b: float) -> float:
        if not (math.isfinite(float(a)) and math.isfinite(float(b))):
            return 0.0
        return abs(float(a) - float(b)) / max((abs(float(a)) + abs(float(b))) / 2.0, 1e-6) * 100.0

    def _predicted_point(self) -> Optional[Point]:
        if self._last_point is None:
            return None
        return (
            self._last_point[0] + self._velocity[0],
            self._last_point[1] + self._velocity[1],
        )

    def _select_candidate(
        self,
        candidates: Sequence[PuzzleCandidate],
    ) -> Optional[Tuple[int, PuzzleCandidate]]:
        return self._select_indexed_candidates(list(enumerate(candidates)))

    def _select_indexed_candidates(
        self,
        candidates: Sequence[Tuple[int, PuzzleCandidate]],
    ) -> Optional[Tuple[int, PuzzleCandidate]]:
        pred = self._predicted_point()
        if pred is None:
            return max(candidates, key=lambda item: float(item[1].score))

        gated = [
            (idx, cand)
            for idx, cand in candidates
            if _dist(pred, (cand.cx, cand.cy)) <= float(self._config.max_candidate_jump)
        ]
        if not gated:
            return None
        return min(
            gated,
            key=lambda item: (
                _dist(pred, (item[1].cx, item[1].cy)) - 0.02 * float(item[1].score),
                -float(item[1].score),
            ),
        )

    def _candidate_point(self, candidate: PuzzleCandidate) -> Tuple[Point, str]:
        center = (float(candidate.cx), float(candidate.cy))
        pred = self._predicted_point()
        if pred is None or not _finite_size(candidate):
            return center, "candidate"
        if max(float(candidate.w), float(candidate.h)) < float(self._config.merged_min_size):
            return center, "candidate"

        inside = (
            abs(pred[0] - center[0]) <= float(candidate.w) / 2.0
            and abs(pred[1] - center[1]) <= float(candidate.h) / 2.0
        )
        if not inside:
            return center, "candidate"

        point = min(
            internal_points(candidate, grid_size=5, shrink=0.76),
            key=lambda item: _dist(item, pred),
        )
        if _dist(point, pred) + 1.0 < _dist(center, pred):
            return point, "merged_internal"
        return center, "candidate"

    def _coast(self, frame_index: int, reason: str) -> PuzzleEngineOutput:
        pred = self._predicted_point()
        if pred is None or self._coast_left <= 0:
            return PuzzleEngineOutput(
                x=None,
                y=None,
                confidence=0.0,
                candidate_index=None,
                state="lost",
                debug={"frame_index": frame_index, "reason": reason},
            )
        self._last_point = pred
        self._coast_left -= 1
        return PuzzleEngineOutput(
            x=pred[0],
            y=pred[1],
            confidence=0.25,
            candidate_index=None,
            state="coast",
            debug={"frame_index": frame_index, "reason": reason},
        )
