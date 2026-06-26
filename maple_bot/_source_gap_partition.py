# 투명 퍼즐 실패를 후보 선택 문제와 후보 복원 문제로 분리하는 진단 도구입니다.
from __future__ import annotations

import argparse
import csv
import io
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from _live_source_upper_score import (
    augment_with_local_box,
    build_record_source_paths,
    local_box_candidate_sets_from_rows,
    source_group_for_family,
)
from _selector_shadow_backfill import _load_jsonl
from _selector_shadow_gt_replay_score import load_red_gt


ROOT = Path(__file__).resolve().parent
Point = tuple[float, float]
Candidate = tuple[float, float, float, float, float]
DEFAULT_SOURCE_REPORT = ROOT / "03_output" / "2026-06-26_phase_catalog_live_source_upper_v1.md"


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _empty_score() -> dict[str, object]:
    return {
        "n": 0,
        "coverage": 0.0,
        "mean": float("inf"),
        "max": float("inf"),
        "success": False,
        "worst": [],
    }


def _score_errors(
    errors: Sequence[tuple[int, float]],
    total_frames: int,
    *,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
) -> dict[str, object]:
    if not errors:
        return _empty_score()
    values = [float(error) for _frame, error in errors]
    coverage = float(len(values)) / max(1, int(total_frames))
    worst = sorted(
        (
            {"frame": int(frame), "error": round(float(error), 1)}
            for frame, error in errors
        ),
        key=lambda item: item["error"],
        reverse=True,
    )
    mean = float(sum(values) / len(values))
    return {
        "n": len(values),
        "coverage": coverage,
        "mean": mean,
        "max": float(max(values)),
        "success": mean <= float(success_px) and coverage >= float(min_coverage),
        "worst": worst[:5],
    }


def score_point_path(
    path: Mapping[int, Point],
    gt_by_frame: Mapping[int, Point],
    frames: Sequence[int],
    *,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
) -> dict[str, object]:
    errors = []
    for frame in frames:
        point = path.get(int(frame))
        gt = gt_by_frame.get(int(frame))
        if point is None or gt is None:
            continue
        errors.append((int(frame), _dist(point, gt)))
    return _score_errors(
        errors,
        len(frames),
        success_px=success_px,
        min_coverage=min_coverage,
    )


def _point_to_box_distance(point: Point, candidate: Candidate) -> float:
    cx, cy, width, height, _score = candidate
    half_w = max(0.0, float(width) / 2.0)
    half_h = max(0.0, float(height) / 2.0)
    left = float(cx) - half_w
    right = float(cx) + half_w
    top = float(cy) - half_h
    bottom = float(cy) + half_h
    dx = max(left - float(point[0]), 0.0, float(point[0]) - right)
    dy = max(top - float(point[1]), 0.0, float(point[1]) - bottom)
    return math.hypot(dx, dy)


def raw_candidate_oracles(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    frames: Sequence[int],
    *,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
) -> dict[str, dict[str, object]]:
    candidate_sets = local_box_candidate_sets_from_rows(rows)
    center_errors = []
    box_errors = []
    for frame in frames:
        gt = gt_by_frame.get(int(frame))
        candidates = candidate_sets.get(int(frame), [])
        if gt is None or not candidates:
            continue
        center_error = min(_dist((candidate[0], candidate[1]), gt) for candidate in candidates)
        box_error = min(_point_to_box_distance(gt, candidate) for candidate in candidates)
        center_errors.append((int(frame), center_error))
        box_errors.append((int(frame), box_error))
    return {
        "raw_center": _score_errors(
            center_errors,
            len(frames),
            success_px=success_px,
            min_coverage=min_coverage,
        ),
        "raw_box": _score_errors(
            box_errors,
            len(frames),
            success_px=success_px,
            min_coverage=min_coverage,
        ),
    }


def _score_rank(score: Mapping[str, object]) -> tuple[bool, float, float]:
    return (
        bool(score.get("success", False)),
        float(score.get("coverage", 0.0) or 0.0),
        -float(score.get("mean", float("inf"))),
    )


def current_source_upper(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    frames: Sequence[int],
    *,
    include_live: bool = True,
    include_local_box: bool = True,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
) -> dict[str, object]:
    paths = build_record_source_paths(rows, include_live=include_live)
    if include_local_box:
        candidate_sets = local_box_candidate_sets_from_rows(rows)
        paths = augment_with_local_box(paths, candidate_sets, range(len(rows)))

    by_source: dict[str, dict[str, object]] = {}
    best_score = _empty_score()
    best_family = ""
    best_source = ""
    for family, path in paths.items():
        score = score_point_path(
            path,
            gt_by_frame,
            frames,
            success_px=success_px,
            min_coverage=min_coverage,
        )
        if not score["n"]:
            continue
        group = source_group_for_family(str(family))
        row = {
            **score,
            "family": str(family),
            "source": group,
        }
        if group not in by_source or _score_rank(row) > _score_rank(by_source[group]):
            by_source[group] = row
        if _score_rank(row) > _score_rank(best_score):
            best_score = score
            best_family = str(family)
            best_source = group

    return {
        "best": {
            **best_score,
            "family": best_family,
            "source": best_source,
        },
        "by_source": by_source,
        "family_count": len(paths),
    }


