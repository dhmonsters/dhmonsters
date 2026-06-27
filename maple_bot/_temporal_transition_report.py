# 투명도형 퍼즐 시간축 실패 전환 리포트를 생성한다.
from __future__ import annotations

import math
from typing import Mapping, Sequence

from _temporal_identity_selector import TemporalFrame, TemporalIdentityResult


Point = tuple[float, float]


def first_failure_transition(
    path: Mapping[int, Point],
    gt_by_frame: Mapping[int, Point],
    *,
    fail_px: float = 40.0,
) -> int | None:
    was_good = False
    for frame in sorted(gt_by_frame):
        point = path.get(int(frame))
        if point is None:
            continue
        is_bad = _dist(point, gt_by_frame[int(frame)]) > float(fail_px)
        if is_bad and was_good:
            return int(frame)
        if not is_bad:
            was_good = True
    return None


def transition_window_rows(
    clip: str,
    frames: Sequence[TemporalFrame],
    result: TemporalIdentityResult,
    gt_by_frame: Mapping[int, Point],
    *,
    fail_px: float = 40.0,
    radius: int = 5,
) -> list[dict[str, object]]:
    transition = first_failure_transition(result.path, gt_by_frame, fail_px=fail_px)
    if transition is None:
        return []
    frame_by_index = {int(frame.frame_index): frame for frame in frames}
    start = int(transition) - int(radius)
    end = int(transition) + int(radius)
    rows = []
    for frame_index in sorted(frame for frame in gt_by_frame if start <= int(frame) <= end):
        point = result.path.get(int(frame_index))
        gt = gt_by_frame[int(frame_index)]
        candidate_index = result.candidate_indices.get(int(frame_index))
        frame = frame_by_index.get(int(frame_index))
        background_id = None
        if frame is not None and candidate_index is not None and 0 <= candidate_index < len(frame.background_ids):
            background_id = frame.background_ids[int(candidate_index)]
        rows.append(
            {
                "clip": str(clip),
                "frame": int(frame_index),
                "transition": int(frame_index) == int(transition),
                "state": result.states.get(int(frame_index)),
                "candidate_index": candidate_index,
                "background_id": background_id,
                "x": None if point is None else float(point[0]),
                "y": None if point is None else float(point[1]),
                "gt_x": float(gt[0]),
                "gt_y": float(gt[1]),
                "error": None if point is None else round(_dist(point, gt), 6),
            }
        )
    return rows


def markdown_report(rows: Sequence[Mapping[str, object]]) -> str:
    lines = [
        "# Task55 failure transition report",
        "",
        "| clip | frame | transition | state | cand | bg id | error |",
        "|---|---:|---|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| `{clip}` | {frame} | {transition} | {state} | {cand} | {bg} | {error} |".format(
                clip=row.get("clip", ""),
                frame=row.get("frame", ""),
                transition="yes" if row.get("transition") else "",
                state=row.get("state", ""),
                cand="-" if row.get("candidate_index") is None else row.get("candidate_index"),
                bg="-" if row.get("background_id") is None else row.get("background_id"),
                error="-" if row.get("error") is None else f"{float(row['error']):.1f}",
            )
        )
    return "\n".join(lines) + "\n"


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
