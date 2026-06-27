# 여러 record_debug JSONL에 빠른 selector_shadow backfill 요약을 생성하는 유틸리티입니다.
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import time
from typing import Iterable, Mapping, Sequence

GUARDED_DEBUG_NUMERIC_FIELDS = (
    "period",
    "background_frames",
    "expected_frames",
    "background_ratio",
    "max_step",
)


def _load_jsonl(
    path: str | Path,
    *,
    limit: int | None = None,
    use_width_sidecar: bool = True,
) -> list[dict]:
    rows = []
    max_rows = None if limit is None or int(limit) <= 0 else int(limit)
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
                if max_rows is not None and len(rows) >= max_rows:
                    break
    if use_width_sidecar:
        rows = _merge_width_sidecar(rows, _load_width_sidecar(path, limit=limit))
    return rows


def _load_width_sidecar(path: str | Path, *, limit: int | None = None) -> list[list[list[float]]]:
    source = Path(path)
    sidecar = source.with_suffix(".wjsonl")
    if source.suffix.lower() == ".wjsonl" or not sidecar.exists():
        return []
    rows = []
    max_rows = None if limit is None or int(limit) <= 0 else int(limit)
    with sidecar.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                item = []
            rows.append(item if isinstance(item, list) else [])
            if max_rows is not None and len(rows) >= max_rows:
                break
    return rows


def _merge_width_sidecar(rows: list[dict], width_rows: Sequence[Sequence[Sequence[float]]]) -> list[dict]:
    if not width_rows:
        return rows
    merged = []
    for index, row in enumerate(rows):
        copied = dict(row)
        width_candidates = width_rows[index] if index < len(width_rows) else []
        copied["cands"] = _merge_candidate_widths(copied.get("cands", []), width_candidates)
        merged.append(copied)
    return merged


def _merge_candidate_widths(candidates: object, width_candidates: Sequence[Sequence[float]]) -> object:
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        return candidates
    out = []
    for candidate in candidates:
        if not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes)) or len(candidate) < 3:
            out.append(candidate)
            continue
        if len(candidate) >= 5:
            out.append(candidate)
            continue
        width_match = _nearest_width_candidate(candidate, width_candidates)
        if width_match is None:
            out.append(candidate)
            continue
        out.append([
            float(candidate[0]),
            float(candidate[1]),
            float(candidate[2]),
            float(width_match[2]),
            float(width_match[3]),
        ])
    return out


def _nearest_width_candidate(
    candidate: Sequence[float],
    width_candidates: Sequence[Sequence[float]],
    *,
    max_distance: float = 16.0,
) -> Sequence[float] | None:
    best = None
    best_dist = None
    for width_candidate in width_candidates:
        if not isinstance(width_candidate, Sequence) or len(width_candidate) < 4:
            continue
        try:
            dx = float(candidate[0]) - float(width_candidate[0])
            dy = float(candidate[1]) - float(width_candidate[1])
        except (TypeError, ValueError):
            continue
        dist = (dx * dx + dy * dy) ** 0.5
        if best_dist is None or dist < best_dist:
            best = width_candidate
            best_dist = dist
    if best_dist is None or best_dist > float(max_distance):
        return None
    return best


def backfill_selector_shadow_rows(*args, **kwargs):
    from _selector_shadow_backfill import backfill_selector_shadow_rows as backfill

    return backfill(*args, **kwargs)


def _new_runtime():
    from core.vision.transparent_family_selector_runtime import TransparentFamilySelectorRuntime

    return TransparentFamilySelectorRuntime()


def _shadow_record(row: Mapping[str, object]) -> Mapping[str, object] | None:
    record = row.get("selector_shadow")
    if isinstance(record, Mapping):
        return record
    return None


def _frame(row: Mapping[str, object]) -> int:
    try:
        return int(row.get("i", -1) or -1)
    except (TypeError, ValueError):
        return -1


def _is_bg_split(family: str) -> bool:
    name = family.lower()
    return (
        name.startswith("bg_split_viterbi")
        or name.startswith("merge_context")
    )


def _is_guarded_decal(family: str) -> bool:
    return family.lower().startswith("guarded_decal_identity")


def _first_frame(events: Sequence[Mapping[str, object]], *, kind: str) -> int | None:
    for event in events:
        if event.get("kind") == kind:
            return int(event.get("frame", -1) or -1)
    return None


def _first_rescue_allowed_frame(events: Sequence[Mapping[str, object]]) -> int | None:
    for event in events:
        if bool(event.get("rescue_allowed", False)):
            return int(event.get("frame", -1) or -1)
    return None


