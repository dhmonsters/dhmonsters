# selector shadow rescue를 16개 빨간점 GT 녹화에서 라이브 방식으로 재생해 채점합니다.
from __future__ import annotations

import argparse
import glob
import json
import math
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Mapping, Sequence

from core.vision.transparent_track_health import TransparentTrackHealthSelector


ROOT = Path(__file__).resolve().parent
Point = tuple[float, float]
GUARDED_DEBUG_NUMERIC_FIELDS = (
    "period",
    "background_frames",
    "expected_frames",
    "background_ratio",
    "max_step",
)


def _load_jsonl(*args, **kwargs):
    from _selector_shadow_backfill import _load_jsonl as load_jsonl

    return load_jsonl(*args, **kwargs)


def backfill_selector_shadow_rows(*args, **kwargs):
    from _selector_shadow_backfill import backfill_selector_shadow_rows as backfill

    return backfill(*args, **kwargs)


def _new_runtime():
    from core.vision.transparent_family_selector_runtime import TransparentFamilySelectorRuntime

    return TransparentFamilySelectorRuntime()


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


def red_mark(bgr: object | None) -> Point | None:
    if bgr is None:
        return None
    cv2, np = _import_cv2_np()
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = (
        cv2.inRange(hsv, np.array([0, 120, 100]), np.array([8, 255, 255]))
        | cv2.inRange(hsv, np.array([174, 120, 100]), np.array([180, 255, 255]))
    )
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    contour = max(contours, key=cv2.contourArea)
    if cv2.contourArea(contour) < 8:
        return None
    moments = cv2.moments(contour)
    if moments["m00"] <= 0:
        return None
    return (moments["m10"] / moments["m00"], moments["m01"] / moments["m00"])


def load_red_gt(name: str, *, root: Path = ROOT, min_frame: int = 50) -> dict[int, Point]:
    cv2, _np = _import_cv2_np()
    gt = {}
    gt_dir = root / "_gt_frames" / name
    for path in sorted(glob.glob(str(gt_dir / "f*.png"))):
        frame = int(Path(path).stem[1:4])
        if frame < int(min_frame):
            continue
        point = red_mark(cv2.imread(path))
        if point is not None:
            gt[frame] = point
    return gt


def frame_shape_from_mp4(name: str, *, root: Path = ROOT) -> tuple[int, int] | None:
    cv2, _np = _import_cv2_np()
    cap = cv2.VideoCapture(str(root / "_record_debug" / f"{name}.mp4"))
    try:
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        return tuple(frame.shape[:2])
    finally:
        cap.release()


def track_path_from_rows(rows: Sequence[Mapping[str, object]]) -> dict[int, Point]:
    path = {}
    for frame, row in enumerate(rows):
        point = _point(row.get("track"))
        if point is not None:
            path[int(frame)] = point
    return path


def shadow_point_path_from_rows(rows: Sequence[Mapping[str, object]]) -> dict[int, Point]:
    path = {}
    for frame, row in enumerate(rows):
        record = row.get("selector_shadow")
        if not isinstance(record, Mapping) or not bool(record.get("available", False)):
            continue
        point = _point(record.get("point"))
        if point is not None:
            path[int(frame)] = point
    return path


def guarded_selected_path_from_rows(rows: Sequence[Mapping[str, object]]) -> dict[int, Point]:
    path = {}
    for frame, row in enumerate(rows):
        record = row.get("selector_shadow")
        if not isinstance(record, Mapping) or not bool(record.get("available", False)):
            continue
        family = str(record.get("family", ""))
        if not family.lower().startswith("guarded_decal_identity"):
            continue
        point = _point(record.get("point"))
        if point is not None:
            path[int(frame)] = point
    return path


def guarded_emitted_path_from_rows(rows: Sequence[Mapping[str, object]]) -> dict[int, Point]:
    path = {}
    for frame, row in enumerate(rows):
        live_family = row.get("live_family")
        if not isinstance(live_family, Mapping):
            continue
        points = live_family.get("points")
        if not isinstance(points, Mapping):
            continue
        for family, value in points.items():
            if not str(family).lower().startswith("guarded_decal_identity"):
                continue
            point = _point(value)
            if point is not None:
                path[int(frame)] = point
                break
    return path


def guarded_reason_counts_from_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        guarded = _guarded_debug_from_row(row)
        if guarded is None:
            continue
        reason = _guarded_reason_from_debug(guarded)
        if reason:
            counts[reason] += 1
    return _sorted_counts(counts)


