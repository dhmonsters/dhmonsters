# family 경로를 짧은 미래 구간까지 보고 선택하는 delayed selector 채점기입니다.
from __future__ import annotations

import csv
import io
import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

import _final_selector_score as final_selector
import _offset_state_score as offset_state
import _path_family_oracle as path_oracle
import _phase_catalog_score as phase_catalog


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "03_output"
Point = Tuple[float, float]


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def family_mode_prior(family: str) -> float:
    name = family.lower()
    prior = 0.0
    if "_offset_" in name:
        prior -= 7.0
    elif "_state_" in name:
        prior -= 4.0
    if "_center_mild" in name:
        prior -= 1.0
    if "_center_aggressive" in name:
        prior += 4.0
    if name.endswith("_aggressive"):
        prior -= 1.0
    if name.endswith("_medium"):
        prior -= 0.5
    return prior


def path_roughness_cost(path: Dict[int, Point], frames: Sequence[int]) -> float:
    pts = [(frame, path.get(frame)) for frame in frames if path.get(frame) is not None]
    if len(pts) < 3:
        return 1e5
    speeds = []
    accels = []
    for (fa, pa), (fb, pb) in zip(pts, pts[1:]):
        dt = max(1.0, float(fb - fa))
        speeds.append(((pb[0] - pa[0]) / dt, (pb[1] - pa[1]) / dt))
    for v1, v2 in zip(speeds, speeds[1:]):
        accels.append(math.hypot(v2[0] - v1[0], v2[1] - v1[1]))
    speed_mag = [math.hypot(vx, vy) for vx, vy in speeds]
    return float(np.median(accels) if accels else 0.0) + 0.08 * float(np.median(speed_mag))


def _background_match_distance(point: Point, expected_background, pos_tol: float) -> float | None:
    best = None
    for cand in expected_background:
        if len(cand) < 2:
            continue
        d = _dist(point, (float(cand[0]), float(cand[1])))
        if d <= float(pos_tol) and (best is None or d < best):
            best = d
    return best


def background_frame_costs(
    paths: Dict[str, Dict[int, Point]],
    frames: Sequence[int],
    expected_background_by_frame,
    *,
    pos_tol: float = 14.0,
    match_penalty: float = 18.0,
    miss_bonus: float = -1.5,
) -> Dict[int, Dict[str, float]]:
    costs: Dict[int, Dict[str, float]] = {}
    for frame in frames:
        expected = expected_background_by_frame.get(frame, [])
        costs[frame] = {}
        for family, path in paths.items():
            point = path.get(frame)
            if point is None:
                costs[frame][family] = 1e6
                continue
            match_dist = _background_match_distance(point, expected, pos_tol)
            if match_dist is None:
                costs[frame][family] = float(miss_bonus)
            else:
                closeness = 1.0 - min(float(match_dist) / max(float(pos_tol), 1e-6), 1.0)
                costs[frame][family] = float(match_penalty) * closeness
    return costs


def merge_frame_costs(
    base_costs: Dict[int, Dict[str, float]],
    background_costs: Dict[int, Dict[str, float]],
    *,
    background_weight: float = 1.0,
) -> Dict[int, Dict[str, float]]:
    out: Dict[int, Dict[str, float]] = {}
    frames = sorted(set(base_costs) | set(background_costs))
    for frame in frames:
        families = sorted(set(base_costs.get(frame, {})) | set(background_costs.get(frame, {})))
        out[frame] = {}
        for family in families:
            base = float(base_costs.get(frame, {}).get(family, 0.0))
            bg = float(background_costs.get(frame, {}).get(family, 0.0))
            out[frame][family] = base + float(background_weight) * bg
    return out


def expected_background_by_frame(name: str):
    frames = phase_catalog.load_frames(name)
    rows = phase_catalog.load_rows(name)
    wrows = phase_catalog.load_wrows(name)
    prep_end, white = phase_catalog.detect_prep(frames)
    csets = phase_catalog.candidate_sets(rows, wrows, white)
    period, _period_score = phase_catalog.estimate_period_lag(csets, prep_end)
    out = {}
    step = max(1, int(round(period)))
    for frame in range(prep_end, len(csets)):
        lag = phase_catalog.choose_local_lag(csets, frame, period, prep_end)
        src = frame - lag
        while src >= prep_end and src - step >= 0:
            src -= step
        out[frame] = csets[src] if src >= 0 else []
    return out


def _window_cost(
    path: Dict[int, Point],
    family: str,
    frames: Sequence[int],
    frame_costs: Dict[int, Dict[str, float]],
    local_weight: float,
    roughness_weight: float,
    prior_weight: float,
) -> float:
    local_vals = [
        float(frame_costs.get(frame, {}).get(family, 1e4))
        for frame in frames
        if path.get(frame) is not None
    ]
    if not local_vals:
        return 1e8
    return (
        float(local_weight) * float(np.median(local_vals))
        + float(roughness_weight) * path_roughness_cost(path, frames)
        + float(prior_weight) * family_mode_prior(family)
    )


