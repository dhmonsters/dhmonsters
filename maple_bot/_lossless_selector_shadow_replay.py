# 무손실 녹화에서 selector_shadow를 오프라인 재생하고 커서 GT로 채점합니다.
from __future__ import annotations

import argparse
import glob
import json
import math
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Mapping, Sequence

import cv2
import numpy as np

from _local_residual_signal import local_residual_contrast
import _phase_catalog_score as phase_catalog
from core.vision.transparent_family_selector_runtime import TransparentFamilySelectorRuntime
from core.vision.transparent_selector_shadow import TransparentSelectorShadow


ROOT = Path(__file__).resolve().parent
LOSSLESS_NAMES = ("000_0621_165634", "000_0621_180636")
CURSOR_EXCLUDES = {
    "000_0621_165634": ((0, 3), (36, 42)),
    "000_0621_180636": ((97, 107),),
}
TRACK_ANCHOR_FAMILY = "panel_default_center_mild_state_mild"
RAW_RANK_FAMILY_PREFIX = f"{TRACK_ANCHOR_FAMILY}_raw_rank"
RAW_CONTINUITY_FAMILY_PREFIX = f"{TRACK_ANCHOR_FAMILY}_raw_cont"


Point = tuple[float, float]


@dataclass(frozen=True)
class _RescueHypothesis:
    score: float
    last: Point
    velocity: Point
    path: dict[int, Point]


def _point(value: object) -> Point | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def cursor_center(bgr) -> Point | None:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([140, 60, 60]), np.array([175, 255, 255]))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < 8:
        return None
    moments = cv2.moments(contour)
    if moments["m00"] <= 0:
        return None
    return (moments["m10"] / moments["m00"], moments["m01"] / moments["m00"])


def is_cursor_excluded(name: str, frame_index: int) -> bool:
    return any(
        int(start) <= int(frame_index) <= int(end)
        for start, end in CURSOR_EXCLUDES.get(str(name), ())
    )


def lossless_valid_frames(
    name: str,
    gt_by_frame: Mapping[int, Point],
    *,
    frame_count: int,
    bad_frames: set[int] | None = None,
) -> list[int]:
    bad_frames = bad_frames or set()
    return [
        frame
        for frame in range(int(frame_count))
        if frame in gt_by_frame
        and frame not in bad_frames
        and not is_cursor_excluded(name, frame)
    ]


def score_path(
    path: Mapping[int, Point],
    gt_by_frame: Mapping[int, Point],
    frames: Sequence[int],
    *,
    success_px: float = 40.0,
) -> dict:
    errors = []
    worst = []
    for frame in frames:
        if frame not in path or frame not in gt_by_frame:
            continue
        error = _dist(path[frame], gt_by_frame[frame])
        errors.append(error)
        worst.append({
            "frame": int(frame),
            "error": round(error, 1),
            "point": [round(path[frame][0], 1), round(path[frame][1], 1)],
            "gt": [round(gt_by_frame[frame][0], 1), round(gt_by_frame[frame][1], 1)],
        })
    if not errors:
        return {
            "n": 0,
            "mean": float("nan"),
            "median": float("nan"),
            "max": float("nan"),
            "success": False,
            "worst": [],
        }
    worst.sort(key=lambda item: item["error"], reverse=True)
    return {
        "n": len(errors),
        "mean": float(np.mean(errors)),
        "median": float(median(errors)),
        "max": float(max(errors)),
        "success": float(np.mean(errors)) <= float(success_px),
        "worst": worst[:5],
    }


def path_health(
    path: Mapping[int, Point],
    *,
    frames: Sequence[int],
    frame_shape: Sequence[int] | None,
    margin: float = 40.0,
) -> dict:
    if frame_shape is None or len(frame_shape) < 2:
        height = width = 0.0
    else:
        height = float(frame_shape[0])
        width = float(frame_shape[1])

    points = [
        (int(frame), path[int(frame)])
        for frame in frames
        if int(frame) in path
    ]
    out_of_bounds = 0
    for _frame, point in points:
        x, y = point
        if (
            x < -float(margin)
            or y < -float(margin)
            or (width > 0.0 and x > width + float(margin))
            or (height > 0.0 and y > height + float(margin))
        ):
            out_of_bounds += 1

    steps = [
        _dist(points[index - 1][1], points[index][1])
        for index in range(1, len(points))
    ]
    covered = len(points)
    return {
        "covered": covered,
        "missing": max(0, len(frames) - covered),
        "out_of_bounds": out_of_bounds,
        "out_of_bounds_ratio": out_of_bounds / max(1, covered),
        "max_step": max(steps) if steps else 0.0,
        "mean_step": float(np.mean(steps)) if steps else 0.0,
    }


