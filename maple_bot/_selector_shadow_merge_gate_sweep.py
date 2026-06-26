# selector shadow 병합 gate 후보를 캐시된 backfill 결과로 비교하는 유틸리티입니다.
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Iterable, Mapping, Sequence

from _selector_shadow_backfill import _load_jsonl, backfill_selector_shadow_rows
from core.vision.transparent_family_selector_runtime import TransparentFamilySelectorRuntime


@dataclass(frozen=True)
class GateSpec:
    name: str
    min_size: float
    size_ratio: float


DEFAULT_GATES = (
    GateSpec("loose", 165.0, 1.20),
    GateSpec("default", 175.0, 1.30),
    GateSpec("strict", 190.0, 1.40),
)


def parse_gate(value: str) -> GateSpec:
    parts = str(value).split(":")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("gate format must be name:min_size:size_ratio")
    name, min_size, size_ratio = parts
    try:
        return GateSpec(str(name), float(min_size), float(size_ratio))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("gate min_size and size_ratio must be numbers") from exc


def record_files(
    path: str | Path,
    *,
    gt_dir: str | Path | None = None,
    max_files: int = 0,
) -> list[Path]:
    source = Path(path)
    if source.is_file():
        files = [source]
    else:
        files = sorted(source.glob("*.jsonl"))
    if gt_dir is not None:
        gt_names = {
            item.name
            for item in Path(gt_dir).iterdir()
            if item.is_dir()
        }
        files = [file for file in files if file.stem in gt_names]
    if int(max_files or 0) > 0:
        files = files[: int(max_files)]
    return files


def sweep_backfilled_rows(
    name: str,
    rows: Sequence[Mapping[str, object]],
    gates: Sequence[GateSpec],
) -> list[dict]:
    return [summarize_gate(name, rows, gate) for gate in gates]


def summarize_gate(
    name: str,
    rows: Sequence[Mapping[str, object]],
    gate: GateSpec,
) -> dict:
    shadow_frames = 0
    bg_split_frames = 0
    rescue_allowed_frames = 0
    first_bg_split_frame = None
    first_rescue_allowed_frame = None
    max_size = 0.0
    max_ratio = 0.0
    bg_split_max_size = 0.0
    bg_split_max_ratio = 0.0

    for index, row in enumerate(rows):
        record = _shadow_record(row)
        if record is None:
            continue
        shadow_frames += 1
        family = str(record.get("family", ""))
        merge_context = _merge_context(record.get("merge_context"))
        max_size = max(max_size, merge_context["max_size"])
        max_ratio = max(max_ratio, merge_context["max_ratio"])

        bg_split = family.lower().startswith("bg_split_viterbi")
        if bg_split:
            bg_split_frames += 1
            bg_split_max_size = max(bg_split_max_size, merge_context["max_size"])
            bg_split_max_ratio = max(bg_split_max_ratio, merge_context["max_ratio"])
            if first_bg_split_frame is None:
                first_bg_split_frame = _frame(row, index)
        if _allowed_for_gate(record, gate):
            rescue_allowed_frames += 1
            if first_rescue_allowed_frame is None:
                first_rescue_allowed_frame = _frame(row, index)

    return {
        "name": str(name),
        "gate": gate.name,
        "gate_min_size": float(gate.min_size),
        "gate_size_ratio": float(gate.size_ratio),
        "frames": len(rows),
        "shadow_frames": shadow_frames,
        "bg_split_frames": bg_split_frames,
        "rescue_allowed_frames": rescue_allowed_frames,
        "first_bg_split_frame": first_bg_split_frame,
        "first_rescue_allowed_frame": first_rescue_allowed_frame,
        "merge_context_max_size": round(float(max_size), 1),
        "merge_context_max_ratio": round(float(max_ratio), 3),
        "bg_split_max_size": round(float(bg_split_max_size), 1),
        "bg_split_max_ratio": round(float(bg_split_max_ratio), 3),
    }


def run_sweep(
    path: str | Path,
    *,
    gates: Sequence[GateSpec] = DEFAULT_GATES,
    gt_dir: str | Path | None = None,
    max_files: int = 0,
    limit: int = 80,
    window: int = 24,
    min_frames: int = 8,
    shadow_min_frames: int | None = 1,
    emit_every: int = 10,
    max_candidates: int = 8,
    live_max_candidates: int = 8,
    merge_context_frames: int = 6,
    include_local_box: bool = False,
) -> list[dict]:
    runtime = TransparentFamilySelectorRuntime()
    summaries: list[dict] = []
    for source in record_files(path, gt_dir=gt_dir, max_files=max_files):
        start = time.perf_counter()
        rows = _load_jsonl(source, limit=limit)
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
            merge_min_size=0.0,
            merge_size_ratio=9999.0,
        )
        elapsed_ms = int((time.perf_counter() - start) * 1000.0)
        for summary in sweep_backfilled_rows(source.name, backfilled, gates):
            summary["elapsed_ms"] = elapsed_ms
            summaries.append(summary)
        print(f"swept {source.name} ms={elapsed_ms}", flush=True)
    return summaries


