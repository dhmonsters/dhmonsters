# 라이브 후보 가족이 GT 구간을 끝까지 덮을 수 있는지 빠르게 채점합니다.
from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from _selector_shadow_backfill import _load_jsonl
from _selector_shadow_gt_replay_score import load_red_gt
from core.vision.transparent_live_family_pool import TransparentLiveFamilyPool


ROOT = Path(__file__).resolve().parent
Point = tuple[float, float]
Candidate = tuple[float, float, float, float, float]
DEFAULT_BOX_SWITCH_REL_PAIRS = frozenset({
    ("z0_n05", "p1_n05"),
    ("p1_p05", "n05_z0"),
    ("p05_p1", "n1_z0"),
    ("z0_p1", "z0_n05"),
})
DEFAULT_FAST_BOX_REL_PAIRS = frozenset({
    ("n05", "p05"),
    ("n05", "z0"),
    ("n1", "p05"),
    ("n1", "z0"),
    ("p05", "n05"),
    ("p05", "p05"),
    ("p05", "p1"),
    ("p05", "z0"),
    ("p1", "n05"),
    ("p1", "p05"),
    ("p1", "z0"),
    ("z0", "n05"),
    ("z0", "p05"),
    ("z0", "p1"),
})
DEFAULT_EVENT_GATE_CONT_INDICES = frozenset({0, 2, 4, 10, 11, 12, 13})
DEFAULT_EVENT_GATE_REL_KEYS = frozenset({
    "n05_p05",
    "n05_z0",
    "n1_p05",
    "n1_z0",
    "p05_n05",
    "p05_p05",
    "p05_p1",
    "p05_z0",
    "p1_n05",
    "p1_p05",
    "p1_z0",
    "z0_n05",
    "z0_p1",
})


def replay_live_family_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    family_pool: Any | None = None,
    live_max_candidates: int = 24,
) -> dict[str, dict[int, Point]]:
    pool = family_pool or TransparentLiveFamilyPool(
        window=24,
        min_frames=8,
        enable_bg_mht=False,
        enable_raw_mht=False,
        enable_phase_mht=False,
        enable_guarded_decal_identity=True,
    )
    paths: dict[str, dict[int, Point]] = {}
    seeded = False
    for index, row in enumerate(rows):
        frame_index = int(row.get("i", index) or index)
        primary = _point(row.get("track"))
        white_anchor = None
        live_candidates = _limit_candidates(_candidates(row.get("cands", [])), live_max_candidates)
        if not seeded and primary is not None:
            white_anchor = primary
            live_candidates = []
            seeded = True
        decision = pool.update(
            frame_index,
            candidates=live_candidates,
            white_anchor=white_anchor,
        )
        points = dict(decision.points)
        if primary is not None:
            points["panel_default_center_mild_state_mild"] = primary
        engine = _engine_track(row)
        if engine is not None:
            points["phase_catalog_center_mild_state_mild"] = engine
        for family, point in points.items():
            paths.setdefault(str(family), {})[index] = (float(point[0]), float(point[1]))
    return paths


def best_family_score(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    *,
    paths: Mapping[str, Mapping[int, Point]] | None = None,
    family_pool: Any | None = None,
    include_occlusion_variants: bool = False,
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
    candidate_sets: Mapping[int, Sequence[Sequence[float]]] | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    live_max_candidates: int = 24,
    event_gate_shortlist: bool = False,
) -> dict[str, object]:
    frames = [frame for frame in sorted(gt_by_frame) if frame < len(rows)]
    paths = paths or build_family_paths(
        rows,
        frames=frames,
        family_pool=family_pool,
        include_occlusion_variants=include_occlusion_variants,
        expected_by_frame=expected_by_frame,
        candidate_sets=candidate_sets,
        live_max_candidates=live_max_candidates,
        event_gate_shortlist=event_gate_shortlist,
    )
    best: dict[str, object] | None = None
    for family, path in paths.items():
        score = _score_path(
            path,
            gt_by_frame,
            frames,
            success_px=success_px,
            min_coverage=min_coverage,
        )
        item = {
            "family": family,
            **score,
        }
        if best is None or _score_rank(item) > _score_rank(best):
            best = item
    if best is None:
        return {
            "family": "",
            "n": 0,
            "coverage": 0.0,
            "mean": float("inf"),
            "max": float("inf"),
            "success": False,
        }
    return best


def selected_family_score(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    *,
    paths: Mapping[str, Mapping[int, Point]] | None = None,
    family_pool: Any | None = None,
    include_occlusion_variants: bool = False,
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
    candidate_sets: Mapping[int, Sequence[Sequence[float]]] | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    live_max_candidates: int = 24,
    event_gate_shortlist: bool = True,
) -> dict[str, object]:
    frames = [frame for frame in sorted(gt_by_frame) if frame < len(rows)]
    paths = paths or build_family_paths(
        rows,
        frames=frames,
        family_pool=family_pool,
        include_occlusion_variants=include_occlusion_variants,
        expected_by_frame=expected_by_frame,
        candidate_sets=candidate_sets,
        live_max_candidates=live_max_candidates,
        event_gate_shortlist=event_gate_shortlist,
    )
    selection = select_identity_family(
        paths,
        frames=frames,
        anchor_points=_anchor_points_from_rows(rows),
        expected_by_frame=expected_by_frame,
    )
    family = str(selection.get("family", ""))
    path = paths.get(family, {})
    score = _score_path(
        path,
        gt_by_frame,
        frames,
        success_px=success_px,
        min_coverage=min_coverage,
    )
    return {
        "selection": selection,
        "selected_family": {
            "family": family,
            **score,
        },
        "candidate_count": len(paths),
    }


