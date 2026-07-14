from __future__ import annotations
# 미니맵 배경을 큰 지도에 맞춰 현재 뷰포트 원점과 추정 상태를 계산하는 추적기

from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np

from core.navigation.world_map import Calibration, WorldPoint


@dataclass(frozen=True)
class TrackResult:
    origin: WorldPoint
    confidence: float
    state: str


def _default_match(
    world_gray: np.ndarray,
    current_bgr: np.ndarray,
    previous_bgr: np.ndarray | None,
    scale: float,
):
    current = cv2.cvtColor(current_bgr, cv2.COLOR_BGR2GRAY)
    scaled = cv2.resize(
        current, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR
    )
    scores = cv2.matchTemplate(world_gray, scaled, cv2.TM_CCOEFF_NORMED)
    _, confidence, _, location = cv2.minMaxLoc(scores)
    shift = (0.0, 0.0, 0.0)
    if previous_bgr is not None:
        previous = cv2.cvtColor(previous_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        now = current.astype(np.float32)
        if previous.shape == now.shape:
            (dx, dy), response = cv2.phaseCorrelate(previous, now)
            shift = (dx, dy, response)
    return (
        WorldPoint(float(location[0]), float(location[1])),
        float(confidence),
        shift,
    )


class ViewportTracker:
    def __init__(
        self,
        world_gray: np.ndarray,
        calibration: Calibration,
        match_fn: Callable | None = None,
        confirm_threshold: float = 0.72,
        phase_threshold: float = 0.20,
    ):
        self._world = world_gray
        self._cal = calibration
        self._match = match_fn or _default_match
        self._confirm_threshold = confirm_threshold
        self._phase_threshold = phase_threshold
        self._result = TrackResult(
            WorldPoint(calibration.offset_x, calibration.offset_y),
            0.0,
            "estimated",
        )
        self._previous: np.ndarray | None = None
        self._velocity = WorldPoint(0.0, 0.0)
        self._viewport_size = (0.0, 0.0)

    @staticmethod
    def _limited_correction(
        previous: WorldPoint, matched: WorldPoint, max_step: float = 12.0
    ) -> WorldPoint:
        dx = matched.x - previous.x
        dy = matched.y - previous.y
        distance = float(np.hypot(dx, dy))
        if distance <= max_step or distance == 0:
            return matched
        ratio = max_step / distance
        return WorldPoint(previous.x + dx * ratio, previous.y + dy * ratio)

    def update(self, frame_bgr: np.ndarray, local_char: WorldPoint) -> TrackResult:
        del local_char
        height, width = frame_bgr.shape[:2]
        self._viewport_size = (
            width * self._cal.scale,
            height * self._cal.scale,
        )
        matched, confidence, shift = self._match(
            self._world, frame_bgr, self._previous, self._cal.scale
        )
        previous_origin = self._result.origin
        if confidence >= self._confirm_threshold:
            origin = (
                matched
                if self._previous is None
                else self._limited_correction(previous_origin, matched)
            )
            state = "confirmed"
        else:
            dx, dy, response = shift
            if response >= self._phase_threshold:
                origin = WorldPoint(
                    previous_origin.x - dx * self._cal.scale,
                    previous_origin.y - dy * self._cal.scale,
                )
            else:
                origin = WorldPoint(
                    previous_origin.x + self._velocity.x,
                    previous_origin.y + self._velocity.y,
                )
            state = "estimated"
        self._velocity = WorldPoint(
            origin.x - previous_origin.x,
            origin.y - previous_origin.y,
        )
        self._previous = frame_bgr.copy()
        self._result = TrackResult(origin, confidence, state)
        return self._result

    def character_world(self, local_char: WorldPoint) -> WorldPoint:
        return WorldPoint(
            self._result.origin.x + local_char.x * self._cal.scale,
            self._result.origin.y + local_char.y * self._cal.scale,
        )

    @property
    def result(self) -> TrackResult:
        return self._result

    @property
    def viewport_size(self) -> tuple[float, float]:
        return self._viewport_size
