# 투명도형 퍼즐 16GT를 JSONL 기록만으로 빠르게 채점한다.
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path
from statistics import mean
from typing import Mapping, Sequence

from _selector_shadow_gt_replay_score import load_red_gt


ROOT = Path(__file__).resolve().parent
Point = tuple[float, float]
METRICS = ("track", "engine", "raw_center_oracle", "raw_box_oracle")


def _point(value: object) -> Point | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _candidate(value: object, *, default_size: float = 24.0) -> tuple[float, float, float, float, float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if len(value) < 2:
        return None
    try:
        cx = float(value[0])
        cy = float(value[1])
        score = float(value[2]) if len(value) >= 3 else 0.0
        width = float(value[3]) if len(value) >= 4 else float(default_size)
        height = float(value[4]) if len(value) >= 5 else float(default_size)
    except (TypeError, ValueError):
        return None
    return (cx, cy, score, width, height)


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def load_jsonl_rows(path: str | Path) -> list[dict]:
    rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def gt_clip_names(*, root: Path = ROOT) -> list[str]:
    return [
        path.name
        for path in sorted((root / "_gt_frames").iterdir())
        if path.is_dir()
    ]


def track_path_from_rows(rows: Sequence[Mapping[str, object]], *, source: str = "track") -> dict[int, Point]:
    path: dict[int, Point] = {}
    for frame, row in enumerate(rows):
        if source == "engine":
            engine = row.get("engine")
            value = engine.get("track") if isinstance(engine, Mapping) else None
        else:
            value = row.get(source)
        point = _point(value)
        if point is not None:
            path[int(frame)] = point
    return path


def raw_center_oracle_path(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    *,
    default_size: float = 24.0,
) -> dict[int, Point]:
    path: dict[int, Point] = {}
    for frame, gt in gt_by_frame.items():
        if frame >= len(rows):
            continue
        candidates = [
            candidate
            for value in rows[frame].get("cands", [])
            for candidate in [_candidate(value, default_size=default_size)]
            if candidate is not None
        ]
        if not candidates:
            continue
        cx, cy, _score, _width, _height = min(
            candidates,
            key=lambda candidate: _dist((candidate[0], candidate[1]), gt),
        )
        path[int(frame)] = (cx, cy)
    return path


def raw_box_oracle_path(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    *,
    default_size: float = 24.0,
) -> dict[int, Point]:
    path: dict[int, Point] = {}
    for frame, gt in gt_by_frame.items():
        if frame >= len(rows):
            continue
        candidates = [
            candidate
            for value in rows[frame].get("cands", [])
            for candidate in [_candidate(value, default_size=default_size)]
            if candidate is not None
        ]
        if not candidates:
            continue
        points = [_closest_point_in_box(gt, candidate) for candidate in candidates]
        path[int(frame)] = min(points, key=lambda point: _dist(point, gt))
    return path


def _closest_point_in_box(gt: Point, candidate: tuple[float, float, float, float, float]) -> Point:
    cx, cy, _score, width, height = candidate
    half_w = max(0.0, float(width) / 2.0)
    half_h = max(0.0, float(height) / 2.0)
    x = min(max(float(gt[0]), cx - half_w), cx + half_w)
    y = min(max(float(gt[1]), cy - half_h), cy + half_h)
    return (x, y)


def score_path(
    path: Mapping[int, Point],
    gt_by_frame: Mapping[int, Point],
    *,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
) -> dict[str, object]:
    errors = []
    for frame, gt in gt_by_frame.items():
        point = path.get(int(frame))
        if point is None:
            continue
        errors.append(_dist(point, gt))
    total = len(gt_by_frame)
    coverage = float(len(errors)) / float(total) if total else 0.0
    if not errors:
        return {
            "n": 0,
            "coverage": coverage,
            "mean": float("inf"),
            "max": float("inf"),
            "success": False,
        }
    mean_error = float(sum(errors) / len(errors))
    return {
        "n": len(errors),
        "coverage": coverage,
        "mean": mean_error,
        "max": float(max(errors)),
        "success": mean_error <= float(success_px) and coverage >= float(min_coverage),
    }


def score_clip(
    name: str,
    *,
    root: Path = ROOT,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    min_gt_frame: int = 50,
    default_candidate_size: float = 24.0,
) -> dict[str, object]:
    rows = load_jsonl_rows(root / "_record_debug" / f"{name}.jsonl")
    gt = load_red_gt(name, root=root, min_frame=min_gt_frame)
    paths = {
        "track": track_path_from_rows(rows, source="track"),
        "engine": track_path_from_rows(rows, source="engine"),
        "raw_center_oracle": raw_center_oracle_path(rows, gt, default_size=default_candidate_size),
        "raw_box_oracle": raw_box_oracle_path(rows, gt, default_size=default_candidate_size),
    }
    result: dict[str, object] = {
        "name": name,
        "frames": len(rows),
        "gt_frames": len(gt),
    }
    for metric, path in paths.items():
        result[metric] = score_path(
            path,
            gt,
            success_px=success_px,
            min_coverage=min_coverage,
        )
    return result


def score_all(
    *,
    root: Path = ROOT,
    names: Sequence[str] | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    min_gt_frame: int = 50,
    default_candidate_size: float = 24.0,
) -> list[dict[str, object]]:
    return [
        score_clip(
            str(name),
            root=root,
            success_px=success_px,
            min_coverage=min_coverage,
            min_gt_frame=min_gt_frame,
            default_candidate_size=default_candidate_size,
        )
        for name in (list(names) if names is not None else gt_clip_names(root=root))
    ]


def summarize_results(results: Sequence[Mapping[str, object]], *, metrics: Sequence[str] = METRICS) -> dict[str, int]:
    summary: dict[str, int] = {}
    for metric in metrics:
        summary[str(metric)] = sum(
            1
            for result in results
            if isinstance(result.get(metric), Mapping) and bool(result[metric].get("success"))
        )
    return summary


def markdown_report(results: Sequence[Mapping[str, object]], *, elapsed_s: float | None = None) -> str:
    lines = [
        "# 경량 16GT 채점 결과",
        "",
        "JSONL 기록만 사용해 `track`, `engine`, raw 후보 oracle을 빠르게 채점했다.",
        "",
    ]
    if elapsed_s is not None:
        lines.append(f"- elapsed: {elapsed_s:.2f}s.")
        lines.append("")
    lines.extend([
        "| clip | GT | track | engine | raw center oracle | raw box oracle |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for result in results:
        lines.append(
            "| `{name}` | {gt} | {track} | {engine} | {raw_center} | {raw_box} |".format(
                name=result.get("name", ""),
                gt=int(result.get("gt_frames", 0) or 0),
                track=_fmt_score(result.get("track")),
                engine=_fmt_score(result.get("engine")),
                raw_center=_fmt_score(result.get("raw_center_oracle")),
                raw_box=_fmt_score(result.get("raw_box_oracle")),
            )
        )
    summary = summarize_results(results)
    lines.extend(["", "## 요약", ""])
    for metric in METRICS:
        means = [
            float(result[metric]["mean"])
            for result in results
            if isinstance(result.get(metric), Mapping) and math.isfinite(float(result[metric]["mean"]))
        ]
        avg = mean(means) if means else float("nan")
        lines.append(f"- `{metric}`: {summary[metric]}/{len(results)}, mean {avg:.1f}px.")
    return "\n".join(lines) + "\n"


def _fmt_score(score: object) -> str:
    if not isinstance(score, Mapping) or not score.get("n"):
        return "-"
    suffix = " OK" if score.get("success") else ""
    return f"{float(score['mean']):.1f}{suffix}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="16GT를 JSONL 기록 기반으로 빠르게 채점합니다.")
    parser.add_argument("names", nargs="*")
    parser.add_argument("--out", default="03_output/2026-06-27_fast_gt_score_v1.md")
    parser.add_argument("--success-px", type=float, default=40.0)
    parser.add_argument("--min-coverage", type=float, default=0.9)
    parser.add_argument("--min-gt-frame", type=int, default=50)
    parser.add_argument("--candidate-default-size", type=float, default=24.0)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    results = score_all(
        names=args.names or None,
        success_px=args.success_px,
        min_coverage=args.min_coverage,
        min_gt_frame=args.min_gt_frame,
        default_candidate_size=args.candidate_default_size,
    )
    elapsed_s = time.perf_counter() - started
    text = markdown_report(results, elapsed_s=elapsed_s)
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
