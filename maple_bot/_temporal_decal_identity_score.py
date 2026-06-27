# 투명도형 퍼즐 decal identity selector를 16GT에서 비교 채점한다.
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import mean
import time
from typing import Mapping, Sequence

from _background_identity_signal import load_expected_background_with_ids, path_background_identity_stats
from _fast_gt_score import (
    ROOT,
    gt_clip_names,
    load_jsonl_rows,
    raw_box_oracle_path,
    raw_center_oracle_path,
    score_path,
)
from _selector_shadow_gt_replay_score import load_red_gt
from _temporal_identity_selector import (
    TemporalFrame,
    TemporalIdentityConfig,
    frames_from_jsonl_rows,
    select_temporal_identity,
)
from _temporal_transition_report import markdown_report as transition_markdown_report
from _temporal_transition_report import transition_window_rows


Point = tuple[float, float]
METRICS = (
    "temporal_identity",
    "decal_identity",
    "decal_identity_raw",
    "raw_center_oracle",
    "raw_box_oracle",
)


def decal_identity_config(
    *,
    background_identity_penalty_weight: float = 60.0,
    split_support_weight: float = 12.0,
    prediction_hold_cost: float = 1.0,
) -> TemporalIdentityConfig:
    return TemporalIdentityConfig(
        background_identity_penalty_weight=float(background_identity_penalty_weight),
        background_run_weight=60.0,
        background_run_grace=0,
        split_support_weight=float(split_support_weight),
        split_support_gate=40.0,
        prediction_hold_cost=float(prediction_hold_cost),
    )


def decal_identity_path_from_frames(
    frames: Sequence[TemporalFrame],
    *,
    anchor: Point | None,
    config: TemporalIdentityConfig | None = None,
) -> dict[int, Point]:
    result = select_temporal_identity(frames, anchor=anchor, config=config or decal_identity_config())
    return dict(result.path)


def choose_guarded_decal_path(
    base_path: Mapping[int, Point],
    decal_path: Mapping[int, Point],
    expected_background_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]],
    *,
    frames: Sequence[int],
    min_base_background_ratio: float = 0.95,
    min_background_ratio_drop: float = 0.10,
    max_step: float = 80.0,
) -> dict[int, Point]:
    base_stats = path_background_identity_stats(dict(base_path), dict(expected_background_by_frame), frames)
    decal_stats = path_background_identity_stats(dict(decal_path), dict(expected_background_by_frame), frames)
    _mean_step, decal_max_step = _path_step_stats(decal_path)
    base_ratio = float(base_stats["matched_ratio"])
    decal_ratio = float(decal_stats["matched_ratio"])
    if (
        base_ratio >= float(min_base_background_ratio)
        and decal_ratio <= base_ratio - float(min_background_ratio_drop)
        and decal_max_step <= float(max_step)
    ):
        return dict(decal_path)
    return dict(base_path)


def decal_identity_result_from_rows(
    name: str,
    rows: Sequence[Mapping[str, object]],
    *,
    min_gt_frame: int = 50,
    default_candidate_size: float = 24.0,
    config: TemporalIdentityConfig | None = None,
) -> tuple[dict[int, Point], list[TemporalFrame]]:
    expected_background, _background_meta = load_expected_background_with_ids(
        str(name),
        range(max(0, int(min_gt_frame)), len(rows)),
    )
    frames, anchor = frames_from_jsonl_rows(
        rows,
        default_size=default_candidate_size,
        expected_background_by_frame=expected_background,
    )
    return decal_identity_path_from_frames(frames, anchor=anchor, config=config), frames


