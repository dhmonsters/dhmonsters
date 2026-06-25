# family anchor 주변 후보 박스 내부점 경로를 새 family로 생성하고 채점하는 스크립트입니다.
from __future__ import annotations

from dataclasses import dataclass
import csv
import io
import math
import sys
from pathlib import Path
from typing import Dict, Sequence, Tuple

import numpy as np

import _box_grid_viterbi_score as box_grid
import _offset_state_score as offset_state
import _path_family_oracle as path_oracle
import _phase_catalog_score as phase_catalog


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "03_output"
Point = Tuple[float, float]


@dataclass(frozen=True)
class LocalBoxVariant:
    name: str
    transition_weight: float
    accel_weight: float
    anchor_weight: float
    grid_size: int = 5
    shrink: float = 0.9
    max_dist: float = 110.0
    fallback_candidates: int = 2
    center_weight: float = 0.0


DEFAULT_VARIANTS = (
    LocalBoxVariant("smooth", transition_weight=0.2, accel_weight=0.3, anchor_weight=0.0),
    LocalBoxVariant("loose", transition_weight=0.1, accel_weight=0.0, anchor_weight=0.1),
    LocalBoxVariant("free", transition_weight=0.1, accel_weight=0.0, anchor_weight=0.0),
)


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _states_near_anchor(
    candidates,
    anchor: Point,
    *,
    grid_size: int,
    shrink: float,
    max_dist: float,
    fallback_candidates: int,
):
    ranked = sorted(
        enumerate(candidates),
        key=lambda item: _dist((float(item[1][0]), float(item[1][1])), anchor),
    )
    selected = [
        (idx, cand)
        for idx, cand in ranked
        if _dist((float(cand[0]), float(cand[1])), anchor) <= float(max_dist)
    ]
    if not selected and fallback_candidates:
        selected = ranked[: max(1, int(fallback_candidates))]

    states = []
    for cand_idx, cand in selected:
        states.extend(
            box_grid._grid_states_for_candidate(
                cand_idx,
                cand,
                int(grid_size),
                float(shrink),
            )
        )
    return states


def local_box_smooth_path(
    anchor_path: Dict[int, Point],
    candidate_sets,
    frames: Sequence[int],
    *,
    grid_size: int = 5,
    shrink: float = 0.9,
    max_dist: float = 110.0,
    fallback_candidates: int = 2,
    transition_weight: float = 0.2,
    accel_weight: float = 0.3,
    anchor_weight: float = 0.0,
    center_weight: float = 0.0,
) -> Dict[int, Point]:
    usable_frames = []
    frame_states = {}
    anchors = {}
    for frame in frames:
        anchor = anchor_path.get(frame)
        if anchor is None:
            continue
        states = _states_near_anchor(
            candidate_sets.get(frame, []),
            anchor,
            grid_size=grid_size,
            shrink=shrink,
            max_dist=max_dist,
            fallback_candidates=fallback_candidates,
        )
        if not states:
            continue
        usable_frames.append(frame)
        frame_states[frame] = states
        anchors[frame] = anchor

    return box_grid.viterbi_path(
        usable_frames,
        frame_states,
        transition_weight=transition_weight,
        accel_weight=accel_weight,
        anchor_points=anchors,
        anchor_weight=anchor_weight,
        center_weight=center_weight,
    )


def augment_local_box_paths(
    paths: Dict[str, Dict[int, Point]],
    candidate_sets,
    frames: Sequence[int],
    *,
    variants: Sequence[LocalBoxVariant] = DEFAULT_VARIANTS,
) -> Dict[str, Dict[int, Point]]:
    out = dict(paths)
    for family, path in paths.items():
        for variant in variants:
            out[f"{family}_lb_{variant.name}"] = local_box_smooth_path(
                path,
                candidate_sets,
                frames,
                grid_size=variant.grid_size,
                shrink=variant.shrink,
                max_dist=variant.max_dist,
                fallback_candidates=variant.fallback_candidates,
                transition_weight=variant.transition_weight,
                accel_weight=variant.accel_weight,
                anchor_weight=variant.anchor_weight,
                center_weight=variant.center_weight,
            )
    return out


