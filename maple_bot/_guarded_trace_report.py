# guarded path가 크게 튀는 프레임의 후보와 GT를 추적하는 리포트 도구입니다.
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Mapping, Sequence

from _selector_shadow_gt_replay_score import (
    ROOT,
    _load_jsonl,
    backfill_selector_shadow_rows,
    guarded_emitted_path_from_rows,
    load_red_gt,
)

Point = tuple[float, float]


def trace_guarded_worst_rows(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    *,
    max_items: int = 8,
    candidates_per_frame: int = 5,
) -> list[dict[str, object]]:
    path = guarded_emitted_path_from_rows(rows)
    items = []
    for row_index, point in path.items():
        gt = gt_by_frame.get(int(row_index))
        if gt is None or int(row_index) >= len(rows):
            continue
        row = rows[int(row_index)]
        error = _dist(point, gt)
        items.append({
            "row_index": int(row_index),
            "frame": _frame(row, row_index),
            "error": round(error, 1),
            "point": _round_point(point),
            "gt": _round_point(gt),
            "reason": _guarded_reason(row),
            "step_from_previous": _step(path, row_index, -1),
            "step_to_next": _step(path, row_index, 1),
            "debug": _guarded_debug(row),
            "nearest_candidates": _nearest_candidates(
                row,
                point=point,
                gt=gt,
                limit=candidates_per_frame,
                sort_by="point",
            ),
            "gt_nearest_candidates": _nearest_candidates(
                row,
                point=point,
                gt=gt,
                limit=candidates_per_frame,
                sort_by="gt",
            ),
            "family_nearest_to_selected": _nearest_family_points(
                row,
                point=point,
                gt=gt,
                limit=candidates_per_frame,
                sort_by="point",
            ),
            "family_nearest_to_gt": _nearest_family_points(
                row,
                point=point,
                gt=gt,
                limit=candidates_per_frame,
                sort_by="gt",
            ),
        })
    items.sort(key=lambda item: float(item["error"]), reverse=True)
    return items[: max(0, int(max_items))]


def trace_clip(
    name: str,
    *,
    root: Path = ROOT,
    min_background_frames: int = 2,
    match_distance_px: float = 16.0,
    shape_pct: float = 6.0,
    max_step_px: float = 180.0,
    live_max_candidates: int = 8,
    max_items: int = 8,
) -> dict[str, object]:
    source = root / "_record_debug" / f"{name}.jsonl"
    rows = _load_jsonl(source)
    backfilled = backfill_selector_shadow_rows(
        rows,
        clip_id=name,
        window=24,
        min_frames=8,
        shadow_min_frames=1,
        emit_every=1,
        max_candidates=8,
        live_max_candidates=int(live_max_candidates),
        include_local_box=False,
        enable_guarded_decal_identity=True,
        guarded_decal_min_background_frames=min_background_frames,
        guarded_decal_match_distance_px=match_distance_px,
        guarded_decal_shape_pct=shape_pct,
        guarded_decal_max_step_px=max_step_px,
        include_live_family=True,
    )
    gt = load_red_gt(name, root=root, min_frame=50)
    config = {
        "min_bg": int(min_background_frames),
        "match_px": float(match_distance_px),
        "shape_pct": float(shape_pct),
        "max_step": float(max_step_px),
        "live_max_candidates": int(live_max_candidates),
    }
    return {
        "clip": name,
        "config": config,
        "items": trace_guarded_worst_rows(backfilled, gt, max_items=max_items),
    }


