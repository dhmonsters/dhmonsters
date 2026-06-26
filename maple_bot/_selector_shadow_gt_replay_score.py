# selector shadow rescue를 16개 빨간점 GT 녹화에서 라이브 방식으로 재생해 채점합니다.
from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path
from statistics import median
from typing import Mapping, Sequence

from core.vision.transparent_track_health import TransparentTrackHealthSelector


ROOT = Path(__file__).resolve().parent
Point = tuple[float, float]


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
) -> dict:
    from _selector_shadow_backfill import _load_jsonl, backfill_selector_shadow_rows
    from core.vision.transparent_family_selector_runtime import TransparentFamilySelectorRuntime

    source = root / "_record_debug" / f"{name}.jsonl"
    rows = _load_jsonl(source)
    backfilled = backfill_selector_shadow_rows(
        rows,
        runtime=runtime or TransparentFamilySelectorRuntime(),
        clip_id=name,
        window=24,
        min_frames=8,
        shadow_min_frames=1,
        emit_every=1,
        max_candidates=8,
        live_max_candidates=8,
        include_local_box=include_local_box,
        merge_context_frames=6,
        merge_min_size=175.0,
        merge_size_ratio=1.30,
    )
    gt = load_red_gt(name, root=root, min_frame=min_gt_frame)
    frames = [frame for frame in sorted(gt) if frame < len(backfilled)]
    frame_shape = frame_shape_from_mp4(name, root=root)

    track_path = track_path_from_rows(backfilled)
    shadow_path = shadow_point_path_from_rows(backfilled)
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
        "rescue_allowed_frames": len(rescue_path),
        "rescue_used_frames": len(rescue_used),
        "rescue_used_sample": rescue_used[:10],
        "track": score_path(track_path, gt, frames, success_px=success_px),
        "shadow": score_path(shadow_path, gt, frames, success_px=success_px),
        "rescue_allowed": score_path(rescue_path, gt, frames, success_px=success_px),
        "selected": score_path(selected_path, gt, frames, success_px=success_px),
    }


def score_all_gt_clips(
    *,
    root: Path = ROOT,
    names: Sequence[str] | None = None,
    success_px: float = 40.0,
    include_local_box: bool = True,
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
        )
        for name in names
    ]


def markdown_report(results: Sequence[Mapping[str, object]]) -> str:
    lines = [
        "# selector shadow GT 리플레이 채점 결과",
        "",
        "현재 라이브와 같은 구조로 selector shadow rescue를 건강 선택기에 넣어 16개 빨간점 GT를 재생했다.",
        "",
        "| 클립 | GT | track | shadow | allowed rescue | selected | allowed/used |",
        "|---|---:|---|---|---|---|---:|",
    ]
    for result in results:
        lines.append(
            "| `{name}` | {gt} | {track} | {shadow} | {allowed} | {selected} | {allowed_count}/{used_count} |".format(
                name=result.get("name", ""),
                gt=result.get("scored_frames", 0),
                track=_fmt_score(result.get("track", {})),
                shadow=_fmt_score(result.get("shadow", {})),
                allowed=_fmt_score(result.get("rescue_allowed", {})),
                selected=_fmt_score(result.get("selected", {})),
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
    if not bool(record.get("rescue_allowed", False)):
        return None
    return _point(record.get("rescue_point"))


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


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="16개 빨간점 GT에서 selector shadow live 선택을 재생 채점합니다.")
    parser.add_argument("names", nargs="*")
    parser.add_argument("--out", default="03_output/2026-06-26_selector_shadow_gt_replay_score_v1.md")
    parser.add_argument("--success-px", type=float, default=40.0)
    parser.add_argument("--no-local-box", action="store_true")
    args = parser.parse_args(argv)

    results = score_all_gt_clips(
        names=args.names or None,
        success_px=args.success_px,
        include_local_box=not args.no_local_box,
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