def select_path_by_track_health(
    track_path: Mapping[int, Point],
    rescue_path: Mapping[int, Point],
    visual_rescue_path: Mapping[int, Point],
    *,
    frames: Sequence[int],
    frame_shape: Sequence[int] | None,
    margin: float = 40.0,
    max_step_px: float = 240.0,
) -> tuple[dict[int, Point], str, dict]:
    health = {
        "track": path_health(track_path, frames=frames, frame_shape=frame_shape, margin=margin),
        "rescue_beam": path_health(rescue_path, frames=frames, frame_shape=frame_shape, margin=margin),
        "visual_rescue": path_health(visual_rescue_path, frames=frames, frame_shape=frame_shape, margin=margin),
    }
    track_unhealthy = (
        health["track"]["out_of_bounds"] > 0
        or health["track"]["max_step"] > float(max_step_px)
    )
    if track_unhealthy and visual_rescue_path:
        return dict(visual_rescue_path), "visual_rescue_track_unhealthy", health
    if rescue_path and health["rescue_beam"]["out_of_bounds"] < health["track"]["out_of_bounds"]:
        return dict(rescue_path), "rescue_beam_healthier", health
    return dict(track_path), "track_healthy", health


def _normalize_candidates(candidates: Sequence[Sequence[float]]) -> list[tuple[float, float, float, float, float]]:
    normalized = []
    for candidate in candidates:
        if len(candidate) < 2:
            continue
        score = float(candidate[2]) if len(candidate) >= 3 else 0.0
        width = float(candidate[3]) if len(candidate) >= 4 else 24.0
        height = float(candidate[4]) if len(candidate) >= 5 else 24.0
        normalized.append((float(candidate[0]), float(candidate[1]), score, width, height))
    return normalized


def _rank_to_ten(values: Sequence[float], *, high_is_better: bool = True) -> list[float]:
    if not values:
        return []
    numeric = [float(value) for value in values]
    if max(numeric) - min(numeric) <= 1e-6:
        return [0.0 for _value in numeric]
    if len(numeric) == 1:
        return [10.0]
    order = sorted(range(len(numeric)), key=lambda index: numeric[index], reverse=high_is_better)
    scores = [0.0 for _value in numeric]
    denom = max(1, len(numeric) - 1)
    for rank, index in enumerate(order):
        scores[index] = 10.0 * (denom - rank) / denom
    return scores


def visual_rank_scores_for_candidates(
    diff: np.ndarray,
    candidates: Sequence[Sequence[float]],
    *,
    metric: str = "center_mean",
    inner_radius: int = 6,
    outer_radius: int = 16,
    high_is_better: bool | None = None,
) -> list[float]:
    normalized = _normalize_candidates(candidates)
    if not normalized:
        return []
    if metric not in {"center_mean", "ring_mean", "contrast"}:
        raise ValueError(f"unknown visual metric: {metric}")
    if high_is_better is None:
        high_is_better = metric != "ring_mean"
    values = []
    for candidate in normalized:
        stats = local_residual_contrast(
            diff,
            (candidate[0], candidate[1]),
            inner_radius=inner_radius,
            outer_radius=outer_radius,
        )
        values.append(float(stats[metric]))
    return _rank_to_ten(values, high_is_better=bool(high_is_better))