def _merge_context(value: object) -> dict:
    if not isinstance(value, Mapping):
        return {
            "frames": 0,
            "latest": False,
            "max_size": 0.0,
            "max_ratio": 0.0,
        }
    return {
        "frames": int(value.get("frames", 0) or 0),
        "latest": bool(value.get("latest", False)),
        "max_size": float(value.get("max_size", 0.0) or 0.0),
        "max_ratio": float(value.get("max_ratio", 0.0) or 0.0),
    }


def _guarded_reason(row: Mapping[str, object]) -> str | None:
    guarded = _guarded_debug(row)
    if guarded is None:
        return None
    reason = _guarded_reason_from_debug(guarded)
    return reason or None


def _guarded_debug(row: Mapping[str, object]) -> Mapping[str, object] | None:
    live_family = row.get("live_family")
    if not isinstance(live_family, Mapping):
        return None
    debug = live_family.get("debug")
    if not isinstance(debug, Mapping):
        return None
    guarded = debug.get("guarded_decal_identity")
    if not isinstance(guarded, Mapping):
        return None
    return guarded


def _guarded_reason_from_debug(guarded: Mapping[str, object]) -> str:
    reason = str(guarded.get("reason") or "")
    if not reason and bool(guarded.get("accepted", False)):
        reason = "accepted"
    return reason


def _jsonl_files(path: str | Path, max_files: int | None = None) -> list[Path]:
    source = Path(path)
    if source.is_file():
        return [source]
    files = sorted(source.glob("*.jsonl"))
    if max_files is not None and int(max_files) > 0:
        return files[: int(max_files)]
    return files


def summarize_backfilled_rows(
    name: str,
    rows: Sequence[Mapping[str, object]],
    *,
    elapsed_ms: int = 0,
    max_events: int = 20,
) -> dict:
    families: Counter[str] = Counter()
    guarded_reasons: Counter[str] = Counter()
    guarded_stats: dict[str, dict[str, list[float]]] = {}
    shadow_frames = 0
    bg_split_frames = 0
    guarded_decal_frames = 0
    rescue_allowed_frames = 0
    merge_context_frames = 0
    merge_context_max_size = 0.0
    merge_context_max_ratio = 0.0
    events = []

    for row in rows:
        guarded = _guarded_debug(row)
        reason = _guarded_reason_from_debug(guarded) if guarded is not None else None
        if reason:
            guarded_reasons[reason] += 1
            fields = guarded_stats.setdefault(reason, {})
            for field in GUARDED_DEBUG_NUMERIC_FIELDS:
                value = guarded.get(field)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                fields.setdefault(field, []).append(float(value))

        record = _shadow_record(row)
        if record is None:
            continue

        shadow_frames += 1
        family = str(record.get("family", ""))
        if family:
            families[family] += 1

        rescue_point = record.get("rescue_point")
        rescue_allowed = bool(record.get("rescue_allowed", False)) and rescue_point is not None
        bg_split = _is_bg_split(family)
        guarded_decal = _is_guarded_decal(family)
        merge_context = _merge_context(record.get("merge_context"))
        merge_context_frames = max(merge_context_frames, int(merge_context.get("frames", 0) or 0))
        merge_context_max_size = max(merge_context_max_size, float(merge_context.get("max_size", 0.0) or 0.0))
        merge_context_max_ratio = max(merge_context_max_ratio, float(merge_context.get("max_ratio", 0.0) or 0.0))
        if bg_split:
            bg_split_frames += 1
        if guarded_decal:
            guarded_decal_frames += 1
        if rescue_allowed:
            rescue_allowed_frames += 1
        if bg_split or guarded_decal or rescue_allowed:
            events.append({
                "kind": "guarded_decal" if guarded_decal else ("bg_split" if bg_split else "rescue_allowed"),
                "frame": _frame(row),
                "family": family,
                "point": record.get("point"),
                "rescue_point": rescue_point,
                "rescue_allowed": rescue_allowed,
                "merge_context": merge_context,
            })

    events = events[: max(0, int(max_events))]
    return {
        "name": str(name),
        "frames": len(rows),
        "shadow_frames": shadow_frames,
        "bg_split_frames": bg_split_frames,
        "guarded_decal_frames": guarded_decal_frames,
        "rescue_allowed_frames": rescue_allowed_frames,
        "merge_context_frames": int(merge_context_frames),
        "merge_context_max_size": round(float(merge_context_max_size), 1),
        "merge_context_max_ratio": round(float(merge_context_max_ratio), 3),
        "first_bg_split_frame": _first_frame(events, kind="bg_split"),
        "first_guarded_decal_frame": _first_frame(events, kind="guarded_decal"),
        "first_rescue_allowed_frame": _first_rescue_allowed_frame(events),
        "families": dict(families),
        "guarded_reason_counts": _sorted_counts(guarded_reasons),
        "guarded_debug_stats": _guarded_debug_stats(guarded_reasons, guarded_stats),
        "events": events,
        "elapsed_ms": int(elapsed_ms),
    }