def score_clip(
    name: str,
    *,
    root: Path = ROOT,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    min_gt_frame: int = 50,
    default_candidate_size: float = 24.0,
    config: TemporalIdentityConfig | None = None,
) -> dict[str, object]:
    rows = load_jsonl_rows(root / "_record_debug" / f"{name}.jsonl")
    gt = load_red_gt(name, root=root, min_frame=min_gt_frame)
    expected_background, _background_meta = load_expected_background_with_ids(
        str(name),
        range(max(0, int(min_gt_frame)), len(rows)),
    )
    frames, anchor = frames_from_jsonl_rows(
        rows,
        default_size=default_candidate_size,
        expected_background_by_frame=expected_background,
    )
    base_result = select_temporal_identity(frames, anchor=anchor)
    decal_result = select_temporal_identity(frames, anchor=anchor, config=config or decal_identity_config())
    base_path = dict(base_result.path)
    decal_path = dict(decal_result.path)
    guarded_path = choose_guarded_decal_path(
        base_path,
        decal_path,
        expected_background,
        frames=sorted(gt),
    )
    raw_center = raw_center_oracle_path(rows, gt, default_size=default_candidate_size)
    raw_box = raw_box_oracle_path(rows, gt, default_size=default_candidate_size)
    paths = {
        "temporal_identity": base_path,
        "decal_identity": guarded_path,
        "decal_identity_raw": decal_path,
        "raw_center_oracle": raw_center,
        "raw_box_oracle": raw_box,
    }
    result: dict[str, object] = {"name": name, "frames": len(rows), "gt_frames": len(gt)}
    for metric, path in paths.items():
        result[metric] = score_path(path, gt, success_px=success_px, min_coverage=min_coverage)
    chosen_result = decal_result if guarded_path == decal_path else base_result
    result["transition_rows"] = transition_window_rows(str(name), frames, chosen_result, gt, fail_px=40.0, radius=5)
    return result


def score_all(
    *,
    root: Path = ROOT,
    names: Sequence[str] | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    min_gt_frame: int = 50,
    default_candidate_size: float = 24.0,
    config: TemporalIdentityConfig | None = None,
) -> list[dict[str, object]]:
    return [
        score_clip(
            str(name),
            root=root,
            success_px=success_px,
            min_coverage=min_coverage,
            min_gt_frame=min_gt_frame,
            default_candidate_size=default_candidate_size,
            config=config,
        )
        for name in (list(names) if names is not None else gt_clip_names(root=root))
    ]


def markdown_report(results: Sequence[Mapping[str, object]], *, elapsed_s: float | None = None) -> str:
    lines = [
        "# Task59 decal identity score",
        "",
        "배경 데칼로 설명되는 후보를 직접 감점하고, hold 이후 split recovery 후보를 보너스 처리한 실험 경로를 비교했다.",
        "",
    ]
    if elapsed_s is not None:
        lines.extend([f"- elapsed: {elapsed_s:.2f}s.", ""])
    lines.extend(
        [
            "| clip | GT | temporal | guarded decal | raw decal | raw center | raw box |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for result in results:
        lines.append(
            "| `{name}` | {gt} | {temporal} | {decal} | {raw_decal} | {raw_center} | {raw_box} |".format(
                name=result.get("name", ""),
                gt=int(result.get("gt_frames", 0) or 0),
                temporal=_fmt_score(result.get("temporal_identity")),
                decal=_fmt_score(result.get("decal_identity")),
                raw_decal=_fmt_score(result.get("decal_identity_raw")),
                raw_center=_fmt_score(result.get("raw_center_oracle")),
                raw_box=_fmt_score(result.get("raw_box_oracle")),
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


def combined_transition_report(results: Sequence[Mapping[str, object]]) -> str:
    rows = [
        row
        for result in results
        for row in result.get("transition_rows", [])
        if isinstance(row, Mapping)
    ]
    return transition_markdown_report(rows)


def _path_step_stats(path: Mapping[int, Point]) -> tuple[float, float]:
    keys = sorted(path)
    steps = []
    for left, right in zip(keys, keys[1:]):
        a = path[int(left)]
        b = path[int(right)]
        steps.append(math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1])))
    if not steps:
        return 0.0, 0.0
    return float(sum(steps) / len(steps)), float(max(steps))


def _fmt_score(score: object) -> str:
    if not isinstance(score, Mapping) or not score.get("n"):
        return "-"
    suffix = " OK" if score.get("success") else ""
    return f"{float(score['mean']):.1f}{suffix}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="decal identity temporal selector score")
    parser.add_argument("names", nargs="*")
    parser.add_argument("--out", default="03_output/2026-06-27_task59_decal_identity_score_v1.md")
    parser.add_argument("--transition-out", default="03_output/2026-06-27_task55_failure_transition_v1.md")
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
    transition_text = combined_transition_report(results)
    print(text)
    print(transition_text)
    print(json.dumps(results, ensure_ascii=False))
    for out_name, out_text in ((args.out, text), (args.transition_out, transition_text)):
        out = ROOT / out_name
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(out_text, encoding="utf-8")
        except PermissionError as exc:
            print(f"[write-skip] {out}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