def box_grid_family_score(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    *,
    paths: Mapping[str, Mapping[int, Point]] | None = None,
    family_pool: Any | None = None,
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    live_max_candidates: int = 24,
    event_gate_shortlist: bool = True,
) -> dict[str, object]:
    frames = [frame for frame in sorted(gt_by_frame) if frame < len(rows)]
    paths = paths or build_family_paths(
        rows,
        frames=frames,
        family_pool=family_pool,
        include_occlusion_variants=False,
        live_max_candidates=live_max_candidates,
        event_gate_shortlist=event_gate_shortlist,
    )
    selection = select_box_grid_family(
        paths,
        frames=frames,
        anchor_points=_anchor_points_from_rows(rows),
        expected_by_frame=expected_by_frame or {},
    )
    family = str(selection.get("family", ""))
    score = _score_path(
        paths.get(family, {}),
        gt_by_frame,
        frames,
        success_px=success_px,
        min_coverage=min_coverage,
    )
    return {
        "selection": selection,
        "box_grid_family": {
            "family": family,
            **score,
        },
        "candidate_count": len(paths),
    }


def build_family_paths(
    rows: Sequence[Mapping[str, object]],
    *,
    frames: Sequence[int],
    family_pool: Any | None = None,
    include_occlusion_variants: bool = False,
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
    candidate_sets: Mapping[int, Sequence[Sequence[float]]] | None = None,
    live_max_candidates: int = 24,
    event_gate_shortlist: bool = False,
) -> dict[str, Mapping[int, Point]]:
    paths = replay_live_family_rows(
        rows,
        family_pool=family_pool,
        live_max_candidates=live_max_candidates,
    )
    if include_occlusion_variants:
        paths.update(gap_fill_variant_paths(paths, frames=frames))
        paths.update(occlusion_variant_paths(
            paths,
            frames=frames,
            expected_by_frame=expected_by_frame or {},
            candidate_sets=candidate_sets or candidate_sets_from_rows(rows),
        ))
        paths.update(box_switch_variant_paths(paths, frames=frames))
    if event_gate_shortlist:
        paths = event_gate_shortlist_paths(paths)
    return dict(paths)


def event_gate_shortlist_paths(
    paths: Mapping[str, Mapping[int, Point]],
    *,
    cont_indices: Sequence[int] | None = None,
    rel_keys: Sequence[str] | None = None,
) -> dict[str, Mapping[int, Point]]:
    allowed_cont = set(cont_indices or DEFAULT_EVENT_GATE_CONT_INDICES)
    allowed_rels = set(rel_keys or DEFAULT_EVENT_GATE_REL_KEYS)
    return {
        str(family): path
        for family, path in paths.items()
        if _is_event_gate_family(str(family), allowed_cont, allowed_rels)
    }


def _is_event_gate_family(
    family: str,
    allowed_cont: set[int],
    allowed_rels: set[str],
) -> bool:
    name = str(family)
    lowered = name.lower()
    if lowered.startswith("balanced_viterbi_center_mild_state_mild"):
        return True
    cont_index = _raw_cont_index(lowered)
    if cont_index is None or cont_index not in allowed_cont:
        return False
    if "box_switch" in lowered:
        return True
    rel_key = _box_rel_key(lowered)
    if rel_key is not None:
        return rel_key in allowed_rels
    return "center_mild_state_mild" in lowered


def _raw_cont_index(family: str) -> int | None:
    marker = "raw_candidate_cont"
    if marker not in family:
        return None
    suffix = family.split(marker, 1)[1]
    digits = []
    for char in suffix:
        if not char.isdigit():
            break
        digits.append(char)
    if not digits:
        return None
    return int("".join(digits))


def _box_rel_key(family: str) -> str | None:
    marker = "_box_rel_"
    if marker not in family:
        return None
    suffix = family.split(marker, 1)[1]
    parts = suffix.split("_")
    if len(parts) < 2:
        return None
    x_label, y_label = parts[0], parts[1]
    labels = {"n1", "n05", "z0", "p05", "p1"}
    if x_label not in labels or y_label not in labels:
        return None
    return f"{x_label}_{y_label}"


def select_event_gate_family(
    paths: Mapping[str, Mapping[int, Point]],
    *,
    frames: Sequence[int],
    anchor_points: Mapping[int, Point] | None = None,
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
) -> dict[str, object]:
    if not paths:
        return {"family": "", "judge": "none", "score": float("-inf")}
    ranked = []
    for family, path in paths.items():
        score, judge = _event_gate_score(
            str(family),
            path,
            frames,
            anchor_points=anchor_points,
            paths=paths,
            expected_by_frame=expected_by_frame,
        )
        ranked.append((score, str(family), judge))
    score, family, judge = max(ranked, key=lambda item: (item[0], item[1]))
    return {
        "family": family,
        "judge": judge,
        "score": score,
    }


def select_identity_family(
    paths: Mapping[str, Mapping[int, Point]],
    *,
    frames: Sequence[int],
    anchor_points: Mapping[int, Point] | None = None,
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
    box_grid_threshold: float = 1.0,
) -> dict[str, object]:
    event = select_event_gate_family(
        paths,
        frames=frames,
        anchor_points=anchor_points,
        expected_by_frame=expected_by_frame,
    )
    grid = select_box_grid_family(
        paths,
        frames=frames,
        anchor_points=anchor_points,
        expected_by_frame=expected_by_frame,
    )
    if float(grid.get("score", float("-inf"))) >= float(box_grid_threshold):
        return grid
    return event


