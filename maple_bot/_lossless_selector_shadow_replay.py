# 무손실 녹화에서 selector_shadow를 오프라인 재생하고 커서 GT로 채점합니다.
from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path
from statistics import median
from typing import Mapping, Sequence

import cv2
import numpy as np

from core.vision.transparent_family_selector_runtime import TransparentFamilySelectorRuntime
from core.vision.transparent_selector_shadow import TransparentSelectorShadow


ROOT = Path(__file__).resolve().parent
LOSSLESS_NAMES = ("000_0621_165634", "000_0621_180636")
CURSOR_EXCLUDES = {
    "000_0621_165634": ((0, 3), (36, 42)),
    "000_0621_180636": ((97, 107),),
}
TRACK_ANCHOR_FAMILY = "panel_default_center_mild_state_mild"
RAW_RANK_FAMILY_PREFIX = f"{TRACK_ANCHOR_FAMILY}_raw_rank"
RAW_CONTINUITY_FAMILY_PREFIX = f"{TRACK_ANCHOR_FAMILY}_raw_cont"


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


def cursor_center(bgr) -> Point | None:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([140, 60, 60]), np.array([175, 255, 255]))
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


def is_cursor_excluded(name: str, frame_index: int) -> bool:
    return any(
        int(start) <= int(frame_index) <= int(end)
        for start, end in CURSOR_EXCLUDES.get(str(name), ())
    )


def lossless_valid_frames(
    name: str,
    gt_by_frame: Mapping[int, Point],
    *,
    frame_count: int,
    bad_frames: set[int] | None = None,
) -> list[int]:
    bad_frames = bad_frames or set()
    return [
        frame
        for frame in range(int(frame_count))
        if frame in gt_by_frame
        and frame not in bad_frames
        and not is_cursor_excluded(name, frame)
    ]


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
        "mean": float(np.mean(errors)),
        "median": float(median(errors)),
        "max": float(max(errors)),
        "success": float(np.mean(errors)) <= float(success_px),
        "worst": worst[:5],
    }


def _normalize_candidates(candidates: Sequence[Sequence[float]]) -> list[tuple[float, float, float, float, float]]:
    normalized = []
    for candidate in candidates:
        if len(candidate) < 2:
            continue
        score = float(candidate[2]) if len(candidate) >= 3 else 0.0
        width = float(candidate[3]) if len(candidate) >= 4 else 24.0
        height = float(candidate[4]) if len(candidate) >= 5 else 24.0
        normalized.append((float(candidate[0]), float(candidate[1]), score, width, height))
    return normalized


def raw_candidate_anchor_paths(
    rows: Sequence[Mapping[str, object]],
    *,
    max_rank_families: int = 3,
    max_continuity_families: int = 6,
    max_candidates_per_frame: int = 24,
    max_step_px: float = 85.0,
) -> dict[str, dict[int, Point]]:
    paths: dict[str, dict[int, Point]] = {
        f"{RAW_RANK_FAMILY_PREFIX}{rank}": {}
        for rank in range(max(0, int(max_rank_families)))
    }
    continuity_paths: dict[str, dict[int, Point]] = {}
    last_points: dict[str, Point] = {}

    for frame, row in enumerate(rows):
        candidates = _normalize_candidates(row.get("cands", []))
        candidates.sort(key=lambda candidate: candidate[2], reverse=True)
        candidates = candidates[: max(1, int(max_candidates_per_frame))]
        points = [(candidate[0], candidate[1]) for candidate in candidates]
        if not points:
            continue

        for rank, point in enumerate(points[: max(0, int(max_rank_families))]):
            paths[f"{RAW_RANK_FAMILY_PREFIX}{rank}"][frame] = point

        if not last_points:
            for index, point in enumerate(points[: max(0, int(max_continuity_families))]):
                family = f"{RAW_CONTINUITY_FAMILY_PREFIX}{index}"
                continuity_paths[family] = {frame: point}
                last_points[family] = point
            continue

        used: set[int] = set()
        for family in sorted(last_points):
            previous = last_points[family]
            best_index = None
            best_error = float("inf")
            for index, point in enumerate(points):
                if index in used:
                    continue
                error = _dist(previous, point)
                if error < best_error:
                    best_index = index
                    best_error = error
            if best_index is None or best_error > float(max_step_px):
                continue
            used.add(best_index)
            point = points[best_index]
            continuity_paths.setdefault(family, {})[frame] = point
            last_points[family] = point

    paths.update(continuity_paths)
    return {
        family: path
        for family, path in paths.items()
        if path
    }


