# 투명도형 퍼즐 시간축 selector 실패 원인을 clip 단위로 분류한다.
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from _background_identity_signal import load_expected_background_with_ids
from _fast_gt_score import (
    ROOT,
    gt_clip_names,
    load_jsonl_rows,
    raw_box_oracle_path,
    raw_center_oracle_path,
    score_path,
)
from _selector_shadow_gt_replay_score import load_red_gt
from _temporal_identity_selector import temporal_identity_path_from_rows


Point = tuple[float, float]


def first_bad_frame(
    path: Mapping[int, Point],
    gt_by_frame: Mapping[int, Point],
    *,
    threshold: float = 40.0,
) -> int | None:
    for frame in sorted(int(frame) for frame in gt_by_frame):
        point = path.get(frame)
        if point is None:
            return frame
        gt = gt_by_frame[frame]
        if math.hypot(float(point[0]) - float(gt[0]), float(point[1]) - float(gt[1])) > float(threshold):
            return frame
    return None


def classify_failure(
    temporal: Mapping[str, object],
    raw_center: Mapping[str, object],
    raw_box: Mapping[str, object],
) -> str:
    if bool(temporal.get("success")):
        return "success"
    if bool(raw_center.get("success")):
        return "candidate_selection"
    if bool(raw_box.get("success")):
        return "box_internal_reconstruction"
    return "candidate_source_gap"


def failure_rows(
    *,
    root: Path = ROOT,
    names: Sequence[str] | None = None,
    success_px: float = 40.0,
    min_gt_frame: int = 50,
    default_candidate_size: float = 24.0,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in (list(names) if names is not None else gt_clip_names(root=root)):
        json_rows = load_jsonl_rows(root / "_record_debug" / f"{name}.jsonl")
        gt = load_red_gt(str(name), root=root, min_frame=min_gt_frame)
        expected_background, _meta = load_expected_background_with_ids(
            str(name),
            range(max(0, int(min_gt_frame)), len(json_rows)),
        )
        temporal_path = temporal_identity_path_from_rows(
            json_rows,
            default_size=default_candidate_size,
            expected_background_by_frame=expected_background,
        )
        raw_center_path = raw_center_oracle_path(json_rows, gt, default_size=default_candidate_size)
        raw_box_path = raw_box_oracle_path(json_rows, gt, default_size=default_candidate_size)
        temporal_score = score_path(temporal_path, gt, success_px=success_px)
        raw_center_score = score_path(raw_center_path, gt, success_px=success_px)
        raw_box_score = score_path(raw_box_path, gt, success_px=success_px)
        reason = classify_failure(temporal_score, raw_center_score, raw_box_score)
        rows.append(
            {
                "name": str(name),
                "reason": reason,
                "first_bad_frame": first_bad_frame(temporal_path, gt, threshold=success_px),
                "temporal_mean": temporal_score["mean"],
                "raw_center_mean": raw_center_score["mean"],
                "raw_box_mean": raw_box_score["mean"],
                "temporal_success": temporal_score["success"],
                "raw_center_success": raw_center_score["success"],
                "raw_box_success": raw_box_score["success"],
            }
        )
    return rows


def markdown_report(rows: Sequence[Mapping[str, object]]) -> str:
    lines = [
        "# Task48 temporal identity 실패 분류",
        "",
        "| clip | reason | first bad frame | temporal | raw center | raw box |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| `{name}` | {reason} | {bad} | {temporal} | {raw_center} | {raw_box} |".format(
                name=row.get("name", ""),
                reason=row.get("reason", ""),
                bad="-" if row.get("first_bad_frame") is None else row.get("first_bad_frame"),
                temporal=_fmt_mean(row.get("temporal_mean"), bool(row.get("temporal_success"))),
                raw_center=_fmt_mean(row.get("raw_center_mean"), bool(row.get("raw_center_success"))),
                raw_box=_fmt_mean(row.get("raw_box_mean"), bool(row.get("raw_box_success"))),
            )
        )
    counts: dict[str, int] = {}
    for row in rows:
        reason = str(row.get("reason", "unknown"))
        counts[reason] = counts.get(reason, 0) + 1
    lines.extend(["", "## 요약", ""])
    for reason, count in sorted(counts.items()):
        lines.append(f"- `{reason}`: {count}.")
    return "\n".join(lines) + "\n"


def _fmt_mean(value: object, success: bool) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(number):
        return "-"
    suffix = " OK" if success else ""
    return f"{number:.1f}{suffix}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="temporal identity 실패 원인을 분류합니다.")
    parser.add_argument("names", nargs="*")
    parser.add_argument("--out", default="03_output/2026-06-27_task48_failure_report_v1.md")
    args = parser.parse_args(argv)

    rows = failure_rows(names=args.names or None)
    text = markdown_report(rows)
    print(text)
    print(json.dumps(rows, ensure_ascii=False))
    out = ROOT / args.out
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    except PermissionError as exc:
        print(f"[write-skip] {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
