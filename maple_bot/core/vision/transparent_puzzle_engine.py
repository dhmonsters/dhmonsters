# 투명 도형 퍼즐 후보를 추적 상태로 변환하는 엔진입니다.
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple


Point = Tuple[float, float]


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
