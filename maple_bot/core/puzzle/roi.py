# 투명도형 퍼즐 탐지 ROI와 퍼즐판 ROI의 좌표 변환을 담당한다.
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.puzzle.models import RoiSpec


def resolve_ratio_roi(
    roi: Mapping[str, float],
    *,
    frame_w: int,
    frame_h: int,
    name: str,
    basis: str = "window_client",
    dpi_scale: float = 1.0,
    window_title: str = "",
) -> RoiSpec:
    x_ratio = _required_ratio(roi, "x_ratio")
    y_ratio = _required_ratio(roi, "y_ratio")
    w_ratio = _required_ratio(roi, "w_ratio")
    h_ratio = _required_ratio(roi, "h_ratio")
    if frame_w <= 0 or frame_h <= 0:
        raise ValueError("frame dimensions must be positive")

    x = int(round(float(frame_w) * x_ratio))
    y = int(round(float(frame_h) * y_ratio))
    w = int(round(float(frame_w) * w_ratio))
    h = int(round(float(frame_h) * h_ratio))
    if w <= 0 or h <= 0:
        raise ValueError("resolved ROI width and height must be positive")

    return RoiSpec(
        name=name,
        basis=basis,  # type: ignore[arg-type]
        x=x,
        y=y,
        w=w,
        h=h,
        x_ratio=x_ratio,
        y_ratio=y_ratio,
        w_ratio=w_ratio,
        h_ratio=h_ratio,
        dpi_scale=float(dpi_scale),
        window_title=str(window_title),
    )


def crop_by_roi(frame: Any, roi: RoiSpec) -> Any:
    height, width = frame.shape[:2]
    if roi.x < 0 or roi.y < 0 or roi.x + roi.w > width or roi.y + roi.h > height:
        raise ValueError("ROI must be fully inside the frame")
    return frame[roi.y : roi.y + roi.h, roi.x : roi.x + roi.w].copy()


def _required_ratio(roi: Mapping[str, float], key: str) -> float:
    if key not in roi:
        raise ValueError(f"missing ROI ratio: {key}")
    value = float(roi[key])
    if key in {"w_ratio", "h_ratio"} and value <= 0.0:
        raise ValueError("ROI width and height ratios must be positive")
    return value