def analyze_record_file_fast(
    path: str | Path,
    *,
    runtime=None,
    limit: int = 80,
    window: int = 24,
    min_frames: int = 8,
    shadow_min_frames: int | None = 1,
    emit_every: int = 10,
    max_candidates: int = 8,
    live_max_candidates: int = 8,
    include_local_box: bool = False,
    merge_context_frames: int = 6,
    merge_min_size: float = 175.0,
    merge_size_ratio: float = 1.30,
    enable_guarded_decal_identity: bool = False,
) -> dict:
    source = Path(path)
    rows = _load_jsonl(source, limit=limit)
    start = time.perf_counter()
    backfilled = backfill_selector_shadow_rows(
        rows,
        runtime=runtime,
        clip_id=source.stem,
        window=window,
        min_frames=min_frames,
        shadow_min_frames=shadow_min_frames,
        emit_every=emit_every,
        max_candidates=max_candidates,
        live_max_candidates=live_max_candidates,
        include_local_box=include_local_box,
        merge_context_frames=merge_context_frames,
        merge_min_size=merge_min_size,
        merge_size_ratio=merge_size_ratio,
        enable_guarded_decal_identity=enable_guarded_decal_identity,
        include_live_family=enable_guarded_decal_identity,
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000.0)
    return summarize_backfilled_rows(source.name, backfilled, elapsed_ms=elapsed_ms)


def analyze_record_path_fast(
    path: str | Path,
    *,
    runtime=None,
    max_files: int = 0,
    **kwargs,
) -> list[dict]:
    shared_runtime = runtime or _new_runtime()
    summaries = []
    for source in _jsonl_files(path, max_files=max_files):
        summaries.append(analyze_record_file_fast(
            source,
            runtime=shared_runtime,
            **kwargs,
        ))
    return summaries


def _top_family(summary: Mapping[str, object]) -> str:
    families = summary.get("families", {})
    if not isinstance(families, Mapping) or not families:
        return "-"
    return str(max(families.items(), key=lambda pair: int(pair[1]))[0])


def _sorted_counts(counts: Mapping[str, int]) -> dict[str, int]:
    return {
        str(key): int(value)
        for key, value in sorted(
            counts.items(),
            key=lambda item: (-int(item[1]), str(item[0])),
        )
    }


def _fmt_counts(value: object) -> str:
    if not isinstance(value, Mapping) or not value:
        return "-"
    counts = _sorted_counts({str(key): int(count) for key, count in value.items()})
    return ", ".join(f"{key}={count}" for key, count in counts.items())


def _guarded_debug_stats(
    counts: Mapping[str, int],
    buckets: Mapping[str, Mapping[str, Sequence[float]]],
) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for reason, count in _sorted_counts(counts).items():
        item: dict[str, object] = {"count": int(count)}
        for field in GUARDED_DEBUG_NUMERIC_FIELDS:
            values = list(buckets.get(reason, {}).get(field, []))
            if values:
                item[field] = _number_summary(values)
        out[reason] = item
    return out


def _number_summary(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "mean": 0.0, "max": 0.0}
    return {
        "min": round(float(min(values)), 3),
        "mean": round(float(sum(values) / len(values)), 3),
        "max": round(float(max(values)), 3),
    }


def _fmt_number(value: object) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "-"


def _fmt_guarded_debug_stats(value: object) -> str:
    if not isinstance(value, Mapping) or not value:
        return "-"
    parts = []
    for reason, stats in value.items():
        if not isinstance(stats, Mapping):
            continue
        fields = [f"{reason} count={int(stats.get('count', 0) or 0)}"]
        for field in GUARDED_DEBUG_NUMERIC_FIELDS:
            summary = stats.get(field)
            if not isinstance(summary, Mapping):
                continue
            fields.append(
                f"{field}="
                f"{_fmt_number(summary.get('min'))}/"
                f"{_fmt_number(summary.get('mean'))}/"
                f"{_fmt_number(summary.get('max'))}"
            )
        parts.append(" ".join(fields))
    return "; ".join(parts) if parts else "-"