def write_markdown_report(report: Mapping[str, object]) -> str:
    config = report.get("config", {})
    if not isinstance(config, Mapping):
        config = {}
    lines = [
        "# guarded worst frame trace",
        "",
        f"- clip: `{report.get('clip', '')}`",
        (
            "- config: "
            f"min_bg={config.get('min_bg', '-')}, "
            f"match_px={config.get('match_px', '-')}, "
            f"shape_pct={config.get('shape_pct', '-')}, "
            f"max_step={config.get('max_step', '-')}, "
            f"live_max={config.get('live_max_candidates', '-')}"
        ),
        "",
    ]
    items = report.get("items", [])
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        items = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        lines.append(
            "## f{frame} row={row} err={error} reason={reason}".format(
                frame=item.get("frame", "-"),
                row=item.get("row_index", "-"),
                error=_fmt_float(item.get("error")),
                reason=item.get("reason", "-"),
            )
        )
        lines.append(
            "- selected={point} gt={gt} step_prev={prev} step_next={next}".format(
                point=item.get("point", []),
                gt=item.get("gt", []),
                prev=_fmt_float(item.get("step_from_previous")),
                next=_fmt_float(item.get("step_to_next")),
            )
        )
        debug = item.get("debug", {})
        if isinstance(debug, Mapping) and debug:
            lines.append(f"- debug={_compact_debug(debug)}")
        candidates = item.get("nearest_candidates", [])
        if isinstance(candidates, Sequence) and not isinstance(candidates, (str, bytes)):
            for index, candidate in enumerate(candidates):
                if not isinstance(candidate, Mapping):
                    continue
                lines.append(
                    "- cand{idx} point={point} score={score} rank={rank} live8={live8} d_sel={d_sel} d_gt={d_gt}".format(
                        idx=index,
                        point=candidate.get("point", []),
                        score=_fmt_float(candidate.get("score")),
                        rank=candidate.get("score_rank", "-"),
                        live8=candidate.get("in_live_top8", "-"),
                        d_sel=_fmt_float(candidate.get("dist_to_point")),
                        d_gt=_fmt_float(candidate.get("dist_to_gt")),
                    )
                )
        gt_candidates = item.get("gt_nearest_candidates", [])
        if isinstance(gt_candidates, Sequence) and not isinstance(gt_candidates, (str, bytes)):
            for index, candidate in enumerate(gt_candidates):
                if not isinstance(candidate, Mapping):
                    continue
                lines.append(
                    "- gt_cand{idx} point={point} score={score} rank={rank} live8={live8} d_sel={d_sel} d_gt={d_gt}".format(
                        idx=index,
                        point=candidate.get("point", []),
                        score=_fmt_float(candidate.get("score")),
                        rank=candidate.get("score_rank", "-"),
                        live8=candidate.get("in_live_top8", "-"),
                        d_sel=_fmt_float(candidate.get("dist_to_point")),
                        d_gt=_fmt_float(candidate.get("dist_to_gt")),
                    )
                )
        selected_families = item.get("family_nearest_to_selected", [])
        if isinstance(selected_families, Sequence) and not isinstance(selected_families, (str, bytes)):
            for index, family in enumerate(selected_families):
                if not isinstance(family, Mapping):
                    continue
                lines.append(
                    "- sel_family{idx} {family} point={point} d_sel={d_sel} d_gt={d_gt}".format(
                        idx=index,
                        family=family.get("family", ""),
                        point=family.get("point", []),
                        d_sel=_fmt_float(family.get("dist_to_point")),
                        d_gt=_fmt_float(family.get("dist_to_gt")),
                    )
                )
        gt_families = item.get("family_nearest_to_gt", [])
        if isinstance(gt_families, Sequence) and not isinstance(gt_families, (str, bytes)):
            for index, family in enumerate(gt_families):
                if not isinstance(family, Mapping):
                    continue
                lines.append(
                    "- gt_family{idx} {family} point={point} d_sel={d_sel} d_gt={d_gt}".format(
                        idx=index,
                        family=family.get("family", ""),
                        point=family.get("point", []),
                        d_sel=_fmt_float(family.get("dist_to_point")),
                        d_gt=_fmt_float(family.get("dist_to_gt")),
                    )
                )
        lines.append("")
    return "\n".join(lines) + "\n"


def _nearest_candidates(
    row: Mapping[str, object],
    *,
    point: Point,
    gt: Point,
    limit: int,
    sort_by: str = "point",
) -> list[dict[str, object]]:
    candidates = []
    raw = row.get("cands", [])
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    score_ranks = _candidate_score_ranks(raw)
    for value in raw:
        candidate = _candidate(value)
        if candidate is None:
            continue
        cand_point = (candidate[0], candidate[1])
        rank = score_ranks.get((candidate[0], candidate[1], candidate[2], candidate[3], candidate[4]))
        candidates.append({
            "point": _round_point(cand_point),
            "score": round(float(candidate[2]), 3),
            "score_rank": rank,
            "in_live_top8": rank is not None and int(rank) < 8,
            "size": [round(float(candidate[3]), 1), round(float(candidate[4]), 1)],
            "dist_to_point": round(_dist(cand_point, point), 1),
            "dist_to_gt": round(_dist(cand_point, gt), 1),
        })
    if sort_by == "gt":
        candidates.sort(key=lambda item: (float(item["dist_to_gt"]), float(item["dist_to_point"])))
    else:
        candidates.sort(key=lambda item: (float(item["dist_to_point"]), float(item["dist_to_gt"])))
    return candidates[: max(0, int(limit))]