def raw_candidate_anchor_paths(
    rows: Sequence[Mapping[str, object]],
    *,
    max_rank_families: int = 3,
    max_continuity_families: int = 6,
    max_candidates_per_frame: int = 24,
    max_step_px: float = 85.0,
) -> dict[str, dict[int, Point]]:
    paths: dict[str, dict[int, Point]] = {
        f"{RAW_RANK_FAMILY_PREFIX}{rank}": {}
        for rank in range(max(0, int(max_rank_families)))
    }
    continuity_paths: dict[str, dict[int, Point]] = {}
    last_points: dict[str, Point] = {}

    for frame, row in enumerate(rows):
        candidates = _normalize_candidates(row.get("cands", []))
        candidates.sort(key=lambda candidate: candidate[2], reverse=True)
        candidates = candidates[: max(1, int(max_candidates_per_frame))]
        points = [(candidate[0], candidate[1]) for candidate in candidates]
        if not points:
            continue

        for rank, point in enumerate(points[: max(0, int(max_rank_families))]):
            paths[f"{RAW_RANK_FAMILY_PREFIX}{rank}"][frame] = point

        if not last_points:
            for index, point in enumerate(points[: max(0, int(max_continuity_families))]):
                family = f"{RAW_CONTINUITY_FAMILY_PREFIX}{index}"
                continuity_paths[family] = {frame: point}
                last_points[family] = point
            continue

        used: set[int] = set()
        for family in sorted(last_points):
            previous = last_points[family]
            best_index = None
            best_error = float("inf")
            for index, point in enumerate(points):
                if index in used:
                    continue
                error = _dist(previous, point)
                if error < best_error:
                    best_index = index
                    best_error = error
            if best_index is None or best_error > float(max_step_px):
                continue
            used.add(best_index)
            point = points[best_index]
            continuity_paths.setdefault(family, {})[frame] = point
            last_points[family] = point

    paths.update(continuity_paths)
    return {
        family: path
        for family, path in paths.items()
        if path
    }


def track_rescue_candidate_path(
    rows: Sequence[Mapping[str, object]],
    *,
    max_candidates: int = 24,
    track_prediction_gate: float = 90.0,
    rescue_prediction_gate: float = 160.0,
    velocity_alpha: float = 0.55,
) -> dict[int, Point]:
    path: dict[int, Point] = {}
    last: Point | None = None
    velocity = (0.0, 0.0)

    for frame, row in enumerate(rows):
        candidates = _normalize_candidates(row.get("cands", []))
        candidates.sort(key=lambda candidate: candidate[2], reverse=True)
        points = [
            (candidate[0], candidate[1])
            for candidate in candidates[: max(1, int(max_candidates))]
        ]
        if not points:
            continue

        track = _point(row.get("track"))
        track_pick = (
            min(points, key=lambda point: _dist(point, track))
            if track is not None
            else None
        )
        if last is None:
            picked = track_pick if track_pick is not None else points[0]
        else:
            pred = (last[0] + velocity[0], last[1] + velocity[1])
            rescue_pick = min(points, key=lambda point: _dist(point, pred))
            track_ok = (
                track_pick is not None
                and _dist(track_pick, pred) <= float(track_prediction_gate)
            )
            rescue_ok = _dist(rescue_pick, pred) <= float(rescue_prediction_gate)
            if track_ok:
                picked = track_pick
            elif rescue_ok:
                picked = rescue_pick
            else:
                picked = track_pick if track_pick is not None else rescue_pick

        if last is not None:
            new_velocity = (picked[0] - last[0], picked[1] - last[1])
            alpha = float(velocity_alpha)
            velocity = (
                alpha * velocity[0] + (1.0 - alpha) * new_velocity[0],
                alpha * velocity[1] + (1.0 - alpha) * new_velocity[1],
            )
        last = picked
        path[frame] = picked

    return path


