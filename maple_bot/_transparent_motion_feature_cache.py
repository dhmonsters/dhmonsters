# path pool에서 motion selector 학습용 feature cache row를 생성합니다.
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

import _background_identity_signal as background_identity
import _final_candidate_selector as final_candidate
import _local_box_family_score as local_box
import _local_residual_signal as local_residual
import _offset_state_score as offset_state
import _path_family_oracle as path_oracle
import _phase_catalog_score as phase_catalog
from core.vision.transparent_feature_rows import build_transparent_feature_rows


ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "03_output" / "2026-06-26_motion_feature_rows_v1.json"
Point = tuple[float, float]


def build_motion_feature_rows_from_pool(
    clip: str,
    paths: Mapping[str, Mapping[int, Point]],
    frames: Sequence[int],
    *,
    gt: Mapping[int, Point] | None = None,
    meta: Mapping[str, Mapping[str, object]] | None = None,
    candidate_sets: Mapping[int, Sequence[Sequence[float]]] | None = None,
    background_stats: Mapping[str, Mapping[str, object]] | None = None,
    residual_stats: Mapping[str, Mapping[str, object]] | None = None,
) -> list[dict]:
    rows = build_transparent_feature_rows(
        clip,
        paths,
        frames,
        meta=meta,
        candidate_sets=candidate_sets,
        background_stats=background_stats,
        residual_stats=residual_stats,
    )
    if gt is None:
        return rows

    out = []
    for row in rows:
        family = str(row["family"])
        score = path_oracle.score_path(dict(paths.get(family, {})), dict(gt))
        labeled = dict(row)
        labeled.update({
            "success": bool(score["success"]),
            "mean": float(score["mean"]),
            "max": float(score["max"]),
            "coverage": float(score["coverage"]),
        })
        out.append(labeled)
    return out


def build_clip_motion_feature_rows(
    name: str,
    *,
    max_local_box_families: int = 96,
    include_background: bool = True,
    include_residual: bool = True,
) -> list[dict]:
    gt = phase_catalog.load_gt(name)
    if not gt:
        return []
    frames = sorted(gt)
    paths, meta, _failures = local_box.local_box_family_paths(
        name,
        frames=frames,
        max_local_box_families=max_local_box_families,
    )
    candidate_sets = offset_state._load_candidate_sets(name)
    background_stats = None
    residual_stats = None

    if include_background:
        expected, _bg_meta = background_identity.load_expected_background_with_ids(
            name,
            frames,
        )
        background_stats = background_identity.score_paths_against_background(
            paths,
            expected,
            frames,
        )

    if include_residual:
        diff_by_frame, _diff_meta = local_residual.periodic_diff_by_frame(
            name,
            frames,
        )
        residual_stats = local_residual.score_paths_by_residual_contrast(
            paths,
            diff_by_frame,
            frames,
        )

    return build_motion_feature_rows_from_pool(
        name,
        paths,
        frames,
        gt=gt,
        meta=meta,
        candidate_sets=candidate_sets,
        background_stats=background_stats,
        residual_stats=residual_stats,
    )


def build_all_motion_feature_rows(
    names: Sequence[str] | None = None,
    *,
    max_local_box_families: int = 96,
) -> list[dict]:
    rows = []
    for name in names or phase_catalog.names_from_gt():
        print(f"build {name}", flush=True)
        rows.extend(
            build_clip_motion_feature_rows(
                name,
                max_local_box_families=max_local_box_families,
            )
        )
    return rows


def summarize_rows(rows: Sequence[Mapping[str, object]]) -> dict:
    clips = sorted({row.get("clip") for row in rows})
    selected = final_candidate.select_weighted_feature_rows(
        rows,
        {"rank_rough": 1.0},
    )
    summary = final_candidate.summarize_selected_rows(selected)
    return {
        "rows": len(rows),
        "clips": len(clips),
        "rough_success": summary["success"],
        "rough_total": summary["total"],
        "rough_mean": summary["mean"],
        "has_motion_div": any("motion_div" in row for row in rows),
        "has_rank_high_motion_div": any("rank_high_motion_div" in row for row in rows),
    }


def save_rows(path: str | Path, rows: Sequence[Mapping[str, object]]) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    final_candidate.save_feature_rows_cache(out, [dict(row) for row in rows])
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="motion feature cache를 생성합니다.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--max-local-box-families", type=int, default=96)
    parser.add_argument("names", nargs="*")
    args = parser.parse_args(argv)

    rows = build_all_motion_feature_rows(
        args.names or None,
        max_local_box_families=args.max_local_box_families,
    )
    summary = summarize_rows(rows)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    try:
        save_rows(args.out, rows)
        print(f"saved {args.out}")
    except PermissionError as exc:
        print(f"[write-skip] {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
