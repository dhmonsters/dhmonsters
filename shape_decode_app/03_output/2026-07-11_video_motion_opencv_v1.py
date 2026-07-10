# 원본 영상의 캔버스가 자전하는지 평행 원운동하는지 OpenCV 특징점으로 측정한다.
from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np


APP = Path(__file__).resolve().parents[1]
OUT = APP / "03_output"
VIDEO = Path(r"C:\Users\PC\Downloads\녹화_2026_07_09_00_28_18_662_trim.mp4")
CANVAS = (238, 6, 394, 264)
SEGMENTS = {
    "star_play": (11.15, 20.55),
    "circle_play": (24.45, 33.35),
}


def crop_gray(frame: np.ndarray) -> np.ndarray:
    x, y, width, height = CANVAS
    crop = frame[y + 8:y + height - 8, x + 8:x + width - 8]
    return cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)


def robust_step(previous: np.ndarray, current: np.ndarray) -> dict[str, float] | None:
    points = cv2.goodFeaturesToTrack(
        previous,
        maxCorners=650,
        qualityLevel=0.012,
        minDistance=4,
        blockSize=5,
    )
    if points is None or len(points) < 20:
        return None
    tracked, status, error = cv2.calcOpticalFlowPyrLK(
        previous,
        current,
        points,
        None,
        winSize=(21, 21),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 25, 0.01),
    )
    valid = status.reshape(-1) == 1
    source = points.reshape(-1, 2)[valid]
    target = tracked.reshape(-1, 2)[valid]
    errors = error.reshape(-1)[valid]
    keep = errors < np.percentile(errors, 82)
    source = source[keep]
    target = target[keep]
    if len(source) < 18:
        return None

    matrix, inliers = cv2.estimateAffinePartial2D(
        source,
        target,
        method=cv2.RANSAC,
        ransacReprojThreshold=1.6,
        maxIters=1500,
        confidence=0.995,
        refineIters=10,
    )
    if matrix is None or inliers is None:
        return None
    selected = inliers.reshape(-1) == 1
    displacement = target[selected] - source[selected]
    if len(displacement) < 10:
        return None
    dx, dy = np.median(displacement, axis=0)
    angle = math.degrees(math.atan2(matrix[1, 0], matrix[0, 0]))
    scale = math.hypot(matrix[0, 0], matrix[1, 0])
    return {
        "dx": float(dx),
        "dy": float(dy),
        "angle_deg": float(angle),
        "scale": float(scale),
        "tracked": int(len(source)),
        "inliers": int(selected.sum()),
    }