def track_rescue_beam_path(
    rows: Sequence[Mapping[str, object]],
    *,
    max_candidates: int = 24,
    keep: int = 24,
    branch: int = 6,
    track_prediction_gate: float = 90.0,
    track_snap_gate: float = 30.0,
    rescue_prediction_gate: float = 160.0,
    velocity_alpha: float = 0.55,
    continuity_weight: float = 10.0,
    track_weight: float = 8.0,
    detection_weight: float = 0.6,
    jump_penalty_weight: float = 0.03,
) -> dict[int, Point]:
    hypotheses: list[_RescueHypothesis] = []

    for frame, row in enumerate(rows):
        candidates = _normalize_candidates(row.get("cands", []))
        candidates.sort(key=lambda candidate: candidate[2], reverse=True)
        points = [
            ((candidate[0], candidate[1]), candidate[2])
            for candidate in candidates[: max(1, int(max_candidates))]
        ]
        if not points:
            continue

        track = _point(row.get("track"))
        if not hypotheses:
            seed_point = (
                min((point for point, _score in points), key=lambda point: _dist(point, track))
                if track is not None
                else points[0][0]
            )
            hypotheses = [
                _RescueHypothesis(
                    score=0.0,
                    last=seed_point,
                    velocity=(0.0, 0.0),
                    path={frame: seed_point},
                )
            ]
            continue

        expanded: list[_RescueHypothesis] = []
        for hyp in hypotheses:
            pred = (hyp.last[0] + hyp.velocity[0], hyp.last[1] + hyp.velocity[1])
            track_reliable = (
                track is not None
                and _dist(track, pred) <= float(track_prediction_gate)
            )
            scored_points = []
            for point, det_score in points:
                pred_dist = _dist(point, pred)
                continuity = max(
                    0.0,
                    1.0 - pred_dist / max(float(rescue_prediction_gate), 1e-6),
                ) * float(continuity_weight)
                track_bonus = 0.0
                if track_reliable and track is not None:
                    track_dist = _dist(point, track)
                    track_bonus = max(
                        0.0,
                        1.0 - track_dist / max(float(track_snap_gate), 1e-6),
                    ) * float(track_weight)
                local_score = (
                    continuity
                    + track_bonus
                    + float(detection_weight) * float(det_score)
                    - float(jump_penalty_weight) * pred_dist
                )
                scored_points.append((local_score, point))

            scored_points.sort(key=lambda item: item[0], reverse=True)
            for local_score, point in scored_points[: max(1, int(branch))]:
                new_velocity = (point[0] - hyp.last[0], point[1] - hyp.last[1])
                alpha = float(velocity_alpha)
                velocity = (
                    alpha * hyp.velocity[0] + (1.0 - alpha) * new_velocity[0],
                    alpha * hyp.velocity[1] + (1.0 - alpha) * new_velocity[1],
                )
                path = dict(hyp.path)
                path[frame] = point
                expanded.append(
                    _RescueHypothesis(
                        score=hyp.score + local_score,
                        last=point,
                        velocity=velocity,
                        path=path,
                    )
                )

        hypotheses = sorted(
            expanded,
            key=lambda hyp: hyp.score,
            reverse=True,
        )[: max(1, int(keep))]

    if not hypotheses:
        return {}
    return max(hypotheses, key=lambda hyp: hyp.score).path