def write_markdown_report(
    summaries: Iterable[Mapping[str, object]],
    out_path: str | Path,
) -> Path | None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    items = list(summaries)
    lines = [
        "# selector_shadow merge gate sweep",
        "",
        f"- rows: {len(items)}",
        f"- rescue_allowed total: {sum(int(item.get('rescue_allowed_frames', 0) or 0) for item in items)}",
        "",
        "| file | gate | min_size | ratio | shadow | bg_split | allowed | first_bg | first_allowed | bg_max | bg_ratio | merge_max | merge_ratio | ms |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in items:
        lines.append(
            "| {name} | {gate} | {min_size} | {ratio} | {shadow} | {bg} | {allowed} | "
            "{first_bg} | {first_allowed} | {bg_max} | {bg_ratio} | "
            "{merge_max} | {merge_ratio} | {ms} |".format(
                name=item.get("name", ""),
                gate=item.get("gate", ""),
                min_size=item.get("gate_min_size", ""),
                ratio=item.get("gate_size_ratio", ""),
                shadow=item.get("shadow_frames", 0),
                bg=item.get("bg_split_frames", 0),
                allowed=item.get("rescue_allowed_frames", 0),
                first_bg=item.get("first_bg_split_frame") or "-",
                first_allowed=item.get("first_rescue_allowed_frame") or "-",
                bg_max=item.get("bg_split_max_size", 0.0),
                bg_ratio=item.get("bg_split_max_ratio", 0.0),
                merge_max=item.get("merge_context_max_size", 0.0),
                merge_ratio=item.get("merge_context_max_ratio", 0.0),
                ms=item.get("elapsed_ms", 0),
            )
        )
    try:
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except PermissionError:
        return None
    return out


def _shadow_record(row: Mapping[str, object]) -> Mapping[str, object] | None:
    record = row.get("selector_shadow")
    if isinstance(record, Mapping):
        return record
    return None


def _merge_context(value: object) -> dict:
    if not isinstance(value, Mapping):
        return {
            "max_size": 0.0,
            "max_ratio": 0.0,
        }
    return {
        "max_size": float(value.get("max_size", 0.0) or 0.0),
        "max_ratio": float(value.get("max_ratio", 0.0) or 0.0),
    }


def _frame(row: Mapping[str, object], fallback: int) -> int:
    try:
        return int(row.get("i", fallback) or fallback)
    except (TypeError, ValueError):
        return int(fallback)


def _allowed_for_gate(record: Mapping[str, object], gate: GateSpec) -> bool:
    family = str(record.get("family", ""))
    if not family.lower().startswith("bg_split_viterbi"):
        return False
    if record.get("rescue_point") is None:
        return False
    merge_context = _merge_context(record.get("merge_context"))
    return (
        merge_context["max_size"] >= float(gate.min_size)
        or merge_context["max_ratio"] >= float(gate.size_ratio)
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="selector_shadow merge gate 후보를 빠르게 비교합니다.")
    parser.add_argument("path", nargs="?", default="_record_debug")
    parser.add_argument("--gt-dir", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--files", type=int, default=0)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--window", type=int, default=24)
    parser.add_argument("--min-frames", type=int, default=8)
    parser.add_argument("--shadow-min-frames", type=int, default=1)
    parser.add_argument("--emit-every", type=int, default=10)
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--live-max-candidates", type=int, default=8)
    parser.add_argument("--merge-context-frames", type=int, default=6)
    parser.add_argument("--with-local-box", action="store_true")
    parser.add_argument("--gate", action="append", type=parse_gate, default=[])
    args = parser.parse_args(argv)

    gates = args.gate or list(DEFAULT_GATES)
    summaries = run_sweep(
        args.path,
        gates=gates,
        gt_dir=args.gt_dir or None,
        max_files=args.files,
        limit=args.limit,
        window=args.window,
        min_frames=args.min_frames,
        shadow_min_frames=args.shadow_min_frames,
        emit_every=args.emit_every,
        max_candidates=args.max_candidates,
        live_max_candidates=args.live_max_candidates,
        merge_context_frames=args.merge_context_frames,
        include_local_box=args.with_local_box,
    )
    if args.out:
        report = write_markdown_report(summaries, args.out)
        print(f"selector_shadow_merge_gate_sweep rows={len(summaries)} report={report}")
    else:
        for summary in summaries:
            print(
                f"{summary['name']} gate={summary['gate']} "
                f"bg={summary['bg_split_frames']} allowed={summary['rescue_allowed_frames']} "
                f"bg_max={summary['bg_split_max_size']} "
                f"bg_ratio={summary['bg_split_max_ratio']} "
                f"merge_max={summary['merge_context_max_size']} "
                f"merge_ratio={summary['merge_context_max_ratio']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