def _parse_score_cell(cell: str) -> tuple[float | None, bool]:
    value = str(cell).strip()
    if not value or value == "-":
        return None, False
    success = "OK" in value
    number = value.split()[0].replace("px", "")
    try:
        return float(number), success
    except ValueError:
        return None, False


def parse_source_upper_markdown(text: str) -> dict[str, dict[str, object]]:
    lines = [line.strip() for line in str(text).splitlines()]
    header: list[str] | None = None
    parsed: dict[str, dict[str, object]] = {}
    for line in lines:
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        if cells[0] == "clip":
            header = cells
            continue
        if header is None or cells[0].startswith("---"):
            continue
        if cells[0].startswith("`") and cells[0].endswith("`"):
            name = cells[0].strip("`")
        else:
            continue

        best: dict[str, object] | None = None
        for source, cell in zip(header[2:], cells[2:]):
            mean, success = _parse_score_cell(cell)
            if mean is None:
                continue
            row = {
                "n": int(cells[1]) if cells[1].isdigit() else 0,
                "coverage": 1.0,
                "mean": float(mean),
                "max": float("nan"),
                "success": bool(success),
                "worst": [],
                "family": str(source),
                "source": str(source),
                "cached": True,
            }
            if best is None or _score_rank(row) > _score_rank(best):
                best = row
        if best is not None:
            parsed[name] = best
    return parsed


def classify_clip(
    source_score: Mapping[str, object],
    raw_center_score: Mapping[str, object],
    raw_box_score: Mapping[str, object],
) -> str:
    if bool(source_score.get("success", False)):
        return "source_upper_solved"
    if bool(raw_center_score.get("success", False)):
        return "raw_center_family_missing"
    if bool(raw_box_score.get("success", False)):
        return "offset_or_merge_center_reconstruction"
    return "detection_gap_or_visual_reconstruction"


def score_clip(
    name: str,
    *,
    root: Path = ROOT,
    source_cache: Mapping[str, Mapping[str, object]] | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
) -> dict[str, object]:
    rows = _load_jsonl(root / "_record_debug" / f"{name}.jsonl")
    gt = load_red_gt(name, root=root)
    frames = [frame for frame in sorted(gt) if frame < len(rows)]
    if source_cache is not None and name in source_cache:
        source = {
            "best": dict(source_cache[name]),
            "by_source": {},
            "family_count": 0,
            "mode": "cached_source_report",
        }
    else:
        source = current_source_upper(
            rows,
            gt,
            frames,
            success_px=success_px,
            min_coverage=min_coverage,
        )
        source["mode"] = "recomputed_source_upper"
    raw = raw_candidate_oracles(
        rows,
        gt,
        frames,
        success_px=success_px,
        min_coverage=min_coverage,
    )
    bucket = classify_clip(
        source["best"],
        raw["raw_center"],
        raw["raw_box"],
    )
    return {
        "name": name,
        "gt_frames": len(frames),
        "bucket": bucket,
        "source_best": source["best"],
        "source_by_group": source["by_source"],
        "family_count": source["family_count"],
        "source_mode": source.get("mode", ""),
        "raw_center": raw["raw_center"],
        "raw_box": raw["raw_box"],
    }


def score_all(
    *,
    root: Path = ROOT,
    names: Sequence[str] | None = None,
    source_cache: Mapping[str, Mapping[str, object]] | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
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
            source_cache=source_cache,
            success_px=success_px,
            min_coverage=min_coverage,
        )
        for name in names
    ]


def _fmt_score(score: Mapping[str, object]) -> str:
    if not score or not score.get("n"):
        return "-"
    suffix = " OK" if score.get("success") else ""
    return (
        f"{float(score['mean']):.1f}px/"
        f"{float(score.get('coverage', 0.0)):.0%}{suffix}"
    )