def track_rescue_visual_beam_path(
    rows: Sequence[Mapping[str, object]],
    visual_scores_by_frame: Mapping[int, Sequence[float]],
    *,
    max_candidates: int = 24,
    keep: int = 24,
    branch: int = 6,
    track_prediction_gate: float = 90.0,
    track_snap_gate: float = 30.0,
    rescue_prediction_gate: float = 160.0,
    velocity_alpha: float = 0.55,
    continuity_weight: float = 10.0,
    track_weight: float = 8.0,
    detection_weight: float = 0.6,
    visual_weight: float = 1.0,
    jump_penalty_weight: float = 0.03,
) -> dict[int, Point]:
    hypotheses: list[_RescueHypothesis] = []

    for frame, row in enumerate(rows):
        indexed_candidates = [
            (index, candidate)
            for index, candidate in enumerate(_normalize_candidates(row.get("cands", [])))
        ]
        indexed_candidates.sort(key=lambda item: item[1][2], reverse=True)
        points = [
            ((candidate[0], candidate[1]), candidate[2], original_index)
            for original_index, candidate in indexed_candidates[: max(1, int(max_candidates))]
        ]
        if not points:
            continue

        frame_visual_scores = list(visual_scores_by_frame.get(frame, ()))
        track = _point(row.get("track"))
        if not hypotheses:
            seed_point = (
                min((point for point, _score, _index in points), key=lambda point: _dist(point, track))
                if track is not None
                else points[0][0]
            )
            hypotheses = [
                _RescueHypothesis(
                    score=0.0,
                    last=seed_point,
                    velocity=(0.0, 0.0),
                    path={frame: seed_point},
                )
            ]
            continue

        expanded: list[_RescueHypothesis] = []
        for hyp in hypotheses:
            pred = (hyp.last[0] + hyp.velocity[0], hyp.last[1] + hyp.velocity[1])
            track_reliable = (
                track is not None
                and _dist(track, pred) <= float(track_prediction_gate)
            )
            scored_points = []
            for point, det_score, original_index in points:
                pred_dist = _dist(point, pred)
                continuity = max(
                    0.0,
                    1.0 - pred_dist / max(float(rescue_prediction_gate), 1e-6),
                ) * float(continuity_weight)
                track_bonus = 0.0
                if track_reliable and track is not None:
                    track_dist = _dist(point, track)
                    track_bonus = max(
                        0.0,
                        1.0 - track_dist / max(float(track_snap_gate), 1e-6),
                    ) * float(track_weight)
                visual_score = (
                    float(frame_visual_scores[original_index])
                    if 0 <= original_index < len(frame_visual_scores)
                    else 0.0
                )
                local_score = (
                    continuity
                    + track_bonus
                    + float(detection_weight) * float(det_score)
                    + float(visual_weight) * visual_score
                    - float(jump_penalty_weight) * pred_dist
                )
                scored_points.append((local_score, point))

            scored_points.sort(key=lambda item: item[0], reverse=True)
            for local_score, point in scored_points[: max(1, int(branch))]:
                new_velocity = (point[0] - hyp.last[0], point[1] - hyp.last[1])
                alpha = float(velocity_alpha)
                velocity = (
                    alpha * hyp.velocity[0] + (1.0 - alpha) * new_velocity[0],
                    alpha * hyp.velocity[1] + (1.0 - alpha) * new_velocity[1],
                )
                path = dict(hyp.path)
                path[frame] = point
                expanded.append(
                    _RescueHypothesis(
                        score=hyp.score + local_score,
                        last=point,
                        velocity=velocity,
                        path=path,
                    )
                )

        hypotheses = sorted(
            expanded,
            key=lambda hyp: hyp.score,
            reverse=True,
        )[: max(1, int(keep))]

    if not hypotheses:
        return {}
    return max(hypotheses, key=lambda hyp: hyp.score).path


def lossless_visual_scores_for_clip(
    clip: Mapping[str, object],
    *,
    metric: str = "center_mean",
    inner_radius: int = 6,
    outer_radius: int = 16,
) -> tuple[dict[int, list[float]], dict]:
    frames = list(clip.get("frames", []))
    rows = list(clip.get("rows", []))
    if not frames or not rows:
        return {}, {
            "prep_end": 0,
            "period": 0,
            "period_score": float("inf"),
            "period_delta": 0,
        }

    prep_end, white = phase_catalog.detect_prep(frames)
    csets = phase_catalog.candidate_sets(rows, None, white)
    period, period_score = phase_catalog.estimate_period_lag(csets, prep_end)
    step = max(1, int(round(period)))
    grays = [
        None if frame is None else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        for frame in frames
    ]

    scores_by_frame: dict[int, list[float]] = {}
    for frame, row in enumerate(rows):
        if frame < int(prep_end) or frame >= len(grays):
            continue
        lag = phase_catalog.choose_local_lag(csets, int(frame), int(period), int(prep_end))
        source = int(frame) - int(lag)
        while source >= int(prep_end) and source - step >= 0:
            source -= step
        if source < 0 or source >= len(grays):
            continue
        current_gray = grays[frame]
        source_gray = grays[source]
        if current_gray is None or source_gray is None or current_gray.shape != source_gray.shape:
            continue
        diff = cv2.absdiff(current_gray, source_gray).astype(np.float32)
        scores = visual_rank_scores_for_candidates(
            diff,
            row.get("cands", []),
            metric=metric,
            inner_radius=inner_radius,
            outer_radius=outer_radius,
        )
        if scores:
            scores_by_frame[int(frame)] = scores

    return scores_by_frame, {
        "prep_end": int(prep_end),
        "period": int(period),
        "period_score": float(period_score),
        "period_delta": int(period) - int(prep_end),
    }