def _event_gate_score(
    family: str,
    path: Mapping[int, Point],
    frames: Sequence[int],
    *,
    anchor_points: Mapping[int, Point] | None = None,
    paths: Mapping[str, Mapping[int, Point]] | None = None,
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
) -> tuple[float, str]:
    if anchor_points:
        return _anchor_gate_score(
            family,
            path,
            frames,
            anchor_points,
            paths=paths,
            expected_by_frame=expected_by_frame,
        )
    name = family.lower()
    motion = _path_motion_stats(path, frames)
    cont_index = _raw_cont_index(name)
    cont_bonus = _cont_index_bonus(cont_index)
    smooth_bonus = -0.08 * motion["mean_speed"] - 0.03 * motion["mean_accel"]

    if "occlusion_state" in name:
        rel_key = _box_rel_key(name)
        rel_bonus = _occlusion_rel_bonus(cont_index, rel_key)
        return (
            104.0
            + rel_bonus
            + smooth_bonus
            - 0.015 * motion["max_speed"],
            "occlusion",
        )
    if "box_switch" in name:
        switch_bonus = _switch_combo_bonus(name)
        switch_at = _box_switch_at(name)
        timing_penalty = 0.0 if switch_at is None else abs(float(switch_at) - 80.0) * 0.05
        return (
            106.0
            + cont_bonus
            + switch_bonus
            - timing_penalty
            + smooth_bonus,
            "switch",
        )
    if "_box_rel_" in name:
        return (
            108.0
            + cont_bonus
            + _rel_key_bonus(_box_rel_key(name))
            + smooth_bonus,
            "box_rel",
        )
    if "center_mild_state_mild" in name and name.startswith("raw_candidate_cont"):
        return (
            104.0
            + cont_bonus
            + smooth_bonus,
            "center",
        )
    if name.startswith("balanced_viterbi"):
        return (
            100.0
            + smooth_bonus,
            "balanced",
        )
    return (smooth_bonus, "fallback")


def _anchor_gate_score(
    family: str,
    path: Mapping[int, Point],
    frames: Sequence[int],
    anchor_points: Mapping[int, Point],
    *,
    paths: Mapping[str, Mapping[int, Point]] | None = None,
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
) -> tuple[float, str]:
    name = family.lower()
    motion = _path_motion_stats(path, frames)
    anchor_distance = _anchor_mean_distance(path, anchor_points)
    score = (
        -anchor_distance
        + _anchor_kind_bonus(family)
        - 0.03 * motion["mean_speed"]
        - 0.01 * motion["mean_accel"]
    )
    if "_gap_fill" in name:
        score -= 2.0
    if "occlusion_state" in name:
        original = (paths or {}).get(_occlusion_source_family(family), {})
        score += _occlusion_signal_adjustment(path, original, frames, expected_by_frame or {})
        return score, "anchor_occlusion"
    if "_box_switch_" in name:
        score += _switch_signal_penalty(
            path,
            frames,
            switch_frame=_box_switch_at(family),
            anchor_points=anchor_points,
        )
        return score, "anchor_switch"
    if "_box_rel_" in name:
        score += _box_rel_consistency_bonus(family, paths or {}, frames)
        return score, "anchor_box_rel"
    if "center_mild_state_mild" in name and name.startswith("raw_candidate_cont"):
        return score, "anchor_center"
    if name.startswith("balanced_viterbi"):
        return score, "anchor_balanced"
    return score, "anchor"


def _occlusion_signal_adjustment(
    corrected_path: Mapping[int, Point],
    original_path: Mapping[int, Point],
    frames: Sequence[int],
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]],
) -> float:
    deltas = []
    corrected_bg = 0
    original_bg = 0
    compared = 0
    rejoined = False
    changed_seen = False
    for frame in frames:
        frame = int(frame)
        corrected = corrected_path.get(frame)
        original = original_path.get(frame)
        if corrected is None or original is None:
            continue
        expected = expected_by_frame.get(frame, [])
        delta = _dist(corrected, original)
        deltas.append(delta)
        compared += 1
        if _matches_expected_background(corrected, expected, pos_tol=10.0):
            corrected_bg += 1
        if _matches_expected_background(original, expected, pos_tol=10.0):
            original_bg += 1
        if delta > 8.0:
            changed_seen = True
        elif changed_seen and not _matches_expected_background(corrected, expected, pos_tol=10.0):
            rejoined = True
    if compared == 0:
        return -12.0
    mean_delta = sum(deltas) / float(len(deltas)) if deltas else 0.0
    original_bg_ratio = float(original_bg) / float(compared)
    corrected_bg_ratio = float(corrected_bg) / float(compared)
    useful_correction = max(0.0, min(mean_delta, 45.0) - 4.0) * 0.18
    background_gain = (original_bg_ratio - corrected_bg_ratio) * 24.0
    rejoin_bonus = 6.0 if rejoined else -4.0 if mean_delta > 8.0 else 0.0
    over_correction_penalty = max(0.0, mean_delta - 90.0) * 0.08
    return useful_correction + background_gain + rejoin_bonus - corrected_bg_ratio * 18.0 - over_correction_penalty