def replay_shadow_path_from_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    runtime=None,
    clip_id: str = "lossless",
    window: int = 24,
    min_frames: int = 8,
    max_candidates: int = 24,
    include_local_box: bool = True,
    include_raw_candidate_anchors: bool = False,
    raw_rank_families: int = 3,
    raw_continuity_families: int = 6,
) -> tuple[dict[int, Point], dict[int, dict]]:
    runtime = runtime or TransparentFamilySelectorRuntime()
    raw_paths = (
        raw_candidate_anchor_paths(
            rows,
            max_rank_families=raw_rank_families,
            max_continuity_families=raw_continuity_families,
            max_candidates_per_frame=max_candidates,
        )
        if include_raw_candidate_anchors
        else {}
    )
    shadow = TransparentSelectorShadow(
        runtime,
        clip_id=clip_id,
        window=window,
        min_frames=min_frames,
        emit_every=1,
        max_candidates=max_candidates,
        include_local_box=include_local_box,
    )
    path: dict[int, Point] = {}
    records: dict[int, dict] = {}
    for frame, row in enumerate(rows):
        track = _point(row.get("track"))
        anchors = {}
        if track is not None:
            anchors[TRACK_ANCHOR_FAMILY] = track
        engine = row.get("engine")
        if isinstance(engine, Mapping):
            engine_track = _point(engine.get("track"))
            if engine_track is not None:
                anchors["phase_catalog_center_mild_state_mild"] = engine_track
        if include_raw_candidate_anchors:
            for family, raw_path in raw_paths.items():
                point = raw_path.get(frame)
                if point is not None:
                    anchors[family] = point
        if not anchors:
            continue
        record = shadow.update(
            frame,
            candidates=_normalize_candidates(row.get("cands", [])),
            anchors=anchors,
        )
        if not record or not record.get("available"):
            continue
        point = _point(record.get("point"))
        if point is None:
            continue
        path[frame] = point
        records[frame] = dict(record)
    return path, records


def load_lossless_clip(name: str, *, root: Path = ROOT) -> dict:
    base = root / "_record_debug" / name
    png_paths = sorted(glob.glob(str(base) + "_png/*.png"))
    frames = [cv2.imread(path) for path in png_paths]
    rows = [json.loads(line) for line in (base.with_suffix(".jsonl")).read_text(encoding="utf-8").splitlines()]
    count = min(len(frames), len(rows))
    frames = frames[:count]
    rows = rows[:count]
    shapes = [None if frame is None else frame.shape[:2] for frame in frames]
    base_shape = next((shape for shape in shapes if shape is not None), None)
    bad_frames = {
        frame
        for frame, shape in enumerate(shapes)
        if shape != base_shape
    }
    gt_by_frame = {
        frame: center
        for frame, image in enumerate(frames)
        for center in [None if image is None else cursor_center(image)]
        if center is not None
    }
    return {
        "name": name,
        "png_frames": len(frames),
        "jsonl_rows": len(rows),
        "rows": rows,
        "bad_frames": bad_frames,
        "bad_frame_names": [
            Path(png_paths[frame]).name
            for frame in sorted(bad_frames)
            if frame < len(png_paths)
        ],
        "gt_by_frame": gt_by_frame,
    }