def replay_shadow_path_from_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    runtime=None,
    clip_id: str = "lossless",
    window: int = 24,
    min_frames: int = 8,
    max_candidates: int = 24,
    include_local_box: bool = True,
    include_raw_candidate_anchors: bool = False,
    raw_rank_families: int = 3,
    raw_continuity_families: int = 6,
) -> tuple[dict[int, Point], dict[int, dict]]:
    runtime = runtime or TransparentFamilySelectorRuntime()
    raw_paths = (
        raw_candidate_anchor_paths(
            rows,
            max_rank_families=raw_rank_families,
            max_continuity_families=raw_continuity_families,
            max_candidates_per_frame=max_candidates,
        )
        if include_raw_candidate_anchors
        else {}
    )
    shadow = TransparentSelectorShadow(
        runtime,
        clip_id=clip_id,
        window=window,
        min_frames=min_frames,
        emit_every=1,
        max_candidates=max_candidates,
        include_local_box=include_local_box,
    )
    path: dict[int, Point] = {}
    records: dict[int, dict] = {}
    for frame, row in enumerate(rows):
        track = _point(row.get("track"))
        anchors = {}
        if track is not None:
            anchors[TRACK_ANCHOR_FAMILY] = track
        engine = row.get("engine")
        if isinstance(engine, Mapping):
            engine_track = _point(engine.get("track"))
            if engine_track is not None:
                anchors["phase_catalog_center_mild_state_mild"] = engine_track
        if include_raw_candidate_anchors:
            for family, raw_path in raw_paths.items():
                point = raw_path.get(frame)
                if point is not None:
                    anchors[family] = point
        if not anchors:
            continue
        record = shadow.update(
            frame,
            candidates=_normalize_candidates(row.get("cands", [])),
            anchors=anchors,
        )
        if not record or not record.get("available"):
            continue
        point = _point(record.get("point"))
        if point is None:
            continue
        path[frame] = point
        records[frame] = dict(record)
    return path, records


def load_lossless_clip(name: str, *, root: Path = ROOT) -> dict:
    base = root / "_record_debug" / name
    png_paths = sorted(glob.glob(str(base) + "_png/*.png"))
    frames = [cv2.imread(path) for path in png_paths]
    rows = [json.loads(line) for line in (base.with_suffix(".jsonl")).read_text(encoding="utf-8").splitlines()]
    count = min(len(frames), len(rows))
    frames = frames[:count]
    rows = rows[:count]
    shapes = [None if frame is None else frame.shape[:2] for frame in frames]
    base_shape = next((shape for shape in shapes if shape is not None), None)
    bad_frames = {
        frame
        for frame, shape in enumerate(shapes)
        if shape != base_shape
    }
    gt_by_frame = {
        frame: center
        for frame, image in enumerate(frames)
        for center in [None if image is None else cursor_center(image)]
        if center is not None
    }
    return {
        "name": name,
        "png_frames": len(frames),
        "jsonl_rows": len(rows),
        "frames": frames,
        "frame_shape": base_shape,
        "rows": rows,
        "bad_frames": bad_frames,
        "bad_frame_names": [
            Path(png_paths[frame]).name
            for frame in sorted(bad_frames)
            if frame < len(png_paths)
        ],
        "gt_by_frame": gt_by_frame,
    }


def raw_candidate_oracle_path(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    frames: Sequence[int],
) -> dict[int, Point]:
    path = {}
    for frame in frames:
        gt = gt_by_frame.get(frame)
        if gt is None:
            continue
        candidates = _normalize_candidates(rows[frame].get("cands", []))
        if not candidates:
            continue
        best = min(candidates, key=lambda candidate: _dist((candidate[0], candidate[1]), gt))
        path[frame] = (best[0], best[1])
    return path


def track_path_from_rows(rows: Sequence[Mapping[str, object]]) -> dict[int, Point]:
    return {
        frame: point
        for frame, row in enumerate(rows)
        for point in [_point(row.get("track"))]
        if point is not None
    }


