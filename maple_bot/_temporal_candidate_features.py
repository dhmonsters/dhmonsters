# 투명도형 퍼즐 후보 feature와 이미지 residual support를 계산한다.
from __future__ import annotations

import math
from typing import Mapping, Sequence

import numpy as np


Point = tuple[float, float]
Candidate = tuple[float, float, float, float, float]


def rank_supports(values: Sequence[float]) -> tuple[float, ...]:
    if not values:
        return ()
    numbers = [float(value) for value in values]
    lo = min(numbers)
    hi = max(numbers)
    if hi - lo <= 1e-9:
        return tuple(0.0 for _value in numbers)
    return tuple(round((value - lo) / (hi - lo), 6) for value in numbers)


def candidate_local_appearance_supports(
    diff: np.ndarray,
    candidates: Sequence[Candidate],
    *,
    inner_radius: int = 6,
    outer_radius: int = 16,
) -> tuple[float, ...]:
    contrasts = [
        _local_contrast(
            diff,
            (candidate[0], candidate[1]),
            inner_radius=inner_radius,
            outer_radius=outer_radius,
        )
        for candidate in candidates
    ]
    return rank_supports(contrasts)


def candidate_feature_row(
    clip: str,
    *,
    frame_index: int,
    role: str,
    candidate_index: int | None,
    candidate: Candidate | None,
    gt: Point | None,
    selected_index: int | None,
    raw_center_index: int | None,
    raw_box_index: int | None,
    extra: Mapping[str, object] | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "clip": clip,
        "frame": int(frame_index),
        "role": role,
        "candidate_index": candidate_index,
        "is_selected": candidate_index is not None and candidate_index == selected_index,
        "is_raw_center": candidate_index is not None and candidate_index == raw_center_index,
        "is_raw_box": candidate_index is not None and candidate_index == raw_box_index,
    }
    if candidate is None:
        row.update({"cx": None, "cy": None, "score": None, "w": None, "h": None, "gt_dist": None})
    else:
        point = (float(candidate[0]), float(candidate[1]))
        row.update(
            {
                "cx": point[0],
                "cy": point[1],
                "score": float(candidate[2]),
                "w": float(candidate[3]),
                "h": float(candidate[4]),
                "gt_dist": None if gt is None else round(_dist(point, gt), 6),
            }
        )
    if extra:
        row.update(dict(extra))
    return row


def box_internal_point(gt: Point, candidate: Candidate) -> Point:
    cx, cy, _score, width, height = candidate
    half_w = max(0.0, float(width) / 2.0)
    half_h = max(0.0, float(height) / 2.0)
    return (
        min(max(float(gt[0]), float(cx) - half_w), float(cx) + half_w),
        min(max(float(gt[1]), float(cy) - half_h), float(cy) + half_h),
    )


def prediction_box_point(predicted: Point, candidate: Candidate) -> Point:
    cx, cy, _score, width, height = candidate
    half_w = max(0.0, float(width) / 2.0)
    half_h = max(0.0, float(height) / 2.0)
    return (
        min(max(float(predicted[0]), float(cx) - half_w), float(cx) + half_w),
        min(max(float(predicted[1]), float(cy) - half_h), float(cy) + half_h),
    )


def point_inside_candidate_box(point: Point, candidate: Candidate, *, scale: float = 1.0) -> bool:
    cx, cy, _score, width, height = candidate
    half_w = max(0.0, float(width) * float(scale) / 2.0)
    half_h = max(0.0, float(height) * float(scale) / 2.0)
    return (
        float(cx) - half_w <= float(point[0]) <= float(cx) + half_w
        and float(cy) - half_h <= float(point[1]) <= float(cy) + half_h
    )


def _local_contrast(
    diff: np.ndarray,
    point: Point,
    *,
    inner_radius: int,
    outer_radius: int,
) -> float:
    arr = np.asarray(diff)
    if arr.size == 0:
        return 0.0
    if arr.ndim == 3:
        arr = arr.mean(axis=2)
    height, width = arr.shape[:2]
    cx = int(round(float(point[0])))
    cy = int(round(float(point[1])))
    inner = max(1, int(inner_radius))
    outer = max(inner + 1, int(outer_radius))
    left = max(0, cx - outer)
    right = min(width, cx + outer + 1)
    top = max(0, cy - outer)
    bottom = min(height, cy + outer + 1)
    if right <= left or bottom <= top:
        return 0.0
    patch = arr[top:bottom, left:right].astype(np.float32, copy=False)
    yy, xx = np.ogrid[top:bottom, left:right]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    center_mask = dist <= float(inner)
    ring_mask = (dist > float(inner)) & (dist <= float(outer))
    if not np.any(center_mask) or not np.any(ring_mask):
        return 0.0
    center = float(np.mean(patch[center_mask]))
    ring = float(np.mean(patch[ring_mask]))
    return center - ring


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
