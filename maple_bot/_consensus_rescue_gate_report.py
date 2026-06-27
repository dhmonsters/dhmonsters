# consensus rescue 신뢰 게이트 후보 특징을 GT 분석용으로 정리합니다.
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parent
Point = tuple[float, float]
DEFAULT_GATE_CONFIGS: tuple[dict[str, float], ...] = (
    {
        "min_support_weight": 3.0,
        "max_avg_dist": 20.0,
        "min_primary_consensus_dist": 35.0,
        "max_consensus_step": 80.0,
    },
    {
        "min_support_weight": 3.0,
        "max_avg_dist": 16.0,
        "min_primary_consensus_dist": 45.0,
        "max_consensus_step": 80.0,
    },
    {
        "min_support_weight": 3.5,
        "max_avg_dist": 14.0,
        "min_primary_consensus_dist": 45.0,
        "max_consensus_step": 70.0,
    },
    {
        "min_support_weight": 4.0,
        "max_avg_dist": 12.0,
        "min_primary_consensus_dist": 60.0,
        "max_consensus_step": 60.0,
    },
)


def consensus_gate_feature_rows(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    *,
    frame_offset: int = 0,
) -> list[dict[str, object]]:
    feature_rows: list[dict[str, object]] = []
    previous_track: Point | None = None
    previous_consensus: Point | None = None

    for local_frame, row in enumerate(rows):
        frame = int(frame_offset) + int(local_frame)
        track = _point(row.get("track"))
        consensus = _consensus_point(row)
        gt = gt_by_frame.get(frame)
        if track is None or consensus is None or gt is None:
            if track is not None:
                previous_track = track
            if consensus is not None:
                previous_consensus = consensus
            continue

        debug = _consensus_debug(row)
        record = row.get("selector_shadow")
        record_map = record if isinstance(record, Mapping) else {}
        merge_context = record_map.get("merge_context")
        merge_map = merge_context if isinstance(merge_context, Mapping) else {}

        track_error = _dist(track, gt)
        consensus_error = _dist(consensus, gt)
        feature_rows.append({
            "frame": int(frame),
            "track_error": track_error,
            "consensus_error": consensus_error,
            "error_delta": track_error - consensus_error,
            "consensus_better": consensus_error < track_error,
            "primary_consensus_dist": _dist(track, consensus),
            "track_step": _dist(track, previous_track) if previous_track is not None else 0.0,
            "consensus_step": _dist(consensus, previous_consensus) if previous_consensus is not None else 0.0,
            "support_count": int(debug.get("support_count", 0) or 0),
            "support_weight": float(debug.get("support_weight", 0.0) or 0.0),
            "avg_dist": float(debug.get("avg_dist", 0.0) or 0.0),
            "accepted": bool(debug.get("accepted", False)),
            "reason": str(debug.get("reason", "")),
            "background_expected": bool(debug.get("background_expected", False)),
            "rank_center": float(record_map.get("rank_center", 0.0) or 0.0),
            "rank_rough": float(record_map.get("rank_rough", 0.0) or 0.0),
            "merge_frames": int(merge_map.get("frames", 0) or 0),
        })
        previous_track = track
        previous_consensus = consensus

    return feature_rows


def summarize_consensus_gate_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    better = [row for row in rows if bool(row.get("consensus_better", False))]
    worse = [row for row in rows if not bool(row.get("consensus_better", False))]
    return {
        "total": len(rows),
        "better": _bucket_summary(better),
        "worse": _bucket_summary(worse),
    }


def consensus_gate_passes(
    row: Mapping[str, object],
    *,
    min_support_weight: float = 3.0,
    max_avg_dist: float = 20.0,
    min_primary_consensus_dist: float = 45.0,
    max_consensus_step: float = 80.0,
    accepted_required: bool = True,
) -> bool:
    if accepted_required and not bool(row.get("accepted", False)):
        return False
    if _float(row.get("support_weight")) < float(min_support_weight):
        return False
    if _float(row.get("avg_dist")) > float(max_avg_dist):
        return False
    if _float(row.get("primary_consensus_dist")) < float(min_primary_consensus_dist):
        return False
    if _float(row.get("consensus_step")) > float(max_consensus_step):
        return False
    return True