def score_lossless_clip(name: str, *, runtime=None, root: Path = ROOT) -> dict:
    clip = load_lossless_clip(name, root=root)
    frames = lossless_valid_frames(
        name,
        clip["gt_by_frame"],
        frame_count=min(clip["png_frames"], clip["jsonl_rows"]),
        bad_frames=set(clip["bad_frames"]),
    )
    shadow_path, shadow_records = replay_shadow_path_from_rows(
        clip["rows"],
        runtime=runtime,
        clip_id=name,
    )
    track_path = track_path_from_rows(clip["rows"])
    rescue_path = track_rescue_beam_path(
        clip["rows"],
        keep=24,
        branch=8,
        rescue_prediction_gate=220.0,
        detection_weight=0.1,
    )
    visual_scores, visual_meta = lossless_visual_scores_for_clip(
        clip,
        metric="center_mean",
    )
    visual_rescue_path = track_rescue_visual_beam_path(
        clip["rows"],
        visual_scores,
        keep=32,
        branch=12,
        rescue_prediction_gate=260.0,
        track_prediction_gate=45.0,
        continuity_weight=6.0,
        track_weight=1.0,
        detection_weight=0.0,
        visual_weight=1.0,
    )
    selected_path, selected_reason, selected_health = select_path_by_track_health(
        track_path,
        rescue_path,
        visual_rescue_path,
        frames=frames,
        frame_shape=clip["frame_shape"],
    )
    oracle_path = raw_candidate_oracle_path(clip["rows"], clip["gt_by_frame"], frames)
    return {
        "name": name,
        "png_frames": clip["png_frames"],
        "jsonl_rows": clip["jsonl_rows"],
        "bad_frames": clip["bad_frame_names"],
        "cursor_gt_frames": len(clip["gt_by_frame"]) - len(clip["bad_frames"]),
        "scored_frames": len(frames),
        "shadow_records": len(shadow_records),
        "track": score_path(track_path, clip["gt_by_frame"], frames),
        "rescue_beam": score_path(rescue_path, clip["gt_by_frame"], frames),
        "visual_meta": visual_meta,
        "visual_rescue": score_path(visual_rescue_path, clip["gt_by_frame"], frames),
        "selected_reason": selected_reason,
        "selected_health": selected_health,
        "selected": score_path(selected_path, clip["gt_by_frame"], frames),
        "shadow": score_path(shadow_path, clip["gt_by_frame"], frames),
        "oracle": score_path(oracle_path, clip["gt_by_frame"], frames),
    }


def _fmt_score(score: Mapping[str, object]) -> str:
    if not score.get("n"):
        return "평가 불가"
    return (
        f"mean {float(score['mean']):.1f}px, "
        f"median {float(score['median']):.1f}px, "
        f"max {float(score['max']):.1f}px, "
        f"n {int(score['n'])}, "
        f"{'성공' if score.get('success') else '실패'}"
    )


def markdown_report(results: Sequence[Mapping[str, object]]) -> str:
    lines = [
        "# 무손실 selector shadow replay v1 결과",
        "",
        "기존 무손실 JSONL의 `cands`와 `track`을 입력으로 `selector_shadow`를 오프라인 재생했다.",
        "",
        "| 클립 | 이상 프레임 | 채점 프레임 | raw 후보 oracle | 기존 track | shadow replay |",
        "|---|---|---:|---|---|---|",
    ]
    for result in results:
        bad = ", ".join(result["bad_frames"]) if result["bad_frames"] else "없음"
        lines.append(
            f"| `{result['name']}` | {bad} | {result['scored_frames']} | "
            f"{_fmt_score(result['oracle'])} | {_fmt_score(result['track'])} | "
            f"{_fmt_score(result['shadow'])} |"
        )
    lines.extend([
        "",
        "## 해석",
        "",
        "- raw 후보 oracle은 후보 안에 정답이 있는지 보는 상한선이다.",
        "- shadow replay는 기존 `track`을 anchor로 삼는 1차 검증이다.",
        "- 이 결과가 기존 track보다 나쁘면 selector 문제가 아니라 anchor family 생성이 부족하다는 뜻이다.",
    ])
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="무손실 2판에서 selector_shadow replay를 채점합니다.")
    parser.add_argument("--out", default="03_output/2026-06-26_lossless_selector_shadow_replay_score_v1.md")
    args = parser.parse_args(argv)

    runtime = TransparentFamilySelectorRuntime()
    results = [score_lossless_clip(name, runtime=runtime) for name in LOSSLESS_NAMES]
    text = markdown_report(results)
    print(text)
    try:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    except PermissionError as exc:
        print(f"[write-skip] {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