def _switch_signal_penalty(
    path: Mapping[int, Point],
    frames: Sequence[int],
    *,
    switch_frame: int | None,
    anchor_points: Mapping[int, Point] | None = None,
) -> float:
    if switch_frame is None:
        return -8.0
    ordered = [int(frame) for frame in frames if int(frame) in path]
    if switch_frame not in ordered:
        return -10.0
    previous_frame = _nearest_existing_frame(ordered, switch_frame, step=-1)
    next_frame = _nearest_existing_frame(ordered, switch_frame, step=1)
    if previous_frame is None or next_frame is None:
        return -8.0
    previous_point = path[previous_frame]
    switch_point = path[switch_frame]
    next_point = path[next_frame]
    jump = _dist(previous_point, switch_point)
    left_velocity = _frame_velocity(previous_frame, previous_point, switch_frame, switch_point)
    right_velocity = _frame_velocity(switch_frame, switch_point, next_frame, next_point)
    accel = _dist(left_velocity, right_velocity)
    anchor_drift = _anchor_mean_distance(path, anchor_points or {})
    anchor_penalty = 0.0 if anchor_drift >= 9999.0 else anchor_drift * 0.03
    return -(0.12 * jump + 0.35 * accel + anchor_penalty)


def _box_rel_consistency_bonus(
    family: str,
    paths: Mapping[str, Mapping[int, Point]],
    frames: Sequence[int],
) -> float:
    parsed = _parse_box_rel_family(str(family))
    if parsed is None:
        return 0.0
    root, _rel, tail = parsed
    siblings = {
        str(name): path
        for name, path in paths.items()
        if _parse_box_rel_family(str(name)) is not None
        and _parse_box_rel_family(str(name))[0] == root
        and _parse_box_rel_family(str(name))[2] == tail
    }
    motion = _path_motion_stats(paths.get(str(family), {}), frames)
    stability = 8.0 - 0.08 * motion["mean_speed"] - 0.35 * motion["mean_accel"]
    if len(siblings) < 2:
        return stability
    median_penalty_values = []
    for frame in frames:
        frame = int(frame)
        points = [path[frame] for path in siblings.values() if frame in path]
        current = paths.get(str(family), {}).get(frame)
        if current is None or len(points) < 2:
            continue
        median = _median_point(points)
        median_penalty_values.append(_dist(current, median))
    median_penalty = (
        sum(median_penalty_values) / float(len(median_penalty_values))
        if median_penalty_values
        else 0.0
    )
    return stability - 0.03 * median_penalty


def select_box_grid_family(
    paths: Mapping[str, Mapping[int, Point]],
    *,
    frames: Sequence[int],
    anchor_points: Mapping[int, Point] | None = None,
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
) -> dict[str, object]:
    ranked = []
    for family, path in paths.items():
        if _box_grid_group_key(str(family)) is None:
            continue
        score = _box_grid_signal_score(
            str(family),
            path,
            paths,
            frames,
            anchor_points=anchor_points or {},
            expected_by_frame=expected_by_frame or {},
        )
        ranked.append((score, str(family)))
    if not ranked:
        return {"family": "", "judge": "box_grid", "score": float("-inf")}
    score, family = max(ranked, key=lambda item: (item[0], item[1]))
    return {"family": family, "judge": "box_grid", "score": score}


def _box_grid_group_key(family: str) -> str | None:
    parsed = _parse_box_rel_family(str(family))
    if parsed is None:
        return None
    root, _rel, tail = parsed
    return f"{root}{tail}"


def _box_grid_signal_score(
    family: str,
    path: Mapping[int, Point],
    paths: Mapping[str, Mapping[int, Point]],
    frames: Sequence[int],
    *,
    anchor_points: Mapping[int, Point],
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]],
) -> float:
    del anchor_points, paths
    rel_key = _box_rel_key(family) or ""
    cont_index = _raw_cont_index(family)
    return (
        _box_grid_rel_prior(rel_key)
        + _box_grid_cont_prior(cont_index)
        - 10.0 * _background_collision_ratio(path, frames, expected_by_frame)
    )


def _box_grid_rel_prior(rel_key: str | None) -> float:
    return {
        "p05_z0": 4.0,
        "z0_n05": 3.0,
        "n05_z0": 3.0,
        "p05_p05": 2.0,
        "p05_n05": 2.0,
        "n05_p05": 2.0,
    }.get(str(rel_key or ""), 0.0)


def _box_grid_cont_prior(index: int | None) -> float:
    if index in {10, 11, 12}:
        return 5.0
    if index in {0, 2, 4, 13}:
        return 2.0
    return 0.0


def _background_collision_ratio(
    path: Mapping[int, Point],
    frames: Sequence[int],
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]],
) -> float:
    checked = 0
    matched = 0
    for frame in frames:
        frame = int(frame)
        point = path.get(frame)
        if point is None:
            continue
        checked += 1
        if _matches_expected_background(point, expected_by_frame.get(frame, []), pos_tol=10.0):
            matched += 1
    if checked == 0:
        return 1.0
    return float(matched) / float(checked)


def _occlusion_source_family(family: str) -> str:
    name = str(family)
    if name.endswith("_occlusion_state"):
        return name[: -len("_occlusion_state")]
    return name


def _nearest_existing_frame(
    ordered_frames: Sequence[int],
    target_frame: int,
    *,
    step: int,
) -> int | None:
    if target_frame not in ordered_frames:
        return None
    index = ordered_frames.index(int(target_frame)) + int(step)
    if 0 <= index < len(ordered_frames):
        return int(ordered_frames[index])
    return None


def _frame_velocity(
    left_frame: int,
    left: Point,
    right_frame: int,
    right: Point,
) -> Point:
    delta = max(1, int(right_frame) - int(left_frame))
    return (
        (float(right[0]) - float(left[0])) / float(delta),
        (float(right[1]) - float(left[1])) / float(delta),
    )


def _median_point(points: Sequence[Point]) -> Point:
    xs = sorted(float(point[0]) for point in points)
    ys = sorted(float(point[1]) for point in points)
    mid = len(points) // 2
    if len(points) % 2 == 1:
        return (xs[mid], ys[mid])
    return ((xs[mid - 1] + xs[mid]) / 2.0, (ys[mid - 1] + ys[mid]) / 2.0)