def local_box_family_paths(name: str, *, frames: Sequence[int] | None = None):
    base_paths, meta, failures = offset_state.offset_state_family_paths(name)
    candidate_sets = offset_state._load_candidate_sets(name)
    if frames is None:
        frames = sorted(candidate_sets)
    paths = augment_local_box_paths(base_paths, candidate_sets, frames)
    for family in list(base_paths):
        for variant in DEFAULT_VARIANTS:
            paths_name = f"{family}_lb_{variant.name}"
            meta[paths_name] = {
                "source": family,
                "mode": "local_box",
                "variant": variant.name,
                "suspect_count": meta.get(family, {}).get("suspect_count", 0),
            }
    return paths, meta, failures


def score_clip(name: str, *, gt_frames_only: bool = True):
    gt = phase_catalog.load_gt(name)
    if not gt:
        return None
    frames = sorted(gt) if gt_frames_only else None
    paths, meta, failures = local_box_family_paths(name, frames=frames)
    scores = {
        family: path_oracle.score_path(path, gt)
        for family, path in paths.items()
    }
    best_family = min(scores, key=lambda family: scores[family]["mean"])
    best = scores[best_family]
    return {
        "name": name,
        "family_count": len(paths),
        "best_family": best_family,
        "best_mean": best["mean"],
        "best_max": best["max"],
        "best_coverage": best["coverage"],
        "best_success": best["success"],
        "mode": meta.get(best_family, {}).get("mode", "base"),
        "variant": meta.get(best_family, {}).get("variant", ""),
        "failures": "; ".join(failures),
    }


def score_all(names=None, *, gt_frames_only: bool = True):
    rows = []
    for name in names or phase_catalog.names_from_gt():
        print(f"score {name}", flush=True)
        row = score_clip(name, gt_frames_only=gt_frames_only)
        if row:
            rows.append(row)
    return rows


def summarize(rows):
    return {
        "success": sum(1 for row in rows if row["best_success"]),
        "total": len(rows),
        "mean": float(np.mean([row["best_mean"] for row in rows])) if rows else float("nan"),
    }


def csv_text(rows):
    buf = io.StringIO()
    fields = [
        "name", "family_count", "best_family", "mode", "variant",
        "best_mean", "best_max", "best_coverage", "best_success", "failures",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row[field] for field in fields})
    return buf.getvalue()


def markdown_text(rows):
    summary = summarize(rows)
    lines = [
        "# 2026-06-25 Local Box Family 결과",
        "",
        f"- best-family 상한: {summary['success']}/{summary['total']} 성공, 평균오차 {summary['mean']:.1f}px.",
        "- family anchor 주변 후보 박스 내부 grid를 Viterbi로 보정했다.",
        "",
        "| 클립 | best family | mode | variant | 평균오차 | 커버리지 | 성공 |",
        "|---|---|---|---|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['name']} | {row['best_family']} | {row['mode']} | "
            f"{row['variant']} | {row['best_mean']:.1f}px | "
            f"{row['best_coverage']:.2f} | {row['best_success']} |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(rows):
    OUT_DIR.mkdir(exist_ok=True)
    version = 1
    while True:
        md_path = OUT_DIR / f"2026-06-25_local_box_family_score_v{version}.md"
        csv_path = OUT_DIR / f"2026-06-25_local_box_family_score_v{version}.csv"
        if not md_path.exists() and not csv_path.exists():
            break
        version += 1
    md_path.write_text(markdown_text(rows), encoding="utf-8")
    csv_path.write_text(csv_text(rows), encoding="utf-8")
    return md_path, csv_path


def main():
    rows = score_all(sys.argv[1:] or None)
    summary = summarize(rows)
    print(f"local_box_family: {summary['success']}/{summary['total']} mean={summary['mean']:.1f}px")
    for row in rows:
        print(
            f"{row['name']}: {row['best_mean']:.1f}px "
            f"{'OK' if row['best_success'] else 'FAIL'} {row['best_family']}"
        )
    md_path, csv_path = write_outputs(rows)
    print(f"saved: {md_path}")
    print(f"saved: {csv_path}")
    print("\n=== CSV ===")
    print(csv_text(rows))


if __name__ == "__main__":
    main()
