# 16GT baseline selector가 고른 family를 실제 path generator로 재생 채점합니다.
from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Mapping, Sequence, Tuple

import numpy as np

import _local_box_family_score as local_box
import _path_family_oracle as path_oracle
import _phase_catalog_score as phase_catalog
from _offline_16gt_solver import DEFAULT_CACHE_PATH, solve_cached_16gt


Point = Tuple[float, float]
PathMap = Dict[str, Dict[int, Point]]


def selected_family_by_clip(selected_rows: Mapping[object, Mapping[str, object]]) -> dict[str, str]:
    return {
        str(clip): str(row.get("family", ""))
        for clip, row in selected_rows.items()
    }


def load_local_box_paths_for_clip(
    name: str,
    *,
    max_local_box_families: int = 96,
) -> PathMap:
    gt = phase_catalog.load_gt(name)
    frames = sorted(gt) if gt else None
    paths, _meta, _failures = local_box.local_box_family_paths(
        name,
        frames=frames,
        max_local_box_families=max_local_box_families,
    )
    return paths


def score_selected_family_paths(
    selected_families: Mapping[str, str],
    *,
    load_paths: Callable[[str], PathMap],
    load_gt: Callable[[str], Dict[int, Point]],
) -> list[dict]:
    rows = []
    for name in sorted(selected_families):
        family = str(selected_families[name])
        gt = load_gt(name)
        paths = load_paths(name)
        if family not in paths:
            rows.append({
                "name": name,
                "family": family,
                "mean": float("inf"),
                "max": float("inf"),
                "covered": 0,
                "coverage": 0.0,
                "success": False,
                "failure": "missing_family",
            })
            continue

        score = path_oracle.score_path(paths[family], gt)
        score.update({
            "name": name,
            "family": family,
            "failure": "",
        })
        rows.append(score)
    return rows


def summarize_path_scores(rows: Sequence[dict]) -> dict:
    means = [float(row.get("mean", 0.0) or 0.0) for row in rows]
    return {
        "success": sum(1 for row in rows if bool(row.get("success", False))),
        "total": len(rows),
        "mean": float(np.mean(means)) if means else float("nan"),
    }


def score_cached_16gt_selected_paths(
    cache_path: str | Path = DEFAULT_CACHE_PATH,
    *,
    max_local_box_families: int = 96,
) -> list[dict]:
    selected = selected_family_by_clip(solve_cached_16gt(cache_path))
    return score_selected_family_paths(
        selected,
        load_paths=lambda name: load_local_box_paths_for_clip(
            name,
            max_local_box_families=max_local_box_families,
        ),
        load_gt=phase_catalog.load_gt,
    )