def _anchor_kind_bonus(family: str) -> float:
    name = family.lower()
    if "occlusion_state" in name:
        combo = (_raw_cont_index(name), _box_rel_key(name))
        if combo in {
            (0, "p1_n05"),
            (0, "p05_p05"),
            (0, "n05_p05"),
            (4, "n1_p05"),
            (11, "p05_z0"),
            (11, "p05_n05"),
        }:
            return 4.0
        return -30.0
    if "_box_switch_" in name:
        return -14.0
    if "_box_rel_" in name:
        return 5.0
    if "center_mild_state_mild" in name and name.startswith("raw_candidate_cont"):
        return 8.0
    if name.startswith("balanced_viterbi"):
        return 6.0
    return -20.0


def _anchor_mean_distance(
    path: Mapping[int, Point],
    anchor_points: Mapping[int, Point],
) -> float:
    distances = [
        _dist(path[int(frame)], anchor)
        for frame, anchor in anchor_points.items()
        if int(frame) in path
    ]
    if not distances:
        return 9999.0
    return sum(distances) / float(len(distances))


def _anchor_points_from_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    max_frames: int = 30,
) -> dict[int, Point]:
    points: dict[int, Point] = {}
    for index, row in enumerate(rows[: max(0, int(max_frames))]):
        point = _point(row.get("track"))
        if point is not None:
            points[int(index)] = point
    return points


def _path_motion_stats(
    path: Mapping[int, Point],
    frames: Sequence[int],
) -> dict[str, float]:
    points = [
        (int(frame), path[int(frame)])
        for frame in frames
        if int(frame) in path
    ]
    if len(points) < 2:
        return {
            "mean_speed": 0.0,
            "max_speed": 0.0,
            "mean_accel": 0.0,
        }
    velocities = []
    speeds = []
    for (left_frame, left), (right_frame, right) in zip(points, points[1:]):
        delta = max(1, int(right_frame) - int(left_frame))
        velocity = (
            (float(right[0]) - float(left[0])) / float(delta),
            (float(right[1]) - float(left[1])) / float(delta),
        )
        velocities.append(velocity)
        speeds.append(math.hypot(velocity[0], velocity[1]))
    accels = [
        math.hypot(right[0] - left[0], right[1] - left[1])
        for left, right in zip(velocities, velocities[1:])
    ]
    return {
        "mean_speed": sum(speeds) / float(len(speeds)) if speeds else 0.0,
        "max_speed": max(speeds) if speeds else 0.0,
        "mean_accel": sum(accels) / float(len(accels)) if accels else 0.0,
    }


def _cont_index_bonus(index: int | None) -> float:
    if index in {10, 11, 12}:
        return 10.0
    if index in {0, 2, 4, 13}:
        return 6.0
    return 0.0


def _switch_pair_bonus(family: str) -> float:
    for left, right in DEFAULT_BOX_SWITCH_REL_PAIRS:
        if f"box_switch_{left}_to_{right}_" in family:
            return 10.0
    return 0.0


def _rel_key_bonus(rel_key: str | None) -> float:
    if rel_key in {"p05_n05", "p05_p05", "p05_z0", "n05_p05", "n1_p05"}:
        return 8.0
    if rel_key in {"p1_n05", "p1_z0", "p1_p05"}:
        return 6.0
    return 0.0


def _occlusion_rel_bonus(index: int | None, rel_key: str | None) -> float:
    if (index, rel_key) in {
        (0, "p1_n05"),
        (0, "p05_p05"),
        (0, "n05_p05"),
        (4, "n1_p05"),
        (11, "p05_z0"),
        (11, "p05_n05"),
    }:
        return 34.0
    if rel_key in {"p1_n05", "p05_p05", "p05_z0", "p05_n05", "n05_p05", "n1_p05"}:
        return -20.0
    return -42.0


def _switch_combo_bonus(family: str) -> float:
    combo = _box_switch_combo(family)
    if combo in {
        (0, "z0_n05", "p1_n05"),
        (2, "p1_p05", "n05_z0"),
        (10, "p05_p1", "n1_z0"),
        (10, "z0_n05", "p1_n05"),
        (13, "z0_p1", "z0_n05"),
    }:
        return 28.0
    if _switch_pair_bonus(family) > 0.0:
        return -18.0
    return -36.0


def _box_switch_combo(family: str) -> tuple[int | None, str | None, str | None] | None:
    if "_box_switch_" not in family:
        return None
    suffix = family.split("_box_switch_", 1)[1]
    if "_to_" not in suffix:
        return None
    left, right_suffix = suffix.split("_to_", 1)
    if "_at" not in right_suffix:
        return None
    right = right_suffix.split("_at", 1)[0]
    return (_raw_cont_index(family), left, right)


def _box_switch_at(family: str) -> int | None:
    if "_at" not in family:
        return None
    suffix = family.split("_at", 1)[1]
    digits = []
    for char in suffix:
        if not char.isdigit():
            break
        digits.append(char)
    if not digits:
        return None
    return int("".join(digits))


