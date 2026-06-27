# 투명도형 퍼즐 후보 residual 신호와 박스 예측 복원을 16GT에서 비교 채점한다.
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import math
from pathlib import Path
import time
from statistics import mean
from typing import Mapping, Sequence

from _background_identity_signal import load_expected_background_with_ids
from _fast_gt_score import (
    ROOT,
    gt_clip_names,
    load_jsonl_rows,
    raw_box_oracle_path,
    raw_center_oracle_path,
    score_path,
    track_path_from_rows,
)
from _local_residual_signal import periodic_diff_by_frame
from _selector_shadow_gt_replay_score import load_red_gt
from _temporal_candidate_features import (
    candidate_local_appearance_supports,
    point_inside_candidate_box,
    prediction_box_point,
)
from _temporal_identity_selector import (
    TemporalFrame,
    TemporalIdentityConfig,
    TemporalIdentityResult,
    frames_from_jsonl_rows,
    select_temporal_identity,
)


Point = tuple[float, float]
METRICS = (
    "temporal_identity",
    "appearance_identity",
    "appearance_box_identity",
    "raw_center_oracle",
    "raw_box_oracle",
)


def attach_appearance_supports(
    name: str,
    frames: Sequence[TemporalFrame],
    *,
    min_frame: int = 50,
    inner_radius: int = 6,
    outer_radius: int = 16,
) -> tuple[list[TemporalFrame], dict[str, object]]:
    wanted = [int(frame.frame_index) for frame in frames if int(frame.frame_index) >= int(min_frame)]
    diff_by_frame, meta = periodic_diff_by_frame(str(name), wanted)
    out = []
    covered = 0
    for frame in frames:
        diff = diff_by_frame.get(int(frame.frame_index))
        if diff is None or not frame.candidates:
            out.append(replace(frame, appearance_supports=()))
            continue
        covered += 1
        out.append(
            replace(
                frame,
                appearance_supports=candidate_local_appearance_supports(
                    diff,
                    frame.candidates,
                    inner_radius=inner_radius,
                    outer_radius=outer_radius,
                ),
            )
        )
    meta = dict(meta)
    meta["appearance_covered_frames"] = covered
    return out, meta


def box_projected_identity_path(
    frames: Sequence[TemporalFrame],
    result: TemporalIdentityResult,
    *,
    anchor: Point | None,
    config: TemporalIdentityConfig,
) -> dict[int, Point]:
    frame_by_index = {int(frame.frame_index): frame for frame in frames}
    ordered_indices = sorted(result.path)
    if not ordered_indices:
        return {}

    first = result.path[ordered_indices[0]]
    last = (float(anchor[0]), float(anchor[1])) if anchor is not None else first
    vx = 0.0
    vy = 0.0
    path: dict[int, Point] = {}
    for frame_index in ordered_indices:
        original = result.path[int(frame_index)]
        predicted = (last[0] + vx, last[1] + vy)
        frame = frame_by_index.get(int(frame_index))
        candidate_index = result.candidate_indices.get(int(frame_index))
        point = original
        if frame is not None and candidate_index is not None and 0 <= candidate_index < len(frame.candidates):
            candidate = frame.candidates[int(candidate_index)]
            if point_inside_candidate_box(
                predicted,
                candidate,
                scale=float(config.prediction_hold_box_scale),
            ):
                point = prediction_box_point(predicted, candidate)
        path[int(frame_index)] = point
        dx = float(point[0]) - float(last[0])
        dy = float(point[1]) - float(last[1])
        alpha = float(config.velocity_alpha)
        vx = alpha * vx + (1.0 - alpha) * dx
        vy = alpha * vy + (1.0 - alpha) * dy
        last = point
    return path


def identity_paths_with_residual(
    name: str,
    rows: Sequence[Mapping[str, object]],
    *,
    min_gt_frame: int = 50,
    default_candidate_size: float = 24.0,
    appearance_weight: float = 14.0,
) -> tuple[dict[str, dict[int, Point]], dict[str, object]]:
    expected_background, _background_meta = load_expected_background_with_ids(
        str(name),
        range(max(0, int(min_gt_frame)), len(rows)),
    )
    base_frames, anchor = frames_from_jsonl_rows(
        rows,
        default_size=default_candidate_size,
        expected_background_by_frame=expected_background,
    )
    appearance_frames, residual_meta = attach_appearance_supports(
        str(name),
        base_frames,
        min_frame=min_gt_frame,
    )
    base_config = TemporalIdentityConfig()
    appearance_config = TemporalIdentityConfig(appearance_support_weight=float(appearance_weight))
    base = select_temporal_identity(base_frames, anchor=anchor, config=base_config)
    appearance = select_temporal_identity(appearance_frames, anchor=anchor, config=appearance_config)
    return (
        {
            "temporal_identity": dict(base.path),
            "appearance_identity": dict(appearance.path),
            "appearance_box_identity": box_projected_identity_path(
                appearance_frames,
                appearance,
                anchor=anchor,
                config=appearance_config,
            ),
        },
        residual_meta,
    )


