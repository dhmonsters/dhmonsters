# 시간축 도전자 경로가 연속될 때만 기존 표적을 교체하는 안전장치입니다.
from __future__ import annotations

from math import hypot
from typing import Sequence


Point = tuple[float, float]


class HypothesisChallengeGuard:
    def __init__(
        self,
        *,
        confirm_frames: int = 2,
        max_step_px: float = 90.0,
        min_separation_px: float = 24.0,
    ) -> None:
        self.confirm_frames = max(1, int(confirm_frames))
        self.max_step_px = max(1.0, float(max_step_px))
        self.min_separation_px = max(0.0, float(min_separation_px))
        self.reset()

    def reset(self) -> None:
        self._pending_point: Point | None = None
        self._pending_frames = 0
        self._confirmed = False

    def update(
        self,
        *,
        incumbent_point: Sequence[float] | None,
        challenger_point: Sequence[float] | None,
        protect_incumbent: bool = False,
    ) -> tuple[Point | None, dict[str, object]]:
        incumbent = _point(incumbent_point)
        challenger = _point(challenger_point)
        if protect_incumbent and incumbent is not None:
            self.reset()
            return incumbent, self._debug("incumbent_protected", incumbent, challenger)
        if challenger is None:
            self.reset()
            return incumbent, self._debug("challenger_missing", incumbent, challenger)
        if incumbent is None:
            self.reset()
            return challenger, self._debug("incumbent_missing", incumbent, challenger)
        if _distance(incumbent, challenger) <= self.min_separation_px:
            self.reset()
            return incumbent, self._debug("challenger_matches_incumbent", incumbent, challenger)

        previous = self._pending_point
        if previous is None:
            self._pending_point = challenger
            self._pending_frames = 1
            self._confirmed = self.confirm_frames <= 1
            reason = "challenger_confirmed" if self._confirmed else "challenger_pending"
        elif _distance(previous, challenger) <= self.max_step_px:
            self._pending_point = challenger
            self._pending_frames += 1
            self._confirmed = self._pending_frames >= self.confirm_frames
            reason = "challenger_confirmed" if self._confirmed else "challenger_pending"
        else:
            self._pending_point = challenger
            self._pending_frames = 1
            self._confirmed = self.confirm_frames <= 1
            reason = "challenger_confirmed" if self._confirmed else "challenger_reset"

        selected = challenger if self._confirmed else incumbent
        return selected, self._debug(reason, incumbent, challenger)

    def _debug(
        self,
        reason: str,
        incumbent: Point | None,
        challenger: Point | None,
    ) -> dict[str, object]:
        return {
            "reason": reason,
            "selected": self._confirmed,
            "incumbent_point": incumbent,
            "challenger_point": challenger,
            "pending_point": self._pending_point,
            "pending_frames": self._pending_frames,
            "confirm_frames": self.confirm_frames,
            "max_step_px": self.max_step_px,
            "min_separation_px": self.min_separation_px,
        }


def _point(value: Sequence[float] | None) -> Point | None:
    if value is None or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _distance(left: Point, right: Point) -> float:
    return hypot(left[0] - right[0], left[1] - right[1])