def box_switch_variant_paths(
    paths: Mapping[str, Mapping[int, Point]],
    *,
    frames: Sequence[int],
    switch_stride: int = 2,
    min_coverage: float = 0.9,
    rel_pairs: Sequence[tuple[str, str]] | None = None,
) -> dict[str, dict[int, Point]]:
    variants: dict[str, dict[int, Point]] = {}
    ordered = [int(frame) for frame in frames]
    if not ordered:
        return variants
    allowed_pairs = set(rel_pairs or DEFAULT_BOX_SWITCH_REL_PAIRS)
    groups: dict[tuple[str, str], dict[str, tuple[str, Mapping[int, Point]]]] = {}
    for family, path in paths.items():
        parsed = _parse_box_rel_family(str(family))
        if parsed is None:
            continue
        root, rel, tail = parsed
        coverage = sum(1 for frame in ordered if int(frame) in path) / float(len(ordered))
        if coverage < float(min_coverage):
            continue
        groups.setdefault((root, tail), {})[rel] = (str(family), path)

    for (root, tail), rel_paths in groups.items():
        rels = sorted(rel_paths)
        for left_rel in rels:
            _left_family, left_path = rel_paths[left_rel]
            for right_rel in rels:
                if right_rel == left_rel:
                    continue
                if (left_rel, right_rel) not in allowed_pairs:
                    continue
                _right_family, right_path = rel_paths[right_rel]
                for index, switch in enumerate(ordered):
                    if index == 0 or index % max(1, int(switch_stride)) != 0:
                        continue
                    path: dict[int, Point] = {}
                    for frame in ordered:
                        source = left_path if frame < switch else right_path
                        point = source.get(int(frame))
                        if point is not None:
                            path[int(frame)] = (float(point[0]), float(point[1]))
                    if path:
                        name = f"{root}_box_switch_{left_rel}_to_{right_rel}_at{switch}{tail}"
                        variants[name] = path
    return variants


def _parse_box_rel_family(family: str) -> tuple[str, str, str] | None:
    if "_gap_fill" in family or "_occlusion_state" in family:
        return None
    marker = "_box_rel_"
    if marker not in family:
        return None
    root, suffix = family.split(marker, 1)
    parts = suffix.split("_")
    if len(parts) < 3:
        return None
    x_label, y_label = parts[0], parts[1]
    labels = {"n1", "n05", "z0", "p05", "p1"}
    if x_label not in labels or y_label not in labels:
        return None
    return root, f"{x_label}_{y_label}", "_" + "_".join(parts[2:])


def gap_fill_variant_paths(
    paths: Mapping[str, Mapping[int, Point]],
    *,
    frames: Sequence[int],
    max_gap: int = 2,
) -> dict[str, dict[int, Point]]:
    variants: dict[str, dict[int, Point]] = {}
    ordered = [int(frame) for frame in frames]
    for family, path in paths.items():
        filled = {int(frame): (float(point[0]), float(point[1])) for frame, point in path.items()}
        for index, frame in enumerate(ordered):
            if frame in filled:
                continue
            previous = _nearest_known_frame(ordered, filled, index, step=-1)
            following = _nearest_known_frame(ordered, filled, index, step=1)
            if previous is None or following is None:
                continue
            previous_index, previous_frame = previous
            following_index, following_frame = following
            if following_index - previous_index - 1 > int(max_gap):
                continue
            span = float(following_frame - previous_frame)
            if span <= 0.0:
                continue
            left = filled[previous_frame]
            right = filled[following_frame]
            ratio = float(frame - previous_frame) / span
            filled[frame] = (
                float(left[0]) + (float(right[0]) - float(left[0])) * ratio,
                float(left[1]) + (float(right[1]) - float(left[1])) * ratio,
            )
        variants[f"{family}_gap_fill"] = filled
    return variants


def _nearest_known_frame(
    ordered_frames: Sequence[int],
    path: Mapping[int, Point],
    start_index: int,
    *,
    step: int,
) -> tuple[int, int] | None:
    index = int(start_index) + int(step)
    while 0 <= index < len(ordered_frames):
        frame = int(ordered_frames[index])
        if frame in path:
            return index, frame
        index += int(step)
    return None


def occlusion_variant_paths(
    paths: Mapping[str, Mapping[int, Point]],
    *,
    frames: Sequence[int],
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]],
    candidate_sets: Mapping[int, Sequence[Sequence[float]]],
) -> dict[str, dict[int, Point]]:
    variants: dict[str, dict[int, Point]] = {}
    normalized_candidates = {
        int(frame): _normalize_candidate_set(candidates)
        for frame, candidates in candidate_sets.items()
    }
    for family, path in paths.items():
        corrected = _correct_occlusion_path(
            dict(path),
            frames,
            expected_by_frame=expected_by_frame,
            candidate_sets=normalized_candidates,
        )
        if corrected:
            variants[f"{family}_occlusion_state"] = corrected
    return variants


def candidate_sets_from_rows(
    rows: Sequence[Mapping[str, object]],
) -> dict[int, list[Candidate]]:
    return {
        int(index): _candidates(row.get("cands", []))
        for index, row in enumerate(rows)
    }


def _correct_occlusion_path(
    observed_path: Mapping[int, Point],
    frames: Sequence[int],
    *,
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]],
    candidate_sets: Mapping[int, Sequence[Candidate]],
    enter_distance: float = 12.0,
    release_distance: float = 10.0,
    bg_pos_tol: float = 18.0,
    release_bg_pos_tol: float = 6.0,
    max_coast_frames: int = 5,
) -> dict[int, Point]:
    corrected: dict[int, Point] = {}
    previous: Point | None = None
    velocity: Point = (0.0, 0.0)
    coasting = False
    coast_count = 0

    for frame in frames:
        frame = int(frame)
        observed = observed_path.get(frame)
        if observed is None:
            if previous is None:
                continue
            predicted = _predict_point(previous, velocity)
            corrected[frame] = predicted
            previous = predicted
            coasting = True
            coast_count += 1
            continue

        observed = (float(observed[0]), float(observed[1]))
        if previous is None:
            corrected[frame] = observed
            previous = observed
            continue

        predicted = _predict_point(previous, velocity)
        expected = expected_by_frame.get(frame, [])
        candidates = candidate_sets.get(frame, [])

        if coasting:
            release = _best_occlusion_release(
                predicted,
                candidates,
                expected,
                release_distance=release_distance,
                release_bg_pos_tol=release_bg_pos_tol,
            )
            if release is not None:
                corrected[frame] = release
                velocity = _point_velocity(previous, release)
                previous = release
                coasting = False
                coast_count = 0
                continue
            if coast_count < int(max_coast_frames):
                corrected[frame] = predicted
                previous = predicted
                coast_count += 1
                continue

        if _matches_expected_background(observed, expected, pos_tol=bg_pos_tol) and _dist(observed, predicted) >= float(enter_distance):
            corrected[frame] = predicted
            previous = predicted
            coasting = True
            coast_count = 1
            continue

        corrected[frame] = observed
        velocity = _point_velocity(previous, observed)
        previous = observed
        coasting = False
        coast_count = 0

    return corrected


