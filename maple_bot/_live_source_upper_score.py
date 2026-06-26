# live 기록에서 source별 family 상한을 분리해 채점하는 유틸리티입니다.
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

from _selector_shadow_gt_replay_score import load_red_gt, score_path


ROOT = Path(__file__).resolve().parent
Point = tuple[float, float]
RecordCandidate = tuple[float, float, float, float, float]
LocalBoxCandidate = tuple[float, float, float, float, float]
KNOWN_SOURCES = (
    "raw_candidate",
    "balanced_viterbi",
    "bg_split_viterbi",
    "strict_transition_viterbi",
    "panel_default",
    "merge_context",
    "phase_catalog",
)


def _point(value: object) -> Point | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _record_candidate(candidate: object) -> RecordCandidate | None:
    if not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes)):
        return None
    if len(candidate) < 2:
        return None
    try:
        score = float(candidate[2]) if len(candidate) >= 3 else 0.0
        width = float(candidate[3]) if len(candidate) >= 4 else 24.0
        height = float(candidate[4]) if len(candidate) >= 5 else 24.0
        return (
            float(candidate[0]),
            float(candidate[1]),
            score,
            width,
            height,
        )
    except (TypeError, ValueError):
        return None


def _local_box_candidate(candidate: RecordCandidate) -> LocalBoxCandidate:
    return (
        float(candidate[0]),
        float(candidate[1]),
        float(candidate[3]),
        float(candidate[4]),
        float(candidate[2]),
    )


def local_box_candidate_sets_from_rows(
    rows: Sequence[Mapping[str, object]],
) -> dict[int, list[LocalBoxCandidate]]:
    out: dict[int, list[LocalBoxCandidate]] = {}
    for frame, row in enumerate(rows):
        candidates = [
            parsed
            for candidate in row.get("cands", [])
            for parsed in [_record_candidate(candidate)]
            if parsed is not None
        ]
        out[int(frame)] = [_local_box_candidate(candidate) for candidate in candidates]
    return out


def build_record_source_paths(
    rows: Sequence[Mapping[str, object]],
    *,
    include_live: bool = True,
    live_pool_kwargs: Mapping[str, object] | None = None,
) -> dict[str, dict[int, Point]]:
    paths: dict[str, dict[int, Point]] = {
        "panel_default_center_mild_state_mild": {},
        "phase_catalog_center_mild_state_mild": {},
    }

    live_pool = None
    if include_live:
        from core.vision.transparent_live_family_pool import TransparentLiveFamilyPool

        live_pool = TransparentLiveFamilyPool(
            window=24,
            min_frames=8,
            **dict(live_pool_kwargs or {}),
        )
    seeded = False

    for frame, row in enumerate(rows):
        track = _point(row.get("track"))
        if track is not None:
            paths["panel_default_center_mild_state_mild"][int(frame)] = track

        engine = row.get("engine")
        if isinstance(engine, Mapping):
            engine_track = _point(engine.get("track"))
            if engine_track is not None:
                paths["phase_catalog_center_mild_state_mild"][int(frame)] = engine_track

        if live_pool is None:
            continue

        candidates = [
            parsed
            for candidate in row.get("cands", [])
            for parsed in [_record_candidate(candidate)]
            if parsed is not None
        ]
        white_anchor = None
        live_candidates = candidates
        if not seeded and track is not None:
            white_anchor = track
            live_candidates = []
            seeded = True
        decision = live_pool.update(
            int(frame),
            candidates=live_candidates,
            white_anchor=white_anchor,
        )
        for family, point in decision.points.items():
            paths.setdefault(str(family), {})[int(frame)] = (
                float(point[0]),
                float(point[1]),
            )

    return {family: path for family, path in paths.items() if path}


def augment_with_local_box(
    paths: Mapping[str, Mapping[int, Point]],
    candidate_sets: Mapping[int, Sequence[LocalBoxCandidate]],
    frames: Sequence[int],
    *,
    max_local_box_families: int | None = None,
) -> dict[str, dict[int, Point]]:
    import _local_box_family_score as local_box

    copied = {
        str(family): dict(path)
        for family, path in paths.items()
    }
    local_box_families = list(copied)
    if max_local_box_families is not None:
        local_box_families = local_box_families[: max(0, int(max_local_box_families))]
    return local_box.augment_local_box_paths(
        copied,
        candidate_sets,
        frames,
        local_box_families=local_box_families,
    )


def source_group_for_family(family: str) -> str:
    base = str(family).split("_lb_", 1)[0]
    lower = base.lower()
    for source in KNOWN_SOURCES:
        if lower.startswith(source):
            return source
    return base


def _source_row_rank(row: Mapping[str, object]) -> tuple[bool, float, float]:
    return (
        bool(row.get("success", False)),
        float(row.get("coverage", 0.0) or 0.0),
        -float(row.get("mean", float("inf"))),
    )