def score_clip(
    name: str,
    *,
    root: Path = ROOT,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    min_gt_frame: int = 50,
    default_candidate_size: float = 24.0,
    appearance_weight: float = 14.0,
) -> dict[str, object]:
    rows = load_jsonl_rows(root / "_record_debug" / f"{name}.jsonl")
    gt = load_red_gt(name, root=root, min_frame=min_gt_frame)
    paths, meta = identity_paths_with_residual(
        name,
        rows,
        min_gt_frame=min_gt_frame,
        default_candidate_size=default_candidate_size,
        appearance_weight=appearance_weight,
    )
    paths["raw_center_oracle"] = raw_center_oracle_path(rows, gt, default_size=default_candidate_size)
    paths["raw_box_oracle"] = raw_box_oracle_path(rows, gt, default_size=default_candidate_size)
    result: dict[str, object] = {
        "name": name,
        "frames": len(rows),
        "gt_frames": len(gt),
        "appearance_weight": float(appearance_weight),
        "residual_meta": meta,
    }
    for metric, path in paths.items():
        result[metric] = score_path(path, gt, success_px=success_px, min_coverage=min_coverage)
    return result


def score_all(
    *,
    root: Path = ROOT,
    names: Sequence[str] | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    min_gt_frame: int = 50,
    default_candidate_size: float = 24.0,
    appearance_weight: float = 14.0,
) -> list[dict[str, object]]:
    return [
        score_clip(
            str(name),
            root=root,
            success_px=success_px,
            min_coverage=min_coverage,
            min_gt_frame=min_gt_frame,
            default_candidate_size=default_candidate_size,
            appearance_weight=appearance_weight,
        )
        for name in (list(names) if names is not None else gt_clip_names(root=root))
    ]


def markdown_report(results: Sequence[Mapping[str, object]], *, elapsed_s: float | None = None) -> str:
    lines = [
        "# Task51-53 residual identity score",
        "",
        "시간축 선택기에 후보별 local appearance residual을 붙이고, 선택 후보 박스 안에서 예측점을 복원한 결과를 비교했다.",
        "",
    ]
    if elapsed_s is not None:
        lines.extend([f"- elapsed: {elapsed_s:.2f}s.", ""])
    lines.extend(
        [
            "| clip | GT | temporal | appearance | appearance+box | raw center | raw box | residual frames |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for result in results:
        meta = result.get("residual_meta")
        covered = meta.get("appearance_covered_frames", 0) if isinstance(meta, Mapping) else 0
        lines.append(
            "| `{name}` | {gt} | {temporal} | {appearance} | {appearance_box} | {raw_center} | {raw_box} | {covered} |".format(
                name=result.get("name", ""),
                gt=int(result.get("gt_frames", 0) or 0),
                temporal=_fmt_score(result.get("temporal_identity")),
                appearance=_fmt_score(result.get("appearance_identity")),
                appearance_box=_fmt_score(result.get("appearance_box_identity")),
                raw_center=_fmt_score(result.get("raw_center_oracle")),
                raw_box=_fmt_score(result.get("raw_box_oracle")),
                covered=int(covered or 0),
            )
        )
    lines.extend(["", "## Summary", ""])
    for metric in METRICS:
        scores = [result.get(metric) for result in results]
        successes = sum(1 for score in scores if isinstance(score, Mapping) and bool(score.get("success")))
        means = [
            float(score["mean"])
            for score in scores
            if isinstance(score, Mapping) and math.isfinite(float(score.get("mean", float("inf"))))
        ]
        avg = mean(means) if means else float("nan")
        lines.append(f"- `{metric}`: {successes}/{len(results)}, mean {avg:.1f}px.")
    return "\n".join(lines) + "\n"


def _fmt_score(score: object) -> str:
    if not isinstance(score, Mapping) or not score.get("n"):
        return "-"
    suffix = " OK" if score.get("success") else ""
    return f"{float(score['mean']):.1f}{suffix}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="candidate residual temporal identity score")
    parser.add_argument("names", nargs="*")
    parser.add_argument("--out", default="03_output/2026-06-27_task51_53_residual_score_v1.md")
    parser.add_argument("--success-px", type=float, default=40.0)
    parser.add_argument("--min-coverage", type=float, default=0.9)
    parser.add_argument("--min-gt-frame", type=int, default=50)
    parser.add_argument("--candidate-default-size", type=float, default=24.0)
    parser.add_argument("--appearance-weight", type=float, default=14.0)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    results = score_all(
        names=args.names or None,
        success_px=args.success_px,
        min_coverage=args.min_coverage,
        min_gt_frame=args.min_gt_frame,
        default_candidate_size=args.candidate_default_size,
        appearance_weight=args.appearance_weight,
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