def _best_occlusion_release(
    predicted: Point,
    candidates: Sequence[Candidate],
    expected_background: Sequence[tuple[int, Sequence[float]]],
    *,
    release_distance: float,
    release_bg_pos_tol: float,
) -> Point | None:
    best: tuple[float, float, Point] | None = None
    for candidate in candidates:
        point = (float(candidate[0]), float(candidate[1]))
        if _matches_expected_background(point, expected_background, pos_tol=release_bg_pos_tol):
            continue
        distance = _dist(point, predicted)
        if distance > float(release_distance):
            continue
        item = (distance, -float(candidate[2]), point)
        if best is None or item < best:
            best = item
    return None if best is None else best[2]


def _matches_expected_background(
    point: Point,
    expected_background: Sequence[tuple[int, Sequence[float]]],
    *,
    pos_tol: float,
) -> bool:
    return any(
        _candidate_position_distance(point, expected) <= float(pos_tol)
        for _bg_id, expected in expected_background
    )


def _candidate_position_distance(point: Point, expected: Sequence[float]) -> float:
    if len(expected) < 4:
        return _dist(point, (float(expected[0]), float(expected[1])))
    half_w = float(expected[2]) / 2.0
    half_h = float(expected[3]) / 2.0
    dx = max(0.0, abs(float(point[0]) - float(expected[0])) - half_w)
    dy = max(0.0, abs(float(point[1]) - float(expected[1])) - half_h)
    return math.hypot(dx, dy)


def _predict_point(point: Point, velocity: Point) -> Point:
    return (float(point[0]) + float(velocity[0]), float(point[1]) + float(velocity[1]))


def _point_velocity(previous: Point, current: Point) -> Point:
    return (float(current[0]) - float(previous[0]), float(current[1]) - float(previous[1]))


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def score_clip(
    name: str,
    *,
    root: Path = ROOT,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    min_gt_frame: int = 50,
    live_max_candidates: int = 24,
    family_pool: Any | None = None,
    include_occlusion_variants: bool = False,
    event_gate_shortlist: bool = False,
    selector_scoreboard: bool = False,
) -> dict[str, object]:
    rows = _load_jsonl(root / "_record_debug" / f"{name}.jsonl")
    gt = load_red_gt(name, root=root, min_frame=min_gt_frame)
    frames = [frame for frame in sorted(gt) if frame < len(rows)]
    expected_by_frame = (
        expected_background_for_clip(name, frames=frames)
        if include_occlusion_variants
        else {}
    )
    candidate_sets = candidate_sets_from_rows(rows) if include_occlusion_variants else None
    paths_for_score = (
        build_family_paths(
            rows,
            frames=frames,
            family_pool=family_pool,
            include_occlusion_variants=include_occlusion_variants,
            expected_by_frame=expected_by_frame,
            candidate_sets=candidate_sets,
            live_max_candidates=live_max_candidates,
            event_gate_shortlist=event_gate_shortlist,
        )
        if selector_scoreboard
        else None
    )
    result = {
        "name": name,
        "frames": len(rows),
        "gt_frames": len(gt),
        "best_family": best_family_score(
            rows,
            gt,
            paths=paths_for_score,
            success_px=success_px,
            min_coverage=min_coverage,
            live_max_candidates=live_max_candidates,
            family_pool=family_pool,
            include_occlusion_variants=include_occlusion_variants,
            expected_by_frame=expected_by_frame,
            candidate_sets=candidate_sets,
            event_gate_shortlist=event_gate_shortlist,
        ),
    }
    if selector_scoreboard:
        selected = selected_family_score(
            rows,
            gt,
            paths=paths_for_score,
            success_px=success_px,
            min_coverage=min_coverage,
            live_max_candidates=live_max_candidates,
            family_pool=family_pool,
            include_occlusion_variants=include_occlusion_variants,
            expected_by_frame=expected_by_frame,
            candidate_sets=candidate_sets,
            event_gate_shortlist=event_gate_shortlist,
        )
        result["selected_family"] = selected["selected_family"]
        result["selection"] = selected.get("selection", {})
        result["selector_candidate_count"] = selected.get("candidate_count", 0)
    return result


def score_all(
    *,
    root: Path = ROOT,
    names: Sequence[str] | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    live_max_candidates: int = 24,
    fast_mode: bool = False,
    include_occlusion_variants: bool = False,
    event_gate_shortlist: bool = False,
    selector_scoreboard: bool = False,
) -> list[dict[str, object]]:
    if names is None:
        names = [
            path.name
            for path in sorted((root / "_gt_frames").iterdir())
            if path.is_dir()
        ]
    results = []
    for name in names:
        pool = _fast_family_pool() if fast_mode else None
        results.append(score_clip(
            str(name),
            root=root,
            success_px=success_px,
            min_coverage=min_coverage,
            live_max_candidates=live_max_candidates,
            family_pool=pool,
            include_occlusion_variants=include_occlusion_variants,
            event_gate_shortlist=event_gate_shortlist,
            selector_scoreboard=selector_scoreboard,
        ))
    return results