def evaluate_gate_rows(
    rows: Sequence[Mapping[str, object]],
    **gate_config: object,
) -> dict[str, object]:
    passed_rows = [
        row
        for row in rows
        if consensus_gate_passes(row, **gate_config)
    ]
    better_rows = [row for row in passed_rows if bool(row.get("consensus_better", False))]
    worse_rows = [row for row in passed_rows if not bool(row.get("consensus_better", False))]
    return {
        "passed": len(passed_rows),
        "better_passed": len(better_rows),
        "worse_passed": len(worse_rows),
        "mean_error_delta": _mean(row.get("error_delta", 0.0) for row in passed_rows),
    }


def gate_sweep_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    configs: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    out = []
    for config in configs or DEFAULT_GATE_CONFIGS:
        clean_config = {
            "min_support_weight": float(config.get("min_support_weight", 3.0)),
            "max_avg_dist": float(config.get("max_avg_dist", 20.0)),
            "min_primary_consensus_dist": float(config.get("min_primary_consensus_dist", 45.0)),
            "max_consensus_step": float(config.get("max_consensus_step", 80.0)),
        }
        result = evaluate_gate_rows(rows, **clean_config)
        out.append({"config": clean_config, **result})
    return out


def markdown_report(name: str, rows: Sequence[Mapping[str, object]]) -> str:
    summary = summarize_consensus_gate_rows(rows)
    sweep = gate_sweep_rows(rows)
    lines = [
        "# consensus rescue gate report",
        "",
        f"- clip: `{name}`.",
        f"- rows: {len(rows)}.",
        f"- better: {summary['better']['count']}.",
        f"- worse: {summary['worse']['count']}.",
        "",
        "## summary",
        "",
        "| bucket | count | delta_mean | support_mean | avg_dist_mean | primary_consensus_dist_mean |",
        "|---|---:|---:|---:|---:|---:|",
        _summary_line("better", summary["better"]),
        _summary_line("worse", summary["worse"]),
        "",
        "## gate sweep",
        "",
        "| min_support | max_avg_dist | min_primary_dist | max_step | passed | better | worse | delta_mean |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in sweep:
        config = item["config"]
        lines.append(
            "| {min_support} | {max_avg} | {min_primary} | {max_step} | {passed} | {better} | {worse} | {delta} |".format(
                min_support=_fmt_float(config["min_support_weight"]),
                max_avg=_fmt_float(config["max_avg_dist"]),
                min_primary=_fmt_float(config["min_primary_consensus_dist"]),
                max_step=_fmt_float(config["max_consensus_step"]),
                passed=int(item["passed"]),
                better=int(item["better_passed"]),
                worse=int(item["worse_passed"]),
                delta=_fmt_float(item["mean_error_delta"]),
            )
        )
    lines.extend([
        "",
        "## best and worst samples",
        "",
    ])
    for row in sorted(rows, key=lambda item: _float(item.get("error_delta")), reverse=True)[:8]:
        lines.append(_sample_line(row))
    if rows:
        lines.append("")
        lines.append("## risky samples")
        lines.append("")
        for row in sorted(rows, key=lambda item: _float(item.get("error_delta")))[:8]:
            lines.append(_sample_line(row))
    return "\n".join(lines) + "\n"


def analyze_clip(
    name: str,
    *,
    root: Path = ROOT,
    live_max_candidates: int = 16,
    include_local_box: bool = True,
    start_row: int | None = None,
    end_row: int | None = None,
    warmup_rows: int = 36,
) -> tuple[list[dict[str, object]], str]:
    from _selector_shadow_gt_replay_score import (
        _load_jsonl,
        _new_runtime,
        backfill_selector_shadow_rows,
        load_red_gt,
    )

    source = root / "_record_debug" / f"{name}.jsonl"
    raw_rows = _load_jsonl(source)
    slice_start = 0
    slice_end = len(raw_rows)
    if start_row is not None:
        slice_start = max(0, int(start_row) - max(0, int(warmup_rows)))
    if end_row is not None:
        slice_end = min(len(raw_rows), int(end_row))
    rows = raw_rows[slice_start:slice_end]
    backfilled = backfill_selector_shadow_rows(
        rows,
        runtime=_new_runtime(),
        clip_id=name,
        window=24,
        min_frames=8,
        shadow_min_frames=1,
        emit_every=1,
        max_candidates=8,
        live_max_candidates=int(live_max_candidates),
        include_local_box=bool(include_local_box),
        merge_context_frames=6,
        merge_min_size=175.0,
        merge_size_ratio=1.30,
        enable_guarded_decal_identity=True,
        guarded_decal_min_background_frames=2,
        guarded_decal_match_distance_px=16.0,
        guarded_decal_shape_pct=6.0,
        guarded_decal_max_step_px=180.0,
        include_live_family=True,
    )
    gt = load_red_gt(name, root=root, min_frame=50)
    feature_rows = consensus_gate_feature_rows(backfilled, gt, frame_offset=slice_start)
    return feature_rows, markdown_report(name, feature_rows)


def _bucket_summary(rows: Sequence[Mapping[str, object]]) -> dict[str, float | int]:
    return {
        "count": len(rows),
        "error_delta_mean": _mean(row.get("error_delta", 0.0) for row in rows),
        "support_weight_mean": _mean(row.get("support_weight", 0.0) for row in rows),
        "avg_dist_mean": _mean(row.get("avg_dist", 0.0) for row in rows),
        "primary_consensus_dist_mean": _mean(row.get("primary_consensus_dist", 0.0) for row in rows),
    }


def _consensus_point(row: Mapping[str, object]) -> Point | None:
    record = row.get("selector_shadow")
    if not isinstance(record, Mapping):
        return None
    if not bool(record.get("available", False)):
        return None
    if not bool(record.get("consensus_rescue_allowed", False)):
        return None
    return _point(record.get("consensus_rescue_point"))


def _consensus_debug(row: Mapping[str, object]) -> Mapping[str, object]:
    live_family = row.get("live_family")
    if not isinstance(live_family, Mapping):
        return {}
    debug = live_family.get("debug")
    if not isinstance(debug, Mapping):
        return {}
    consensus = debug.get("guarded_decal_consensus")
    if not isinstance(consensus, Mapping):
        return {}
    return consensus


def _float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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


def _mean(values: Sequence[object]) -> float:
    numbers = []
    for value in values:
        try:
            numbers.append(float(value))
        except (TypeError, ValueError):
            continue
    if not numbers:
        return 0.0
    return sum(numbers) / float(len(numbers))


def _summary_line(name: str, summary: Mapping[str, object]) -> str:
    return (
        f"| {name} | {int(summary.get('count', 0) or 0)} | "
        f"{_fmt_float(summary.get('error_delta_mean'))} | "
        f"{_fmt_float(summary.get('support_weight_mean'))} | "
        f"{_fmt_float(summary.get('avg_dist_mean'))} | "
        f"{_fmt_float(summary.get('primary_consensus_dist_mean'))} |"
    )


def _sample_line(row: Mapping[str, object]) -> str:
    return (
        f"- frame={int(row.get('frame', 0) or 0)} "
        f"delta={_fmt_float(row.get('error_delta'))} "
        f"track={_fmt_float(row.get('track_error'))} "
        f"consensus={_fmt_float(row.get('consensus_error'))} "
        f"support={_fmt_float(row.get('support_weight'))} "
        f"avg={_fmt_float(row.get('avg_dist'))} "
        f"primary_dist={_fmt_float(row.get('primary_consensus_dist'))} "
        f"step={_fmt_float(row.get('consensus_step'))}."
    )


def _fmt_float(value: object) -> str:
    return f"{_float(value):.1f}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="consensus rescue 신뢰 게이트 분석 리포트를 생성합니다.")
    parser.add_argument("names", nargs="+")
    parser.add_argument("--live-max-candidates", type=int, default=16)
    parser.add_argument("--no-local-box", action="store_true")
    parser.add_argument("--start-row", type=int)
    parser.add_argument("--end-row", type=int)
    parser.add_argument("--warmup-rows", type=int, default=36)
    parser.add_argument("--out", default="03_output/2026-06-27_consensus_rescue_gate_report_v1.md")
    args = parser.parse_args(argv)

    texts = []
    json_rows = {}
    for name in args.names:
        rows, text = analyze_clip(
            name,
            live_max_candidates=args.live_max_candidates,
            include_local_box=not args.no_local_box,
            start_row=args.start_row,
            end_row=args.end_row,
            warmup_rows=args.warmup_rows,
        )
        texts.append(text)
        json_rows[name] = rows
    report = "\n".join(texts)
    print(report)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        out.write_text(report, encoding="utf-8")
    except PermissionError as exc:
        print(f"[write-skip] {exc}")
    print(json.dumps(json_rows, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
