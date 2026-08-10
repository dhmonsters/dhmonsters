# 투명 퍼즐 live 추적 좌표의 건강도를 판단하고 rescue 승계를 결정합니다.
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Sequence, Tuple


Point = Tuple[float, float]


@dataclass(frozen=True)
class TrackHealthDecision:
    point: Optional[Point]
    source: str
    reason: str
    unhealthy: bool
    suspect_frames: int
    rescue_hold: int
    prediction: Optional[Point]
    primary_error: float
    out_of_bounds: bool


class TransparentTrackHealthSelector:
    def __init__(
        self,
        *,
        margin: float = 40.0,
        suspect_jump_px: float = 95.0,
        suspect_frames_required: int = 2,
        immediate_jump_px: float = 180.0,
        rescue_hold_frames: int = 3,
        velocity_alpha: float = 0.65,
    ):
        self.margin = float(margin)
        self.suspect_jump_px = float(suspect_jump_px)
        self.suspect_frames_required = max(1, int(suspect_frames_required))
        self.immediate_jump_px = float(immediate_jump_px)
        self.rescue_hold_frames = max(0, int(rescue_hold_frames))
        self.velocity_alpha = max(0.0, min(1.0, float(velocity_alpha)))
        self.reset()

    def reset(self, point: Optional[Point] = None) -> None:
        self._last = None if point is None else self._point(point)
        self._velocity = (0.0, 0.0)
        self._suspect_frames = 0
        self._rescue_hold = 0

    def update(
        self,
        *,
        primary: Optional[Point],
        rescue: Optional[Point],
        frame_shape: Sequence[int] | None,
        force_primary: bool = False,
    ) -> TrackHealthDecision:
        primary_point = self._point(primary)
        rescue_point = self._point(rescue)
        prediction = self._prediction()
        primary_error = (
            self._dist(primary_point, prediction)
            if primary_point is not None and prediction is not None
            else 0.0
        )
        out_of_bounds = (
            primary_point is not None
            and self._out_of_bounds(primary_point, frame_shape)
        )

        if force_primary and primary_point is not None:
            return self._commit(
                primary_point,
                source="primary",
                reason="force_primary",
                unhealthy=False,
                prediction=prediction,
                primary_error=primary_error,
                out_of_bounds=out_of_bounds,
                clear_suspicion=True,
            )

        if self._last is None:
            seed = primary_point if primary_point is not None else rescue_point
            if seed is None:
                return self._decision(None, "none", "no_points", False, prediction, 0.0, False)
            source = "primary" if primary_point is not None else "rescue"
            return self._commit(
                seed,
                source=source,
                reason=f"{source}_init",
                unhealthy=False,
                prediction=prediction,
                primary_error=primary_error,
                out_of_bounds=out_of_bounds,
                clear_suspicion=True,
            )

        if primary_point is None:
            self._suspect_frames += 1
            if rescue_point is not None:
                return self._commit_rescue(
                    rescue_point,
                    "primary_missing",
                    prediction,
                    primary_error,
                    out_of_bounds,
                )
            return self._decision(None, "none", "primary_missing", True, prediction, primary_error, False)

        jump_suspect = primary_error > self.suspect_jump_px
        if jump_suspect:
            self._suspect_frames += 1
        else:
            self._suspect_frames = 0

        if out_of_bounds and rescue_point is not None:
            return self._commit_rescue(
                rescue_point,
                "primary_out_of_bounds",
                prediction,
                primary_error,
                out_of_bounds,
            )

        if primary_error > self.immediate_jump_px and rescue_point is not None:
            return self._commit_rescue(
                rescue_point,
                "primary_immediate_jump",
                prediction,
                primary_error,
                out_of_bounds,
            )

        if self._rescue_hold > 0 and rescue_point is not None:
            self._rescue_hold -= 1
            return self._commit(
                rescue_point,
                source="rescue",
                reason="rescue_hold",
                unhealthy=True,
                prediction=prediction,
                primary_error=primary_error,
                out_of_bounds=out_of_bounds,
                clear_suspicion=False,
            )

        if self._suspect_frames >= self.suspect_frames_required and rescue_point is not None:
            return self._commit_rescue(
                rescue_point,
                "primary_repeated_jump",
                prediction,
                primary_error,
                out_of_bounds,
            )

        if jump_suspect:
            return self._decision(
                primary_point,
                "primary",
                "primary_suspect",
                True,
                prediction,
                primary_error,
                out_of_bounds,
            )

        return self._commit(
            primary_point,
            source="primary",
            reason="primary_healthy",
            unhealthy=jump_suspect,
            prediction=prediction,
            primary_error=primary_error,
            out_of_bounds=out_of_bounds,
            clear_suspicion=not jump_suspect,
        )

    def _commit_rescue(
        self,
        point: Point,
        reason: str,
        prediction: Optional[Point],
        primary_error: float,
        out_of_bounds: bool,
    ) -> TrackHealthDecision:
        self._rescue_hold = self.rescue_hold_frames
        return self._commit(
            point,
            source="rescue",
            reason=reason,
            unhealthy=True,
            prediction=prediction,
            primary_error=primary_error,
            out_of_bounds=out_of_bounds,
            clear_suspicion=False,
        )

    def _commit(
        self,
        point: Point,
        *,
        source: str,
        reason: str,
        unhealthy: bool,
        prediction: Optional[Point],
        primary_error: float,
        out_of_bounds: bool,
        clear_suspicion: bool,
    ) -> TrackHealthDecision:
        if self._last is not None:
            measured = (point[0] - self._last[0], point[1] - self._last[1])
            alpha = self.velocity_alpha
            self._velocity = (
                self._velocity[0] * alpha + measured[0] * (1.0 - alpha),
                self._velocity[1] * alpha + measured[1] * (1.0 - alpha),
            )
        self._last = point
        if clear_suspicion:
            self._suspect_frames = 0
            self._rescue_hold = 0
        return self._decision(
            point,
            source,
            reason,
            unhealthy,
            prediction,
            primary_error,
            out_of_bounds,
        )

    def _decision(
        self,
        point: Optional[Point],
        source: str,
        reason: str,
        unhealthy: bool,
        prediction: Optional[Point],
        primary_error: float,
        out_of_bounds: bool,
    ) -> TrackHealthDecision:
        return TrackHealthDecision(
            point=point,
            source=source,
            reason=reason,
            unhealthy=bool(unhealthy),
            suspect_frames=int(self._suspect_frames),
            rescue_hold=int(self._rescue_hold),
            prediction=prediction,
            primary_error=float(primary_error),
            out_of_bounds=bool(out_of_bounds),
        )

    def _prediction(self) -> Optional[Point]:
        if self._last is None:
            return None
        return (
            self._last[0] + self._velocity[0],
            self._last[1] + self._velocity[1],
        )

    def _out_of_bounds(self, point: Point, frame_shape: Sequence[int] | None) -> bool:
        if frame_shape is None or len(frame_shape) < 2:
            return False
        height = float(frame_shape[0])
        width = float(frame_shape[1])
        margin = self.margin
        return (
            point[0] < -margin
            or point[1] < -margin
            or point[0] > width + margin
            or point[1] > height + margin
        )

    @staticmethod
    def _point(point: Optional[Point]) -> Optional[Point]:
        if point is None:
            return None
        return (float(point[0]), float(point[1]))

    @staticmethod
    def _dist(a: Point, b: Point) -> float:
        return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