def delayed_select_path(
    paths: Dict[str, Dict[int, Point]],
    frames: Sequence[int],
    frame_costs: Dict[int, Dict[str, float]],
    *,
    lookahead: int = 5,
    switch_penalty: float = 4.0,
    local_weight: float = 0.15,
    roughness_weight: float = 1.0,
    prior_weight: float = 1.0,
) -> Tuple[Dict[int, Point], List[str]]:
    frames = list(frames)
    families = sorted(paths)
    if not frames or not families:
        return {}, []

    selected: List[str] = []
    previous = None
    for idx, frame in enumerate(frames):
        window = frames[idx: idx + max(1, int(lookahead))]
        best = None
        for family in families:
            path = paths[family]
            if path.get(frame) is None:
                continue
            cost = _window_cost(
                path,
                family,
                window,
                frame_costs,
                local_weight,
                roughness_weight,
                prior_weight,
            )
            if previous is not None and family != previous:
                cost += float(switch_penalty)
            item = (cost, family)
            if best is None or item < best:
                best = item
        if best is None:
            selected.append(previous if previous is not None else families[0])
        else:
            previous = best[1]
            selected.append(previous)

    out = {
        frame: paths[family][frame]
        for frame, family in zip(frames, selected)
        if paths[family].get(frame) is not None
    }
    return out, selected


def run_clip(
    name: str,
    *,
    bg_weight: float = 0.0,
    bg_pos_tol: float = 14.0,
    bg_match_penalty: float = 18.0,
    bg_miss_bonus: float = -1.5,
    **kwargs,
):
    paths, _meta, _failures = offset_state.offset_state_family_paths(name)
    gt = phase_catalog.load_gt(name)
    frames = sorted(gt)
    frame_costs = final_selector.consensus_frame_costs(paths, frames)
    if bg_weight:
        bg_costs = background_frame_costs(
            paths,
            frames,
            expected_background_by_frame(name),
            pos_tol=bg_pos_tol,
            match_penalty=bg_match_penalty,
            miss_bonus=bg_miss_bonus,
        )
        frame_costs = merge_frame_costs(
            frame_costs,
            bg_costs,
            background_weight=bg_weight,
        )
    return delayed_select_path(paths, frames, frame_costs, **kwargs)


def score_clip(name: str, **kwargs):
    gt = phase_catalog.load_gt(name)
    if not gt:
        return None
    path, families = run_clip(name, **kwargs)
    score = path_oracle.score_path(path, gt)
    score["name"] = name
    score["switches"] = sum(1 for a, b in zip(families, families[1:]) if a != b)
    return score


def score_all(**kwargs):
    rows = []
    for name in phase_catalog.names_from_gt():
        row = score_clip(name, **kwargs)
        if row:
            rows.append(row)
    return rows


def summarize(rows):
    return {
        "success": sum(1 for row in rows if row["success"]),
        "total": len(rows),
        "mean": float(np.mean([row["mean"] for row in rows])) if rows else float("nan"),
    }


def csv_text(rows):
    fields = ["name", "mean", "max", "covered", "coverage", "success", "switches"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row[field] for field in fields})
    return buf.getvalue()


def markdown_text(rows):
    summary = summarize(rows)
    lines = [
        "# 2026-06-24 Delayed Family Selector Score",
        "",
        f"- result: {summary['success']}/{summary['total']} success, mean error {summary['mean']:.1f}px.",
        "",
        "| clip | mean | max | switches | result |",
        "|---|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['name']} | {row['mean']:.1f}px | {row['max']:.1f}px | "
            f"{row['switches']} | {'OK' if row['success'] else 'FAIL'} |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(rows):
    OUT_DIR.mkdir(exist_ok=True)
    version = 1
    while True:
        md_path = OUT_DIR / f"2026-06-24_delayed_selector_score_v{version}.md"
        csv_path = OUT_DIR / f"2026-06-24_delayed_selector_score_v{version}.csv"
        if not md_path.exists() and not csv_path.exists():
            break
        version += 1
    try:
        md_path.write_text(markdown_text(rows), encoding="utf-8")
        csv_path.write_text(csv_text(rows), encoding="utf-8")
    except PermissionError:
        return None, None
    return md_path, csv_path


def main():
    rows = score_all()
    summary = summarize(rows)
    print(f"delayed_selector: {summary['success']}/{summary['total']} mean={summary['mean']:.1f}px")
    for row in rows:
        print(f"{row['name']}: {row['mean']:.1f}px {'OK' if row['success'] else 'FAIL'}")
    md_path, csv_path = write_outputs(rows)
    if md_path and csv_path:
        print(f"saved: {md_path}")
        print(f"saved: {csv_path}")
    else:
        print("saved: skipped by current filesystem permission")
    print("\n=== CSV ===")
    print(csv_text(rows))


if __name__ == "__main__":
    main()
