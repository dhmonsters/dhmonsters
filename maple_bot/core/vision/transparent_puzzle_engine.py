# 투명 도형 퍼즐 후보를 추적 상태로 변환하는 엔진입니다.
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Sequence, Tuple


Point = Tuple[float, float]


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


@dataclass(frozen=True)
class PuzzleCandidate:
    cx: float
    cy: float
    score: float
    w: float = float("nan")
    h: float = float("nan")


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
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._last_point: Optional[Point] = None

    def update(self, inp: PuzzleEngineInput) -> PuzzleEngineOutput:
        if inp.white_anchor is not None:
            x, y = float(inp.white_anchor[0]), float(inp.white_anchor[1])
            self._last_point = (x, y)
            return PuzzleEngineOutput(
                x=x,
                y=y,
                confidence=1.0,
                candidate_index=None,
                state="white_anchor",
                debug={"frame_index": inp.frame_index},
            )

        if not inp.candidates:
            return PuzzleEngineOutput(
                x=None,
                y=None,
                confidence=0.0,
                candidate_index=None,
                state="lost",
                debug={"frame_index": inp.frame_index},
            )

        candidate = max(inp.candidates, key=lambda cand: float(cand.score))
        idx = list(inp.candidates).index(candidate)
        self._last_point = (float(candidate.cx), float(candidate.cy))
        return PuzzleEngineOutput(
            x=float(candidate.cx),
            y=float(candidate.cy),
            confidence=float(candidate.score),
            candidate_index=idx,
            state="candidate",
            debug={"frame_index": inp.frame_index},
        )