def best_by_source_group(
    paths: Mapping[str, Mapping[int, Point]],
    gt_by_frame: Mapping[int, Point],
    frames: Sequence[int],
    *,
    min_coverage: float = 0.9,
) -> dict[str, dict[str, object]]:
    best: dict[str, dict[str, object]] = {}
    total = max(1, len(frames))
    for family, path in paths.items():
        score = score_path(path, gt_by_frame, frames)
        if not score.get("n"):
            continue
        group = source_group_for_family(str(family))
        coverage = float(score["n"]) / float(total)
        row = {
            "family": str(family),
            "mean": float(score["mean"]),
            "max": float(score["max"]),
            "n": int(score["n"]),
            "coverage": coverage,
            "success": bool(score["success"]) and coverage >= float(min_coverage),
        }
        if group not in best or _source_row_rank(row) > _source_row_rank(best[group]):
            best[group] = row
    return best


def score_clip(
    name: str,
    *,
    root: Path = ROOT,
    include_local_box: bool = True,
    max_local_box_families: int | None = None,
    raw_fast: bool = False,
) -> dict[str, object]:
    from _selector_shadow_backfill import _load_jsonl

    rows = _load_jsonl(root / "_record_debug" / f"{name}.jsonl")
    gt = load_red_gt(name, root=root)
    frames = [frame for frame in sorted(gt) if frame < len(rows)]
    live_pool_kwargs = {}
    if raw_fast:
        live_pool_kwargs = {
            "enable_bg_mht": False,
            "enable_phase_catalog": False,
            "enable_phase_mht": False,
            "enable_raw_mht": False,
        }
    paths = build_record_source_paths(
        rows,
        include_live=True,
        live_pool_kwargs=live_pool_kwargs,
    )
    candidate_sets = local_box_candidate_sets_from_rows(rows)
    if include_local_box:
        augmented = augment_with_local_box(
            paths,
            candidate_sets,
            range(len(rows)),
            max_local_box_families=max_local_box_families,
        )
    else:
        augmented = paths
    return {
        "name": name,
        "gt_frames": len(frames),
        "base": best_by_source_group(paths, gt, frames),
        "local_box": best_by_source_group(augmented, gt, frames),
    }


def score_all(
    *,
    root: Path = ROOT,
    names: Sequence[str] | None = None,
    include_local_box: bool = True,
    max_local_box_families: int | None = None,
    raw_fast: bool = False,
) -> list[dict[str, object]]:
    if names is None:
        names = [
            path.name
            for path in sorted((root / "_gt_frames").iterdir())
            if path.is_dir()
        ]
    return [
        score_clip(
            str(name),
            root=root,
            include_local_box=include_local_box,
            max_local_box_families=max_local_box_families,
            raw_fast=raw_fast,
        )
        for name in names
    ]


def markdown_report(results: Sequence[Mapping[str, object]]) -> str:
    groups = sorted({
        group
        for result in results
        for table_name in ("base", "local_box")
        for group in (result.get(table_name, {}) or {})
    })
    lines = [
        "# live source별 상한 채점 결과",
        "",
        "| clip | GT | " + " | ".join(groups) + " |",
        "|---|---:" + "|---:" * len(groups) + "|",
    ]
    for result in results:
        cells = []
        local_box = result.get("local_box", {}) or {}
        for group in groups:
            row = local_box.get(group)
            if not row:
                cells.append("-")
                continue
            cells.append(f"{float(row['mean']):.1f}{' OK' if row.get('success') else ''}")
        lines.append(
            f"| `{result.get('name', '')}` | {int(result.get('gt_frames', 0) or 0)} | "
            + " | ".join(cells)
            + " |"
        )
    lines.extend([
        "",
        "## source별 성공 수",
        "",
    ])
    for group in groups:
        success = sum(
            1
            for result in results
            for row in [(result.get("local_box", {}) or {}).get(group)]
            if row and row.get("success")
        )
        lines.append(f"- `{group}`: {success}/{len(results)}.")
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="live 기록 source별 family 상한을 채점합니다.")
    parser.add_argument("names", nargs="*")
    parser.add_argument("--out", default="03_output/2026-06-26_live_source_upper_score_v1.md")
    parser.add_argument("--no-local-box", action="store_true")
    parser.add_argument("--max-local-box-families", type=int, default=None)
    parser.add_argument("--raw-fast", action="store_true")
    args = parser.parse_args(argv)

    results = score_all(
        names=args.names or None,
        include_local_box=not args.no_local_box,
        max_local_box_families=args.max_local_box_families,
        raw_fast=args.raw_fast,
    )
    text = markdown_report(results)
    print(text)
    print(json.dumps(results, ensure_ascii=False))
    out = ROOT / args.out
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    except PermissionError as exc:
        print(f"[write-skip] {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
