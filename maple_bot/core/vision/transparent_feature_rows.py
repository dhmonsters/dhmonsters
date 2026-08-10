# 투명 퍼즐 family selector가 사용할 공통 feature rows를 생성합니다.
from __future__ import annotations

import math
from statistics import median
from typing import Mapping, Sequence, Tuple

import _final_candidate_selector as final_candidate
import _local_box_selector_score as local_box_selector


Point = Tuple[float, float]
Candidate = Tuple[float, float, float, float, float]

LOWER_RANK_FEATURES = (
    "bg_like",
    "center",
    "cons_med",
    "idsw",
    "match",
    "prior",
    "ring",
    "rough",
    "run",
)
HIGHER_RANK_FEATURES = (
    "contrast",
    "contrast_med",
    "divergence",
    "motion_div",
)


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _point(value: Sequence[float]) -> Point:
    return (float(value[0]), float(value[1]))


def nearest_candidate_distance(
    point: Sequence[float],
    candidates: Sequence[Sequence[float]],
) -> float:
    if not candidates:
        return 1e3
    pt = _point(point)
    return min(_dist(pt, candidate) for candidate in candidates)


def path_candidate_distance_median(
    path: Mapping[int, Point],
    frames: Sequence[int],
    candidate_sets: Mapping[int, Sequence[Sequence[float]]] | None = None,
) -> float:
    if not candidate_sets:
        return 0.0
    distances = []
    for frame in frames:
        point = path.get(int(frame))
        if point is None:
            continue
        distances.append(
            nearest_candidate_distance(point, candidate_sets.get(int(frame), []))
        )
    return float(median(distances)) if distances else 1e3


def path_consensus_median(
    path: Mapping[int, Point],
    paths: Mapping[str, Mapping[int, Point]],
    frames: Sequence[int],
) -> float:
    distances = []
    for frame in frames:
        point = path.get(int(frame))
        if point is None:
            continue
        others = [
            other.get(int(frame))
            for other in paths.values()
            if other.get(int(frame)) is not None
        ]
        if len(others) <= 1:
            continue
        distances.append(float(median(_dist(point, other) for other in others)))
    return float(median(distances)) if distances else 0.0


def path_motion_divergence_median(
    path: Mapping[int, Point],
    paths: Mapping[str, Mapping[int, Point]],
    frames: Sequence[int],
) -> float:
    values = []
    ordered = [int(frame) for frame in frames]
    for prev_frame, frame in zip(ordered, ordered[1:]):
        prev_point = path.get(prev_frame)
        point = path.get(frame)
        if prev_point is None or point is None:
            continue

        velocities = []
        for other in paths.values():
            other_prev = other.get(prev_frame)
            other_point = other.get(frame)
            if other_prev is None or other_point is None:
                continue
            velocities.append((
                float(other_point[0]) - float(other_prev[0]),
                float(other_point[1]) - float(other_prev[1]),
            ))
        if len(velocities) <= 1:
            continue

        median_vx = float(median(velocity[0] for velocity in velocities))
        median_vy = float(median(velocity[1] for velocity in velocities))
        vx = float(point[0]) - float(prev_point[0])
        vy = float(point[1]) - float(prev_point[1])
        values.append(math.hypot(vx - median_vx, vy - median_vy))
    return float(median(values)) if values else 0.0


def _background_columns(stats: Mapping[str, object] | None) -> dict:
    stats = stats or {}
    matched = float(stats.get("matched_ratio", 0.0) or 0.0)
    run_identity = float(stats.get("run_identity_ratio", 0.0) or 0.0)
    return {
        "bg_like": (matched + run_identity) / 2.0,
        "match": matched,
        "run": run_identity,
        "idsw": float(stats.get("id_switches", 0.0) or 0.0),
    }


def _residual_columns(stats: Mapping[str, object] | None) -> dict:
    stats = stats or {}
    return {
        "contrast": float(stats.get("contrast_mean", 0.0) or 0.0),
        "contrast_med": float(stats.get("contrast_median", 0.0) or 0.0),
        "ring": float(stats.get("ring_mean", 0.0) or 0.0),
    }


def build_transparent_feature_rows(
    clip: str,
    paths: Mapping[str, Mapping[int, Point]],
    frames: Sequence[int],
    *,
    meta: Mapping[str, Mapping[str, object]] | None = None,
    candidate_sets: Mapping[int, Sequence[Sequence[float]]] | None = None,
    background_stats: Mapping[str, Mapping[str, object]] | None = None,
    residual_stats: Mapping[str, Mapping[str, object]] | None = None,
) -> list[dict]:
    meta = meta or {}
    background_stats = background_stats or {}
    residual_stats = residual_stats or {}
    rows = []

    for family in sorted(paths):
        path = paths[family]
        family_meta = meta.get(family, {})
        source = str(family_meta.get("source") or family)
        row = {
            "clip": str(clip),
            "family": str(family),
            "center": path_candidate_distance_median(path, frames, candidate_sets),
            "cons_med": path_consensus_median(path, paths, frames),
            "divergence": path_consensus_median(path, paths, frames),
            "motion_div": path_motion_divergence_median(path, paths, frames),
            "rough": local_box_selector.path_quality_prior(dict(path), frames),
            "prior": local_box_selector.local_box_family_prior(
                str(family),
                dict(family_meta),
            ),
        }
        row.update(final_candidate.family_name_features(str(family), source=source))
        row.update(_background_columns(background_stats.get(family)))
        row.update(_residual_columns(residual_stats.get(family)))
        rows.append(row)

    return final_candidate.rank_normalized_feature_rows(
        rows,
        lower_is_better=LOWER_RANK_FEATURES,
        higher_is_better=HIGHER_RANK_FEATURES,
    )