def _nearest_family_points(
    row: Mapping[str, object],
    *,
    point: Point,
    gt: Point,
    limit: int,
    sort_by: str = "point",
) -> list[dict[str, object]]:
    live_family = row.get("live_family")
    if not isinstance(live_family, Mapping):
        return []
    points = live_family.get("points")
    if not isinstance(points, Mapping):
        return []
    items = []
    for family, value in points.items():
        family_point = _point(value)
        if family_point is None:
            continue
        items.append({
            "family": str(family),
            "point": _round_point(family_point),
            "dist_to_point": round(_dist(family_point, point), 1),
            "dist_to_gt": round(_dist(family_point, gt), 1),
        })
    if sort_by == "gt":
        items.sort(key=lambda item: (float(item["dist_to_gt"]), float(item["dist_to_point"]), str(item["family"])))
    else:
        items.sort(key=lambda item: (float(item["dist_to_point"]), float(item["dist_to_gt"]), str(item["family"])))
    return items[: max(0, int(limit))]


def _candidate(value: object) -> tuple[float, float, float, float, float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        return None
    try:
        return (
            float(value[0]),
            float(value[1]),
            float(value[2]) if len(value) > 2 else 0.0,
            float(value[3]) if len(value) > 3 else 0.0,
            float(value[4]) if len(value) > 4 else 0.0,
        )
    except (TypeError, ValueError):
        return None


def _candidate_score_ranks(raw: object) -> dict[tuple[float, float, float, float, float], int]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return {}
    candidates = []
    for value in raw:
        candidate = _candidate(value)
        if candidate is not None:
            candidates.append(candidate)
    ranked = sorted(enumerate(candidates), key=lambda item: (-float(item[1][2]), item[0]))
    return {candidate: rank for rank, (_index, candidate) in enumerate(ranked)}


def _point(value: object) -> Point | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _guarded_debug(row: Mapping[str, object]) -> Mapping[str, object]:
    live_family = row.get("live_family")
    if not isinstance(live_family, Mapping):
        return {}
    debug = live_family.get("debug")
    if not isinstance(debug, Mapping):
        return {}
    guarded = debug.get("guarded_decal_identity")
    if isinstance(guarded, Mapping):
        return guarded
    return {}


def _guarded_reason(row: Mapping[str, object]) -> str:
    debug = _guarded_debug(row)
    reason = str(debug.get("reason") or "")
    if not reason and bool(debug.get("accepted", False)):
        return "accepted"
    return reason or "-"


def _step(path: Mapping[int, Point], row_index: int, direction: int) -> float | None:
    other = int(row_index) + int(direction)
    if other not in path or row_index not in path:
        return None
    return round(_dist(path[int(row_index)], path[other]), 1)


def _frame(row: Mapping[str, object], fallback: int) -> int:
    try:
        return int(row.get("i", fallback) or fallback)
    except (TypeError, ValueError):
        return int(fallback)


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _round_point(point: Point) -> list[float]:
    return [round(float(point[0]), 1), round(float(point[1]), 1)]


def _fmt_float(value: object) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(number):
        return "-"
    return f"{number:.1f}"


def _compact_debug(debug: Mapping[str, object]) -> str:
    keys = ("reason", "background_frames", "expected_frames", "background_ratio", "max_step", "period")
    parts = []
    for key in keys:
        if key in debug:
            parts.append(f"{key}={debug[key]}")
    return ", ".join(parts) if parts else str(dict(debug))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="guarded path worst frame trace 리포트를 생성합니다.")
    parser.add_argument("names", nargs="+")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="03_output/2026-06-27_guarded_trace_report_v1.md")
    parser.add_argument("--min-bg", type=int, default=2)
    parser.add_argument("--match-px", type=float, default=16.0)
    parser.add_argument("--shape-pct", type=float, default=6.0)
    parser.add_argument("--max-step", type=float, default=180.0)
    parser.add_argument("--live-max-candidates", type=int, default=8)
    parser.add_argument("--items", type=int, default=8)
    args = parser.parse_args(argv)

    reports = [
        trace_clip(
            name,
            root=Path(args.root),
            min_background_frames=args.min_bg,
            match_distance_px=args.match_px,
            shape_pct=args.shape_pct,
            max_step_px=args.max_step,
            live_max_candidates=args.live_max_candidates,
            max_items=args.items,
        )
        for name in args.names
    ]
    text = "\n".join(write_markdown_report(report).rstrip() for report in reports) + "\n"
    print(text)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        out.write_text(text, encoding="utf-8")
    except PermissionError as exc:
        print(f"[write-skip] {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
