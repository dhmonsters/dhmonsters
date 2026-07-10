# 원본 영상과 현재 Python 렌더러의 같은 프레임 상태를 측정하고 비교 이미지를 만든다.
from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageStat


APP = Path(__file__).resolve().parents[1]
OUT = APP / "03_output"
FRAME_DIR = OUT / "2026-07-10_ffmpeg_frames_v1"
CANVAS_BOX = (238, 6, 632, 270)

sys.path.insert(0, str(APP))
from scene_renderer import render_scene_rows  # noqa: E402


SAMPLES = (
    ("star_start", "frame_012.png", "별", 0),
    ("star_34", "frame_013.png", "별", 34),
    ("star_110", "frame_015.png", "별", 110),
    ("star_300", "frame_020.png", "별", 300),
    ("circle_stopped", "frame_025.png", "원", 325),
    ("circle_27", "frame_026.png", "원", 27),
    ("circle_141", "frame_029.png", "원", 141),
    ("circle_293", "frame_033.png", "원", 293),
)

VIDEO_FRAME_VALUES = {
    "frame_012.png": 0,
    "frame_013.png": 34,
    "frame_014.png": 72,
    "frame_015.png": 110,
    "frame_016.png": 148,
    "frame_017.png": 186,
    "frame_018.png": 224,
    "frame_019.png": 262,
    "frame_020.png": 300,
    "frame_021.png": 325,
    "frame_025.png": 325,
    "frame_026.png": 27,
    "frame_027.png": 65,
    "frame_028.png": 103,
    "frame_029.png": 141,
    "frame_030.png": 175,
    "frame_031.png": 213,
    "frame_032.png": 255,
    "frame_033.png": 293,
    "frame_034.png": 325,
    "frame_035.png": 21,
}


def rows_to_image(rows: list[str]) -> Image.Image:
    height = len(rows)
    values = [row.strip("{}").split() for row in rows]
    width = len(values[0])
    image = Image.new("RGB", (width, height))
    image.putdata(
        [tuple(int(value[index:index + 2], 16) for index in (1, 3, 5)) for row in values for value in row]
    )
    return image


def video_canvas(name: str) -> Image.Image:
    with Image.open(FRAME_DIR / name) as image:
        return image.convert("RGB").crop(CANVAS_BOX)


def render_current(shape: str, frame: int) -> Image.Image:
    return rows_to_image(render_scene_rows(394, 264, shape, frame, 0, 0))


def target_bbox(image: Image.Image) -> dict[str, float | list[int]] | None:
    array = np.asarray(image, dtype=np.int16)
    channel_spread = array.max(axis=2) - array.min(axis=2)
    mask = (array[:, :, 0] > 155) & (array[:, :, 1] > 150) & (array[:, :, 2] > 125) & (channel_spread < 58)
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    candidates: list[list[tuple[int, int]]] = []
    for start_y, start_x in zip(*np.nonzero(mask)):
        if visited[start_y, start_x]:
            continue
        queue = deque([(int(start_x), int(start_y))])
        visited[start_y, start_x] = True
        component: list[tuple[int, int]] = []
        while queue:
            x, y = queue.popleft()
            component.append((x, y))
            for next_y in range(max(0, y - 1), min(height, y + 2)):
                for next_x in range(max(0, x - 1), min(width, x + 2)):
                    if mask[next_y, next_x] and not visited[next_y, next_x]:
                        visited[next_y, next_x] = True
                        queue.append((next_x, next_y))
        component_xs = [point[0] for point in component]
        component_ys = [point[1] for point in component]
        component_width = max(component_xs) - min(component_xs) + 1
        component_height = max(component_ys) - min(component_ys) + 1
        touches_border = min(component_xs) <= 2 or max(component_xs) >= width - 3 or min(component_ys) <= 2 or max(component_ys) >= height - 3
        if not touches_border and component_width <= 100 and component_height <= 100:
            candidates.append(component)
    largest = max(candidates, key=len, default=[])
    if len(largest) < 24:
        return None
    xs = np.asarray([point[0] for point in largest])
    ys = np.asarray([point[1] for point in largest])
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return {
        "bbox": [x0, y0, x1 + 1, y1 + 1],
        "center": [round(float(xs.mean()), 2), round(float(ys.mean()), 2)],
        "width": x1 - x0 + 1,
        "height": y1 - y0 + 1,
        "neutral_bright_pixels": int(len(xs)),
    }