def guarded_debug_stats_from_rows(rows: Sequence[Mapping[str, object]]) -> dict[str, dict[str, object]]:
    counts: Counter[str] = Counter()
    buckets: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        guarded = _guarded_debug_from_row(row)
        if guarded is None:
            continue
        reason = _guarded_reason_from_debug(guarded)
        if not reason:
            continue
        counts[reason] += 1
        fields = buckets.setdefault(reason, {})
        for field in GUARDED_DEBUG_NUMERIC_FIELDS:
            value = guarded.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            fields.setdefault(field, []).append(float(value))

    out: dict[str, dict[str, object]] = {}
    for reason, count in _sorted_counts(counts).items():
        item: dict[str, object] = {"count": int(count)}
        for field in GUARDED_DEBUG_NUMERIC_FIELDS:
            values = buckets.get(reason, {}).get(field, [])
            if values:
                item[field] = _number_summary(values)
        out[reason] = item
    return out


def allowed_rescue_path_from_rows(rows: Sequence[Mapping[str, object]]) -> dict[int, Point]:
    path = {}
    for frame, row in enumerate(rows):
        rescue = _allowed_selector_rescue(row)
        if rescue is not None:
            path[int(frame)] = rescue
    return path


def apply_live_health_selection(
    rows: Sequence[Mapping[str, object]],
    *,
    frame_shape: Sequence[int] | None,
    health_selector: TransparentTrackHealthSelector | None = None,
) -> tuple[dict[int, Point], dict[int, dict]]:
    selector = health_selector or TransparentTrackHealthSelector()
    path: dict[int, Point] = {}
    decisions: dict[int, dict] = {}
    for frame, row in enumerate(rows):
        primary = _point(row.get("track"))
        rescue = _allowed_selector_rescue(row)
        decision = selector.update(
            primary=primary,
            rescue=rescue,
            frame_shape=frame_shape,
        )
        if decision.point is not None:
            path[int(frame)] = decision.point
        decisions[int(frame)] = {
            "source": decision.source,
            "reason": decision.reason,
            "unhealthy": decision.unhealthy,
            "suspect_frames": decision.suspect_frames,
            "rescue_hold": decision.rescue_hold,
            "primary_error": decision.primary_error,
            "out_of_bounds": decision.out_of_bounds,
        }
    return path, decisions


def score_path(
    path: Mapping[int, Point],
    gt_by_frame: Mapping[int, Point],
    frames: Sequence[int],
    *,
    success_px: float = 40.0,
) -> dict:
    errors = []
    worst = []
    for frame in frames:
        if frame not in path or frame not in gt_by_frame:
            continue
        error = _dist(path[frame], gt_by_frame[frame])
        errors.append(error)
        worst.append({
            "frame": int(frame),
            "error": round(error, 1),
            "point": [round(path[frame][0], 1), round(path[frame][1], 1)],
            "gt": [round(gt_by_frame[frame][0], 1), round(gt_by_frame[frame][1], 1)],
        })
    if not errors:
        return {
            "n": 0,
            "mean": float("nan"),
            "median": float("nan"),
            "max": float("nan"),
            "success": False,
            "worst": [],
        }
    worst.sort(key=lambda item: item["error"], reverse=True)
    return {
        "n": len(errors),
        "mean": float(sum(errors) / len(errors)),
        "median": float(median(errors)),
        "max": float(max(errors)),
        "success": float(sum(errors) / len(errors)) <= float(success_px),
        "worst": worst[:5],
    }