def write_markdown_report(
    summaries: Iterable[Mapping[str, object]],
    out_path: str | Path,
) -> Path | None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    items = list(summaries)
    lines = [
        "# selector_shadow 빠른 backfill 배치 리포트",
        "",
        f"- 분석 파일: {len(items)}개",
        f"- shadow 프레임: {sum(int(item.get('shadow_frames', 0) or 0) for item in items)}개",
        f"- bg_split 프레임: {sum(int(item.get('bg_split_frames', 0) or 0) for item in items)}개",
        f"- guarded decal 프레임: {sum(int(item.get('guarded_decal_frames', 0) or 0) for item in items)}개",
        f"- rescue_allowed 프레임: {sum(int(item.get('rescue_allowed_frames', 0) or 0) for item in items)}개",
        "",
        "| 파일 | 프레임 | shadow | bg_split | guarded | allowed | first_bg | first_guarded | first_allowed | merge_frames | merge_max | merge_ratio | guard_reasons | guard_stats | ms | 주요 family |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---|",
    ]
    for item in items:
        lines.append(
            "| {name} | {frames} | {shadow} | {bg_split} | {guarded} | {allowed} | "
            "{first_bg} | {first_guarded} | {first_allowed} | {merge_frames} | {merge_max} | {merge_ratio} | {guard_reasons} | {guard_stats} | "
            "{elapsed} | {family} |".format(
                name=item.get("name", ""),
                frames=item.get("frames", 0),
                shadow=item.get("shadow_frames", 0),
                bg_split=item.get("bg_split_frames", 0),
                guarded=item.get("guarded_decal_frames", 0),
                allowed=item.get("rescue_allowed_frames", 0),
                first_bg=item.get("first_bg_split_frame") or "-",
                first_guarded=item.get("first_guarded_decal_frame") or "-",
                first_allowed=item.get("first_rescue_allowed_frame") or "-",
                merge_frames=item.get("merge_context_frames", 0),
                merge_max=item.get("merge_context_max_size", 0.0),
                merge_ratio=item.get("merge_context_max_ratio", 0.0),
                guard_reasons=_fmt_counts(item.get("guarded_reason_counts", {})),
                guard_stats=_fmt_guarded_debug_stats(item.get("guarded_debug_stats", {})),
                elapsed=item.get("elapsed_ms", 0),
                family=_top_family(item),
            )
        )
    lines.append("")
    lines.append("## 이벤트")
    for item in items:
        events = item.get("events", []) or []
        if not events:
            continue
        lines.append("")
        lines.append(f"### {item.get('name', '')}")
        for event in events:
            merge_context = _merge_context(event.get("merge_context"))
            lines.append(
                f"- f{event.get('frame')}: {event.get('family')} "
                f"rescue={event.get('rescue_allowed')} "
                f"merge_frames={merge_context.get('frames')} "
                f"merge_max={merge_context.get('max_size')} "
                f"merge_ratio={merge_context.get('max_ratio')}"
            )

    try:
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except PermissionError:
        return None
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="record_debug JSONL 여러 개를 빠르게 backfill 요약합니다.")
    parser.add_argument("path", nargs="?", default="_record_debug")
    parser.add_argument("--out", default="03_output/2026-06-26_selector_shadow_batch_report_v1.md")
    parser.add_argument("--files", type=int, default=5)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--window", type=int, default=24)
    parser.add_argument("--min-frames", type=int, default=8)
    parser.add_argument("--shadow-min-frames", type=int, default=1)
    parser.add_argument("--emit-every", type=int, default=10)
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--live-max-candidates", type=int, default=8)
    parser.add_argument("--merge-context-frames", type=int, default=6)
    parser.add_argument("--merge-min-size", type=float, default=175.0)
    parser.add_argument("--merge-size-ratio", type=float, default=1.30)
    parser.add_argument("--guarded-decal-identity", action="store_true")
    parser.add_argument("--with-local-box", action="store_true")
    args = parser.parse_args(argv)

    summaries = analyze_record_path_fast(
        args.path,
        max_files=args.files,
        limit=args.limit,
        window=args.window,
        min_frames=args.min_frames,
        shadow_min_frames=args.shadow_min_frames,
        emit_every=args.emit_every,
        max_candidates=args.max_candidates,
        live_max_candidates=args.live_max_candidates,
        include_local_box=args.with_local_box,
        merge_context_frames=args.merge_context_frames,
        merge_min_size=args.merge_min_size,
        merge_size_ratio=args.merge_size_ratio,
        enable_guarded_decal_identity=args.guarded_decal_identity,
    )
    report = write_markdown_report(summaries, args.out)
    print(f"selector_shadow_batch files={len(summaries)} report={report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