def raw_candidate_oracle_path(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    frames: Sequence[int],
) -> dict[int, Point]:
    path = {}
    for frame in frames:
        gt = gt_by_frame.get(frame)
        if gt is None:
            continue
        candidates = _normalize_candidates(rows[frame].get("cands", []))
        if not candidates:
            continue
        best = min(candidates, key=lambda candidate: _dist((candidate[0], candidate[1]), gt))
        path[frame] = (best[0], best[1])
    return path


def track_path_from_rows(rows: Sequence[Mapping[str, object]]) -> dict[int, Point]:
    return {
        frame: point
        for frame, row in enumerate(rows)
        for point in [_point(row.get("track"))]
        if point is not None
    }


def score_lossless_clip(name: str, *, runtime=None, root: Path = ROOT) -> dict:
    clip = load_lossless_clip(name, root=root)
    frames = lossless_valid_frames(
        name,
        clip["gt_by_frame"],
        frame_count=min(clip["png_frames"], clip["jsonl_rows"]),
        bad_frames=set(clip["bad_frames"]),
    )
    shadow_path, shadow_records = replay_shadow_path_from_rows(
        clip["rows"],
        runtime=runtime,
        clip_id=name,
    )
    track_path = track_path_from_rows(clip["rows"])
    oracle_path = raw_candidate_oracle_path(clip["rows"], clip["gt_by_frame"], frames)
    return {
        "name": name,
        "png_frames": clip["png_frames"],
        "jsonl_rows": clip["jsonl_rows"],
        "bad_frames": clip["bad_frame_names"],
        "cursor_gt_frames": len(clip["gt_by_frame"]) - len(clip["bad_frames"]),
        "scored_frames": len(frames),
        "shadow_records": len(shadow_records),
        "track": score_path(track_path, clip["gt_by_frame"], frames),
        "shadow": score_path(shadow_path, clip["gt_by_frame"], frames),
        "oracle": score_path(oracle_path, clip["gt_by_frame"], frames),
    }


def _fmt_score(score: Mapping[str, object]) -> str:
    if not score.get("n"):
        return "평가 불가"
    return (
        f"mean {float(score['mean']):.1f}px, "
        f"median {float(score['median']):.1f}px, "
        f"max {float(score['max']):.1f}px, "
        f"n {int(score['n'])}, "
        f"{'성공' if score.get('success') else '실패'}"
    )


def markdown_report(results: Sequence[Mapping[str, object]]) -> str:
    lines = [
        "# 무손실 selector shadow replay v1 결과",
        "",
        "기존 무손실 JSONL의 `cands`와 `track`을 입력으로 `selector_shadow`를 오프라인 재생했다.",
        "",
        "| 클립 | 이상 프레임 | 채점 프레임 | raw 후보 oracle | 기존 track | shadow replay |",
        "|---|---|---:|---|---|---|",
    ]
    for result in results:
        bad = ", ".join(result["bad_frames"]) if result["bad_frames"] else "없음"
        lines.append(
            f"| `{result['name']}` | {bad} | {result['scored_frames']} | "
            f"{_fmt_score(result['oracle'])} | {_fmt_score(result['track'])} | "
            f"{_fmt_score(result['shadow'])} |"
        )
    lines.extend([
        "",
        "## 해석",
        "",
        "- raw 후보 oracle은 후보 안에 정답이 있는지 보는 상한선이다.",
        "- shadow replay는 기존 `track`을 anchor로 삼는 1차 검증이다.",
        "- 이 결과가 기존 track보다 나쁘면 selector 문제가 아니라 anchor family 생성이 부족하다는 뜻이다.",
    ])
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="무손실 2판에서 selector_shadow replay를 채점합니다.")
    parser.add_argument("--out", default="03_output/2026-06-26_lossless_selector_shadow_replay_score_v1.md")
    args = parser.parse_args(argv)

    runtime = TransparentFamilySelectorRuntime()
    results = [score_lossless_clip(name, runtime=runtime) for name in LOSSLESS_NAMES]
    text = markdown_report(results)
    print(text)
    try:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
    except PermissionError as exc:
        print(f"[write-skip] {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
