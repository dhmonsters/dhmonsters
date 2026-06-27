# guarded 후보 파라미터 sweep 리포트를 생성합니다.
from __future__ import annotations

import argparse
import math
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from _selector_shadow_gt_replay_score import score_gt_clip


def parse_int_list(value: str) -> list[int]:
    return [int(item.strip()) for item in str(value).split(",") if item.strip()]


def parse_float_list(value: str) -> list[float]:
    return [float(item.strip()) for item in str(value).split(",") if item.strip()]


def sweep_configs(
    *,
    min_background_frames: Sequence[int],
    match_distances: Sequence[float],
    shape_pcts: Sequence[float],
    max_steps: Sequence[float],
    live_max_candidates: Sequence[int] = (8,),
) -> list[dict[str, float | int]]:
    configs = []
    for min_bg in min_background_frames:
        for match_px in match_distances:
            for shape_pct in shape_pcts:
                for max_step in max_steps:
                    for live_max in live_max_candidates:
                        configs.append({
                            "min_bg": int(min_bg),
                            "match_px": float(match_px),
                            "shape_pct": float(shape_pct),
                            "max_step": float(max_step),
                            "live_max_candidates": int(live_max),
                        })
    return configs


def summarize_sweep_item(
    config: Mapping[str, object],
    results: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    reasons: Counter[str] = Counter()
    emitted_frames = 0
    selected_frames = 0
    guarded_success = 0
    selected_success = 0
    guarded_means = []
    selected_means = []
    for result in results:
        emitted_frames += int(result.get("guarded_emitted_frames", 0) or 0)
        selected_frames += int(result.get("guarded_selected_frames", 0) or 0)
        reasons.update(_reason_counts(result.get("guarded_reason_counts", {})))
        guarded_score = result.get("guarded_emitted", {})
        selected_score = result.get("selected", {})
        if _score_success(guarded_score):
            guarded_success += 1
        if _score_success(selected_score):
            selected_success += 1
        guarded_mean = _score_mean(guarded_score)
        selected_mean = _score_mean(selected_score)
        if guarded_mean is not None:
            guarded_means.append(guarded_mean)
        if selected_mean is not None:
            selected_means.append(selected_mean)

    return {
        "min_bg": int(config.get("min_bg", 0) or 0),
        "match_px": float(config.get("match_px", 0.0) or 0.0),
        "shape_pct": float(config.get("shape_pct", 0.0) or 0.0),
        "max_step": float(config.get("max_step", 0.0) or 0.0),
        "live_max_candidates": int(config.get("live_max_candidates", 8) or 8),
        "clips": len(results),
        "guarded_success": guarded_success,
        "selected_success": selected_success,
        "emitted_frames": emitted_frames,
        "selected_frames": selected_frames,
        "guarded_mean": _mean(guarded_means),
        "selected_mean": _mean(selected_means),
        "reason_counts": _sorted_counts(reasons),
    }


def run_sweep(
    names: Sequence[str],
    *,
    root: Path,
    configs: Sequence[Mapping[str, object]],
    success_px: float = 40.0,
    include_local_box: bool = False,
) -> list[dict[str, object]]:
    summaries = []
    for config in configs:
        results = [
            score_gt_clip(
                name,
                root=root,
                success_px=success_px,
                include_local_box=include_local_box,
                enable_guarded_decal_identity=True,
                guarded_decal_min_background_frames=int(config["min_bg"]),
                guarded_decal_match_distance_px=float(config["match_px"]),
                guarded_decal_shape_pct=float(config["shape_pct"]),
                guarded_decal_max_step_px=float(config["max_step"]),
                live_max_candidates=int(config.get("live_max_candidates", 8) or 8),
            )
            for name in names
        ]
        summaries.append(summarize_sweep_item(config, results))
    return summaries


def write_markdown_report(summaries: Iterable[Mapping[str, object]]) -> str:
    items = list(summaries)
    lines = [
        "# guarded parameter sweep 리포트",
        "",
        "| min_bg | match_px | shape_pct | max_step | live_max | clips | guarded_success | selected_success | emitted | selected | guarded_mean | selected_mean | reasons |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in items:
        lines.append(
            "| {min_bg} | {match_px:.1f} | {shape_pct:.1f} | {max_step:.1f} | {live_max} | {clips} | {guarded_success} | {selected_success} | {emitted_frames} | {selected_frames} | {guarded_mean} | {selected_mean} | {reasons} |".format(
                min_bg=int(item.get("min_bg", 0) or 0),
                match_px=float(item.get("match_px", 0.0) or 0.0),
                shape_pct=float(item.get("shape_pct", 0.0) or 0.0),
                max_step=float(item.get("max_step", 0.0) or 0.0),
                live_max=int(item.get("live_max_candidates", 8) or 8),
                clips=int(item.get("clips", 0) or 0),
                guarded_success=int(item.get("guarded_success", 0) or 0),
                selected_success=int(item.get("selected_success", 0) or 0),
                emitted_frames=int(item.get("emitted_frames", 0) or 0),
                selected_frames=int(item.get("selected_frames", 0) or 0),
                guarded_mean=_fmt_float(item.get("guarded_mean")),
                selected_mean=_fmt_float(item.get("selected_mean")),
                reasons=_fmt_counts(item.get("reason_counts", {})),
            )
        )
    return "\n".join(lines) + "\n"


def _reason_counts(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): int(count) for key, count in value.items()}


def _score_success(value: object) -> bool:
    return isinstance(value, Mapping) and bool(value.get("success", False))


def _score_mean(value: object) -> float | None:
    if not isinstance(value, Mapping) or not int(value.get("n", 0) or 0):
        return None
    mean = float(value.get("mean", float("nan")))
    if not math.isfinite(mean):
        return None
    return mean


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return round(float(sum(values) / len(values)), 3)


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
    return ", ".join(f"{key}={int(count)}" for key, count in _sorted_counts(value).items())


def _fmt_float(value: object) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(number):
        return "-"
    return f"{number:.1f}"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="guarded decal identity 파라미터 sweep 리포트를 생성합니다.")
    parser.add_argument("names", nargs="*")
    parser.add_argument("--root", default=".")
    parser.add_argument("--out", default="03_output/2026-06-27_guarded_sweep_report_v1.md")
    parser.add_argument("--min-bg", default="2")
    parser.add_argument("--match-px", default="10,16")
    parser.add_argument("--shape-pct", default="6")
    parser.add_argument("--max-step", default="80,180")
    parser.add_argument("--live-max-candidates", default="8")
    parser.add_argument("--success-px", type=float, default=40.0)
    parser.add_argument("--with-local-box", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root)
    names = list(args.names) or [
        path.name
        for path in sorted((root / "_gt_frames").iterdir())
        if path.is_dir()
    ]
    configs = sweep_configs(
        min_background_frames=parse_int_list(args.min_bg),
        match_distances=parse_float_list(args.match_px),
        shape_pcts=parse_float_list(args.shape_pct),
        max_steps=parse_float_list(args.max_step),
        live_max_candidates=parse_int_list(args.live_max_candidates),
    )
    summaries = run_sweep(
        names,
        root=root,
        configs=configs,
        success_px=args.success_px,
        include_local_box=args.with_local_box,
    )
    text = write_markdown_report(summaries)
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