def _fast_family_pool() -> TransparentLiveFamilyPool:
    return TransparentLiveFamilyPool(
        window=16,
        min_frames=6,
        enable_phase_catalog=False,
        enable_bg_mht=False,
        enable_phase_mht=False,
        enable_raw_mht=False,
        enable_guarded_decal_identity=False,
        raw_rank_families=0,
        raw_continuity_families=20,
        raw_beam_families=0,
        raw_beam_spawn=0,
        raw_max_candidates_per_frame=24,
        raw_box_rel_pairs=DEFAULT_FAST_BOX_REL_PAIRS,
    )


def expected_background_for_clip(
    name: str,
    *,
    frames: Sequence[int],
) -> Mapping[int, Sequence[tuple[int, Sequence[float]]]]:
    try:
        from _background_identity_signal import load_expected_background_with_ids

        expected, _meta = load_expected_background_with_ids(str(name), list(frames))
        return expected
    except Exception:
        return {}


def summarize(results: Sequence[Mapping[str, object]]) -> dict[str, object]:
    total = len(results)
    success = 0
    for result in results:
        score = result.get("best_family")
        if isinstance(score, Mapping) and bool(score.get("success", False)):
            success += 1
    return {"success": success, "total": total}


def summarize_selected(results: Sequence[Mapping[str, object]]) -> dict[str, object]:
    total = len(results)
    success = 0
    for result in results:
        score = result.get("selected_family")
        if isinstance(score, Mapping) and bool(score.get("success", False)):
            success += 1
    return {"success": success, "total": total}


def _score_path(
    path: Mapping[int, Point],
    gt_by_frame: Mapping[int, Point],
    frames: Sequence[int],
    *,
    success_px: float,
    min_coverage: float,
) -> dict[str, object]:
    errors = []
    for frame in frames:
        point = path.get(int(frame))
        gt = gt_by_frame.get(int(frame))
        if point is None or gt is None:
            continue
        errors.append(math.hypot(point[0] - gt[0], point[1] - gt[1]))
    coverage = len(errors) / len(frames) if frames else 0.0
    if not errors:
        return {
            "n": 0,
            "coverage": coverage,
            "mean": float("inf"),
            "max": float("inf"),
            "success": False,
        }
    mean = sum(errors) / len(errors)
    return {
        "n": len(errors),
        "coverage": coverage,
        "mean": mean,
        "max": max(errors),
        "success": mean <= success_px and coverage >= min_coverage,
    }


def _score_rank(score: Mapping[str, object]) -> tuple[int, int, float, float]:
    return (
        int(bool(score.get("success", False))),
        int(float(score.get("coverage", 0.0) or 0.0) * 1000),
        -float(score.get("mean", float("inf"))),
        -float(score.get("max", float("inf"))),
    )


def _limit_candidates(candidates: Sequence[Candidate], limit: int) -> list[Candidate]:
    return sorted(candidates, key=lambda row: row[2], reverse=True)[: max(1, int(limit))]


def _engine_track(row: Mapping[str, object]) -> Point | None:
    engine = row.get("engine")
    if not isinstance(engine, Mapping):
        return None
    return _point(engine.get("track"))


def _candidates(value: object) -> list[Candidate]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    out = []
    for row in value:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) < 2:
            continue
        try:
            score = float(row[2]) if len(row) >= 3 else 0.0
            width = float(row[3]) if len(row) >= 4 else 24.0
            height = float(row[4]) if len(row) >= 5 else 24.0
            out.append((float(row[0]), float(row[1]), score, width, height))
        except (TypeError, ValueError):
            continue
    return out


def _normalize_candidate_set(candidates: Sequence[Sequence[float]]) -> list[Candidate]:
    return [
        candidate
        for row in candidates
        for candidate in [_candidate(row)]
        if candidate is not None
    ]


def _candidate(row: Sequence[float]) -> Candidate | None:
    if len(row) < 2:
        return None
    try:
        score = float(row[2]) if len(row) >= 3 else 0.0
        width = float(row[3]) if len(row) >= 4 else 24.0
        height = float(row[4]) if len(row) >= 5 else 24.0
        return (float(row[0]), float(row[1]), score, width, height)
    except (TypeError, ValueError):
        return None


def _point(value: object) -> Point | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--success-px", type=float, default=40.0)
    parser.add_argument("--min-coverage", type=float, default=0.9)
    parser.add_argument("--live-max-candidates", type=int, default=24)
    parser.add_argument("--fast-mode", action="store_true")
    parser.add_argument("--occlusion-variants", action="store_true")
    parser.add_argument("--event-gate-shortlist", action="store_true")
    parser.add_argument("--selector-scoreboard", action="store_true")
    parser.add_argument("--names", nargs="*")
    args = parser.parse_args()
    results = score_all(
        names=args.names,
        success_px=args.success_px,
        min_coverage=args.min_coverage,
        live_max_candidates=args.live_max_candidates,
        fast_mode=args.fast_mode,
        include_occlusion_variants=args.occlusion_variants,
        event_gate_shortlist=args.event_gate_shortlist,
        selector_scoreboard=args.selector_scoreboard,
    )
    print(json.dumps({
        "summary": summarize(results),
        "selected_summary": summarize_selected(results),
        "results": results,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