def phase_shift(first: Image.Image, second: Image.Image) -> dict[str, float]:
    a = np.asarray(first.convert("L"), dtype=np.float64)[10:-10, 10:-10]
    b = np.asarray(second.convert("L"), dtype=np.float64)[10:-10, 10:-10]
    a -= a.mean()
    b -= b.mean()
    window = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    fa = np.fft.fft2(a * window)
    fb = np.fft.fft2(b * window)
    cross = fa * np.conj(fb)
    cross /= np.maximum(np.abs(cross), 1e-9)
    corr = np.abs(np.fft.ifft2(cross))
    y, x = np.unravel_index(np.argmax(corr), corr.shape)
    if x > corr.shape[1] // 2:
        x -= corr.shape[1]
    if y > corr.shape[0] // 2:
        y -= corr.shape[0]
    return {"x": int(x), "y": int(y), "peak": round(float(corr.max()), 5)}


def image_metrics(image: Image.Image) -> dict[str, float]:
    gray = image.convert("L")
    data = np.asarray(gray, dtype=np.float64)
    edge = (np.abs(np.diff(data, axis=0)).mean() + np.abs(np.diff(data, axis=1)).mean()) / 2
    stat = ImageStat.Stat(gray)
    return {
        "gray_mean": round(stat.mean[0], 3),
        "gray_stddev": round(stat.stddev[0], 3),
        "edge_mean": round(float(edge), 3),
    }


def labeled(image: Image.Image, title: str) -> Image.Image:
    tile = Image.new("RGB", (image.width, image.height + 24), "white")
    tile.paste(image, (0, 24))
    ImageDraw.Draw(tile).text((6, 6), title, fill="black")
    return tile


def make_comparison(sample_images: list[tuple[str, Image.Image, Image.Image]]) -> Image.Image:
    rows = []
    for label, video, current in sample_images:
        left = labeled(video, f"{label} | video")
        right = labeled(current, f"{label} | current Python")
        row = Image.new("RGB", (left.width + right.width, left.height), "white")
        row.paste(left, (0, 0))
        row.paste(right, (left.width, 0))
        rows.append(row)
    sheet = Image.new("RGB", (rows[0].width, sum(row.height for row in rows)), "white")
    y = 0
    for row in rows:
        sheet.paste(row, (0, y))
        y += row.height
    return sheet


def main() -> None:
    output_samples = []
    sample_metrics = {}
    for label, frame_name, shape, frame in SAMPLES:
        video = video_canvas(frame_name)
        current = render_current(shape, frame)
        output_samples.append((label, video, current))
        sample_metrics[label] = {
            "video": image_metrics(video),
            "current": image_metrics(current),
            "video_target": target_bbox(video),
            "current_target": target_bbox(current),
        }

    star_names = [f"frame_{index:03d}.png" for index in range(13, 21)]
    circle_names = [f"frame_{index:03d}.png" for index in range(26, 34)]
    motion = {}
    for group_name, names in (("star_play", star_names), ("circle_play", circle_names)):
        rows = []
        for first_name, second_name in zip(names, names[1:]):
            rows.append(
                {
                    "from_video_frame": first_name,
                    "to_video_frame": second_name,
                    "from_ui_frame": VIDEO_FRAME_VALUES[first_name],
                    "to_ui_frame": VIDEO_FRAME_VALUES[second_name],
                    "phase_shift": phase_shift(video_canvas(first_name), video_canvas(second_name)),
                }
            )
        motion[group_name] = rows

    target_frames = [
        "frame_012.png", "frame_013.png", "frame_014.png", "frame_015.png",
        "frame_026.png", "frame_027.png", "frame_028.png", "frame_035.png",
    ]
    target_timeline = {
        name: {"ui_frame": VIDEO_FRAME_VALUES[name], "target": target_bbox(video_canvas(name))}
        for name in target_frames
    }

    sheet_path = OUT / "2026-07-11_video_vs_current_same_frame_v3.png"
    json_path = OUT / "2026-07-11_video_vs_current_same_frame_metrics_v3.json"
    make_comparison(output_samples).save(sheet_path)
    json_path.write_text(
        json.dumps(
            {
                "canvas_box": CANVAS_BOX,
                "samples": sample_metrics,
                "video_motion": motion,
                "video_target_timeline": target_timeline,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(sheet_path)
    print(json_path)
    print(json.dumps({"video_motion": motion, "video_target_timeline": target_timeline}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