def analyze_segment(capture: cv2.VideoCapture, fps: float, start: float, end: float) -> dict[str, object]:
    capture.set(cv2.CAP_PROP_POS_MSEC, start * 1000)
    previous = None
    path = [[0.0, 0.0]]
    steps = []
    frame_index = round(start * fps)
    final_index = round(end * fps)
    while frame_index <= final_index:
        ok, frame = capture.read()
        if not ok:
            break
        current = crop_gray(frame)
        if previous is not None:
            step = robust_step(previous, current)
            if step is not None:
                path.append([path[-1][0] + step["dx"], path[-1][1] + step["dy"]])
                step["video_frame"] = frame_index
                step["time_seconds"] = frame_index / fps
                steps.append(step)
            else:
                path.append(path[-1].copy())
        previous = current
        frame_index += 1

    angles = np.asarray([row["angle_deg"] for row in steps], dtype=np.float64)
    scales = np.asarray([row["scale"] for row in steps], dtype=np.float64)
    inlier_ratios = np.asarray([row["inliers"] / row["tracked"] for row in steps], dtype=np.float64)
    path_array = np.asarray(path, dtype=np.float64)
    step_lengths = np.linalg.norm(np.diff(path_array, axis=0), axis=1)
    moving_indices = np.flatnonzero(step_lengths > 0.2)
    moving_path = path_array[moving_indices[0]:] if len(moving_indices) else path_array
    orbit_center = (moving_path.min(axis=0) + moving_path.max(axis=0)) / 2
    orbit_radius = np.maximum((moving_path.max(axis=0) - moving_path.min(axis=0)) / 2, 1e-6)
    orbit_angles = np.unwrap(
        np.arctan2(
            (moving_path[:, 1] - orbit_center[1]) / orbit_radius[1],
            (moving_path[:, 0] - orbit_center[0]) / orbit_radius[0],
        )
    )
    orbit_turns = float((orbit_angles[-1] - orbit_angles[0]) / (2 * math.pi))
    return {
        "start_seconds": start,
        "end_seconds": end,
        "analyzed_steps": len(steps),
        "path": [[round(x, 4), round(y, 4)] for x, y in path],
        "summary": {
            "total_translation": [round(path[-1][0], 3), round(path[-1][1], 3)],
            "path_width": round(max(x for x, _ in path) - min(x for x, _ in path), 3),
            "path_height": round(max(y for _, y in path) - min(y for _, y in path), 3),
            "estimated_orbit_turns": round(abs(orbit_turns), 3),
            "screen_direction": "clockwise" if orbit_turns > 0 else "counterclockwise",
            "median_abs_rotation_per_video_frame_deg": round(float(np.median(np.abs(angles))), 6),
            "p95_abs_rotation_per_video_frame_deg": round(float(np.percentile(np.abs(angles), 95)), 6),
            "median_scale": round(float(np.median(scales)), 7),
            "median_inlier_ratio": round(float(np.median(inlier_ratios)), 4),
        },
    }


def draw_paths(results: dict[str, dict[str, object]], output: Path) -> None:
    image = np.full((520, 900, 3), 248, dtype=np.uint8)
    colors = {"star_play": (32, 111, 235), "circle_play": (33, 164, 92)}
    all_points = [point for result in results.values() for point in result["path"]]
    xs = [point[0] for point in all_points]
    ys = [point[1] for point in all_points]
    margin = 70
    scale_x = (image.shape[1] - margin * 2) / max(1.0, max(xs) - min(xs))
    scale_y = (image.shape[0] - margin * 2) / max(1.0, max(ys) - min(ys))
    scale = min(scale_x, scale_y)

    def convert(point: list[float]) -> tuple[int, int]:
        x = margin + (point[0] - min(xs)) * scale
        y = margin + (point[1] - min(ys)) * scale
        return round(x), round(image.shape[0] - y)

    cv2.putText(image, "Reference video background motion trace", (28, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (25, 25, 25), 2)
    for row, (name, result) in enumerate(results.items()):
        points = np.asarray([convert(point) for point in result["path"]], dtype=np.int32)
        cv2.polylines(image, [points], False, colors[name], 2, cv2.LINE_AA)
        cv2.circle(image, tuple(points[0]), 7, colors[name], -1, cv2.LINE_AA)
        cv2.circle(image, tuple(points[-1]), 7, (30, 30, 30), 2, cv2.LINE_AA)
        label = f"{name}: start=filled, end=ring"
        cv2.putText(image, label, (28, 70 + row * 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, colors[name], 2)
    cv2.imwrite(str(output), image)


def main() -> None:
    capture = cv2.VideoCapture(str(VIDEO))
    if not capture.isOpened():
        raise RuntimeError(f"영상을 열 수 없습니다. {VIDEO}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    results = {
        name: analyze_segment(capture, fps, start, end)
        for name, (start, end) in SEGMENTS.items()
    }
    capture.release()

    payload = {
        "video": {
            "path": str(VIDEO),
            "fps": fps,
            "frame_count": frame_count,
            "duration_seconds": frame_count / fps,
            "size": [width, height],
            "canvas": list(CANVAS),
        },
        "segments": results,
    }
    json_path = OUT / "2026-07-11_reference_video_motion_opencv_v2.json"
    png_path = OUT / "2026-07-11_reference_video_motion_trace_v2.png"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    draw_paths(results, png_path)
    print(json_path)
    print(png_path)
    print(json.dumps({name: result["summary"] for name, result in results.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