def score_gt_clip(
    name: str,
    *,
    root: Path = ROOT,
    runtime=None,
    min_gt_frame: int = 50,
    success_px: float = 40.0,
    include_local_box: bool = True,
    live_max_candidates: int = 8,
    enable_guarded_decal_identity: bool = False,
    guarded_decal_min_background_frames: int = 3,
    guarded_decal_match_distance_px: float = 10.0,
    guarded_decal_shape_pct: float = 6.0,
    guarded_decal_max_step_px: float = 80.0,
) -> dict:
    source = root / "_record_debug" / f"{name}.jsonl"
    rows = _load_jsonl(source)
    backfilled = backfill_selector_shadow_rows(
        rows,
        runtime=runtime or _new_runtime(),
        clip_id=name,
        window=24,
        min_frames=8,
        shadow_min_frames=1,
        emit_every=1,
        max_candidates=8,
        live_max_candidates=int(live_max_candidates),
        include_local_box=include_local_box,
        merge_context_frames=6,
        merge_min_size=175.0,
        merge_size_ratio=1.30,
        enable_guarded_decal_identity=enable_guarded_decal_identity,
        guarded_decal_min_background_frames=guarded_decal_min_background_frames,
        guarded_decal_match_distance_px=guarded_decal_match_distance_px,
        guarded_decal_shape_pct=guarded_decal_shape_pct,
        guarded_decal_max_step_px=guarded_decal_max_step_px,
        include_live_family=enable_guarded_decal_identity,
    )
    gt = load_red_gt(name, root=root, min_frame=min_gt_frame)
    frames = [frame for frame in sorted(gt) if frame < len(backfilled)]
    frame_shape = frame_shape_from_mp4(name, root=root)

    track_path = track_path_from_rows(backfilled)
    shadow_path = shadow_point_path_from_rows(backfilled)
    guarded_emitted_path = guarded_emitted_path_from_rows(backfilled)
    guarded_path = guarded_selected_path_from_rows(backfilled)
    guarded_reason_counts = guarded_reason_counts_from_rows(backfilled)
    guarded_debug_stats = guarded_debug_stats_from_rows(backfilled)
    rescue_path = allowed_rescue_path_from_rows(backfilled)
    selected_path, decisions = apply_live_health_selection(
        backfilled,
        frame_shape=frame_shape,
    )
    rescue_used = [
        frame
        for frame, decision in decisions.items()
        if decision.get("source") == "rescue"
    ]

    return {
        "name": name,
        "frames": len(rows),
        "gt_frames": len(gt),
        "scored_frames": len(frames),
        "frame_shape": frame_shape,
        "selector_records": sum(1 for row in backfilled if isinstance(row.get("selector_shadow"), Mapping)),
        "include_local_box": bool(include_local_box),
        "live_max_candidates": int(live_max_candidates),
        "enable_guarded_decal_identity": bool(enable_guarded_decal_identity),
        "guarded_config": {
            "min_background_frames": int(guarded_decal_min_background_frames),
            "match_distance_px": float(guarded_decal_match_distance_px),
            "shape_pct": float(guarded_decal_shape_pct),
            "max_step_px": float(guarded_decal_max_step_px),
        },
        "guarded_emitted_frames": len(guarded_emitted_path),
        "guarded_selected_frames": len(guarded_path),
        "guarded_reason_counts": guarded_reason_counts,
        "guarded_debug_stats": guarded_debug_stats,
        "rescue_allowed_frames": len(rescue_path),
        "rescue_used_frames": len(rescue_used),
        "rescue_used_sample": rescue_used[:10],
        "track": score_path(track_path, gt, frames, success_px=success_px),
        "shadow": score_path(shadow_path, gt, frames, success_px=success_px),
        "guarded_emitted": score_path(guarded_emitted_path, gt, frames, success_px=success_px),
        "guarded_selected": score_path(guarded_path, gt, frames, success_px=success_px),
        "rescue_allowed": score_path(rescue_path, gt, frames, success_px=success_px),
        "selected": score_path(selected_path, gt, frames, success_px=success_px),
    }


def score_all_gt_clips(
    *,
    root: Path = ROOT,
    names: Sequence[str] | None = None,
    success_px: float = 40.0,
    include_local_box: bool = True,
    live_max_candidates: int = 8,
    enable_guarded_decal_identity: bool = False,
    guarded_decal_min_background_frames: int = 3,
    guarded_decal_match_distance_px: float = 10.0,
    guarded_decal_shape_pct: float = 6.0,
    guarded_decal_max_step_px: float = 80.0,
) -> list[dict]:
    from core.vision.transparent_family_selector_runtime import TransparentFamilySelectorRuntime

    if names is None:
        names = [
            path.name
            for path in sorted((root / "_gt_frames").iterdir())
            if path.is_dir()
        ]
    runtime = TransparentFamilySelectorRuntime()
    return [
        score_gt_clip(
            name,
            root=root,
            runtime=runtime,
            success_px=success_px,
            include_local_box=include_local_box,
            live_max_candidates=live_max_candidates,
            enable_guarded_decal_identity=enable_guarded_decal_identity,
            guarded_decal_min_background_frames=guarded_decal_min_background_frames,
            guarded_decal_match_distance_px=guarded_decal_match_distance_px,
            guarded_decal_shape_pct=guarded_decal_shape_pct,
            guarded_decal_max_step_px=guarded_decal_max_step_px,
        )
        for name in names
    ]