def csv_text(rows: Sequence[Mapping[str, object]]) -> str:
    buf = io.StringIO()
    fields = [
        "name",
        "bucket",
        "gt_frames",
        "source_family",
        "source_mean",
        "source_coverage",
        "source_success",
        "raw_center_mean",
        "raw_center_coverage",
        "raw_center_success",
        "raw_box_mean",
        "raw_box_coverage",
        "raw_box_success",
        "source_mode",
    ]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        source = row["source_best"]
        center = row["raw_center"]
        box = row["raw_box"]
        writer.writerow({
            "name": row["name"],
            "bucket": row["bucket"],
            "gt_frames": row["gt_frames"],
            "source_family": source.get("family", ""),
            "source_mean": source.get("mean", ""),
            "source_coverage": source.get("coverage", ""),
            "source_success": source.get("success", False),
            "raw_center_mean": center.get("mean", ""),
            "raw_center_coverage": center.get("coverage", ""),
            "raw_center_success": center.get("success", False),
            "raw_box_mean": box.get("mean", ""),
            "raw_box_coverage": box.get("coverage", ""),
            "raw_box_success": box.get("success", False),
            "source_mode": row.get("source_mode", ""),
        })
    return buf.getvalue()


def markdown_report(rows: Sequence[Mapping[str, object]]) -> str:
    buckets = {}
    for row in rows:
        buckets.setdefault(str(row["bucket"]), []).append(str(row["name"]))

    lines = [
        "# Source Gap Partition 결과",
        "",
        "현재 live source 상한, raw 후보 중심 oracle, raw 후보 박스 oracle을 같은 GT 프레임 기준으로 비교했다.",
        "",
        "## 요약",
        "",
    ]
    for bucket in sorted(buckets):
        names = buckets[bucket]
        lines.append(f"- `{bucket}`: {len(names)}/{len(rows)}. {', '.join(names)}.")

    source_solved = sum(1 for row in rows if row["source_best"].get("success"))
    center_solved = sum(1 for row in rows if row["raw_center"].get("success"))
    box_solved = sum(1 for row in rows if row["raw_box"].get("success"))
    lines.extend([
        "",
        "## 상한 점수",
        "",
        f"- 현재 source 상한 성공: {source_solved}/{len(rows)}.",
        f"- raw 후보 중심 oracle 성공: {center_solved}/{len(rows)}.",
        f"- raw 후보 박스 oracle 성공: {box_solved}/{len(rows)}.",
        "",
        "| clip | bucket | GT | source best | raw center | raw box |",
        "|---|---|---:|---|---|---|",
    ])
    for row in rows:
        source = row["source_best"]
        family = source.get("family", "") or "-"
        source_text = f"{family} {_fmt_score(source)}"
        lines.append(
            f"| `{row['name']}` | `{row['bucket']}` | {row['gt_frames']} | "
            f"{source_text} | {_fmt_score(row['raw_center'])} | {_fmt_score(row['raw_box'])} |"
        )

    lines.extend([
        "",
        "## 해석",
        "",
        "- `source_upper_solved`는 현재 family 후보 안에 이미 정답 경로가 있다는 뜻이다. 실제 live가 틀리면 최종 selector 문제다.",
        "- `raw_center_family_missing`은 YOLO 후보 중심만으로도 풀 수 있는데 현재 family가 그 경로를 만들지 못한다는 뜻이다.",
        "- `offset_or_merge_center_reconstruction`은 후보 박스 안에는 정답이 있지만 중심이 틀어진 경우다. 병합 중심 복원이나 박스 내부 오프셋 추정이 필요하다.",
        "- `detection_gap_or_visual_reconstruction`은 현재 후보/박스만으로 부족하다. 시각 복원, 재검출, 또는 더 긴 비검출 상태 모델이 필요하다.",
    ])
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="투명 퍼즐 실패 원인을 source, raw center, raw box 기준으로 나눕니다.")
    parser.add_argument("names", nargs="*")
    parser.add_argument("--out", default="03_output/2026-06-26_source_gap_partition_v1.md")
    parser.add_argument("--csv-out", default="03_output/2026-06-26_source_gap_partition_v1.csv")
    parser.add_argument("--source-report", default=str(DEFAULT_SOURCE_REPORT))
    parser.add_argument("--recompute-source", action="store_true")
    parser.add_argument("--success-px", type=float, default=40.0)
    parser.add_argument("--min-coverage", type=float, default=0.9)
    args = parser.parse_args(argv)

    source_cache = None
    source_report = Path(args.source_report)
    if not args.recompute_source and source_report.exists():
        source_cache = parse_source_upper_markdown(source_report.read_text(encoding="utf-8"))

    rows = score_all(
        names=args.names or None,
        source_cache=source_cache,
        success_px=args.success_px,
        min_coverage=args.min_coverage,
    )
    text = markdown_report(rows)
    csv_data = csv_text(rows)
    print(text)
    print("=== JSON ===")
    print(json.dumps(rows, ensure_ascii=False))

    out = ROOT / args.out
    csv_out = ROOT / args.csv_out
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        csv_out.write_text(csv_data, encoding="utf-8", newline="")
    except PermissionError as exc:
        print(f"[write-skip] {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