def markdown_report(results: Sequence[Mapping[str, object]]) -> str:
    lines = [
        "# selector shadow GT 리플레이 채점 결과",
        "",
        "현재 라이브와 같은 구조로 selector shadow rescue를 건강 선택기에 넣어 선택한 빨간점 GT를 재생했다.",
        "",
        "| 클립 | GT | track | shadow | guarded emitted | guarded selected | allowed rescue | selected | emitted/selected/allowed/used |",
        "|---|---:|---|---|---|---|---|---|---:|",
    ]
    for result in results:
        lines.append(
            "| `{name}` | {gt} | {track} | {shadow} | {guarded_emitted} | {guarded_selected} | {allowed} | {selected} | {emitted_count}/{selected_count}/{allowed_count}/{used_count} |".format(
                name=result.get("name", ""),
                gt=result.get("scored_frames", 0),
                track=_fmt_score(result.get("track", {})),
                shadow=_fmt_score(result.get("shadow", {})),
                guarded_emitted=_fmt_score(result.get("guarded_emitted", {})),
                guarded_selected=_fmt_score(result.get("guarded_selected", {})),
                allowed=_fmt_score(result.get("rescue_allowed", {})),
                selected=_fmt_score(result.get("selected", {})),
                emitted_count=result.get("guarded_emitted_frames", 0),
                selected_count=result.get("guarded_selected_frames", 0),
                allowed_count=result.get("rescue_allowed_frames", 0),
                used_count=result.get("rescue_used_frames", 0),
            )
        )

    selected_success = sum(1 for item in results if _score_success(item.get("selected", {})))
    track_success = sum(1 for item in results if _score_success(item.get("track", {})))
    lines.extend([
        "",
        "## 요약",
        "",
        f"- track 통과: {track_success}/{len(results)}.",
        f"- selected 통과: {selected_success}/{len(results)}.",
        "",
        "## guarded reason counts",
        "",
    ])
    for result in results:
        lines.append(f"- `{result.get('name', '')}`: {_fmt_counts(result.get('guarded_reason_counts', {}))}.")
    lines.extend([
        "",
        "## guarded debug stats",
        "",
    ])
    for result in results:
        lines.append(f"- `{result.get('name', '')}`: {_fmt_guarded_debug_stats(result.get('guarded_debug_stats', {}))}.")
    lines.extend([
        "",
        "## rescue 사용 샘플",
        "",
    ])
    for result in results:
        sample = result.get("rescue_used_sample", []) or []
        if sample:
            lines.append(f"- `{result.get('name', '')}`: {sample}.")
    return "\n".join(lines) + "\n"


def _allowed_selector_rescue(row: Mapping[str, object]) -> Point | None:
    record = row.get("selector_shadow")
    if not isinstance(record, Mapping):
        return None
    if not bool(record.get("available", False)):
        return None
    if bool(record.get("consensus_rescue_allowed", False)):
        consensus = _point(record.get("consensus_rescue_point"))
        if consensus is not None:
            return consensus
    if not bool(record.get("rescue_allowed", False)):
        return None
    return _point(record.get("rescue_point"))


def _guarded_debug_from_row(row: Mapping[str, object]) -> Mapping[str, object] | None:
    live_family = row.get("live_family")
    if not isinstance(live_family, Mapping):
        return None
    debug = live_family.get("debug")
    if not isinstance(debug, Mapping):
        return None
    guarded = debug.get("guarded_decal_identity")
    if isinstance(guarded, Mapping):
        return guarded
    return None


def _guarded_reason_from_debug(guarded: Mapping[str, object]) -> str:
    reason = str(guarded.get("reason") or "")
    if not reason and bool(guarded.get("accepted", False)):
        reason = "accepted"
    return reason


def _import_cv2_np():
    import cv2
    import numpy as np

    return cv2, np


def _score_success(score: object) -> bool:
    return isinstance(score, Mapping) and bool(score.get("success", False))


def _fmt_score(score: object) -> str:
    if not isinstance(score, Mapping) or not score.get("n"):
        return "평가 불가"
    return (
        f"{float(score['mean']):.1f}px "
        f"({'성공' if score.get('success') else '실패'})"
    )


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="16개 빨간점 GT에서 selector shadow live 선택을 재생 채점합니다.")
    parser.add_argument("names", nargs="*")
    parser.add_argument("--out", default="03_output/2026-06-26_selector_shadow_gt_replay_score_v1.md")
    parser.add_argument("--success-px", type=float, default=40.0)
    parser.add_argument("--no-local-box", action="store_true")
    parser.add_argument("--live-max-candidates", type=int, default=8)
    parser.add_argument("--guarded-decal-identity", action="store_true")
    parser.add_argument("--guarded-min-background-frames", type=int, default=3)
    parser.add_argument("--guarded-match-distance-px", type=float, default=10.0)
    parser.add_argument("--guarded-shape-pct", type=float, default=6.0)
    parser.add_argument("--guarded-max-step-px", type=float, default=80.0)
    args = parser.parse_args(argv)

    results = score_all_gt_clips(
        names=args.names or None,
        success_px=args.success_px,
        include_local_box=not args.no_local_box,
        live_max_candidates=args.live_max_candidates,
        enable_guarded_decal_identity=args.guarded_decal_identity,
        guarded_decal_min_background_frames=args.guarded_min_background_frames,
        guarded_decal_match_distance_px=args.guarded_match_distance_px,
        guarded_decal_shape_pct=args.guarded_shape_pct,
        guarded_decal_max_step_px=args.guarded_max_step_px,
    )
    text = markdown_report(results)
    print(text)
    out = ROOT / args.out
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    except PermissionError as exc:
        print(f"[write-skip] {exc}")
    print(json.dumps(results, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
