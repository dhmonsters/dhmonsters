# 투명도형 퍼즐 첫 실패 프레임의 선택 후보와 oracle 후보 feature를 덤프한다.
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Mapping, Sequence

from _background_identity_signal import load_expected_background_with_ids
from _fast_gt_score import ROOT, gt_clip_names, load_jsonl_rows, score_path
from _selector_shadow_gt_replay_score import load_red_gt
from _temporal_candidate_features import box_internal_point, candidate_feature_row
from _temporal_identity_selector import TemporalIdentityConfig, frames_from_jsonl_rows, select_temporal_identity


Point = tuple[float, float]
Candidate = tuple[float, float, float, float, float]


def feature_dump_rows(
    *,
    root: Path = ROOT,
    names: Sequence[str] | None = None,
    failure_threshold: float = 40.0,
    min_gt_frame: int = 50,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in (list(names) if names is not None else gt_clip_names(root=root)):
        json_rows = load_jsonl_rows(root / "_record_debug" / f"{name}.jsonl")
        gt_by_frame = load_red_gt(str(name), root=root, min_frame=min_gt_frame)
        expected_background, _meta = load_expected_background_with_ids(
            str(name),
            range(max(0, int(min_gt_frame)), len(json_rows)),
        )
        frames, anchor = frames_from_jsonl_rows(
            json_rows,
            expected_background_by_frame=expected_background,
        )
        frame_by_index = {int(frame.frame_index): frame for frame in frames}
        result = select_temporal_identity(frames, anchor=anchor, config=TemporalIdentityConfig())
        if score_path(result.path, gt_by_frame)["success"]:
            continue
        bad_frame = _first_bad_frame(result.path, gt_by_frame, threshold=failure_threshold)
        if bad_frame is None or bad_frame not in frame_by_index:
            continue
        frame = frame_by_index[bad_frame]
        gt = gt_by_frame.get(bad_frame)
        selected_index = result.candidate_indices.get(bad_frame)
        raw_center_index = _nearest_center_index(frame.candidates, gt)
        raw_box_index = _nearest_box_index(frame.candidates, gt)
        role_indices = (
            ("selected", selected_index),
            ("raw_center", raw_center_index),
            ("raw_box", raw_box_index),
        )
        seen: set[tuple[str, int | None]] = set()
        for role, candidate_index in role_indices:
            key = (role, candidate_index)
            if key in seen:
                continue
            seen.add(key)
            candidate = frame.candidates[candidate_index] if candidate_index is not None else None
            rows.append(
                candidate_feature_row(
                    str(name),
                    frame_index=bad_frame,
                    role=role,
                    candidate_index=candidate_index,
                    candidate=candidate,
                    gt=gt,
                    selected_index=selected_index,
                    raw_center_index=raw_center_index,
                    raw_box_index=raw_box_index,
                    extra=_extra_features(frame, candidate_index),
                )
            )
    return rows


def markdown_report(rows: Sequence[Mapping[str, object]]) -> str:
    lines = [
        "# Task49 첫 실패 후보 feature dump",
        "",
        "| clip | frame | role | idx | selected | raw center | raw box | gt dist | score | support | bg id | bg pen | merge |",
        "|---|---:|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| `{clip}` | {frame} | {role} | {idx} | {selected} | {raw_center} | {raw_box} | {gt_dist} | {score} | {support} | {bg_id} | {bg_pen} | {merge} |".format(
                clip=row.get("clip", ""),
                frame=row.get("frame", ""),
                role=row.get("role", ""),
                idx=_fmt_any(row.get("candidate_index")),
                selected=_fmt_bool(row.get("is_selected")),
                raw_center=_fmt_bool(row.get("is_raw_center")),
                raw_box=_fmt_bool(row.get("is_raw_box")),
                gt_dist=_fmt_float(row.get("gt_dist")),
                score=_fmt_float(row.get("score")),
                support=_fmt_float(row.get("target_support")),
                bg_id=_fmt_any(row.get("background_id")),
                bg_pen=_fmt_float(row.get("background_penalty")),
                merge=_fmt_float(row.get("merge_likelihood")),
            )
        )
    lines.extend(
        [
            "",
            "## 해석",
            "",
            "이 표는 GT를 selector 입력으로 쓰지 않고, 실패 원인 분석용으로만 생성한다.",
            "",
            "selected가 raw center와 다르면 후보 선택 비용 문제다.",
            "",
            "raw center와 raw box가 다르면 후보 박스 내부 중심 복원 문제가 섞여 있다.",
        ]
    )
    return "\n".join(lines) + "\n"


def _extra_features(frame: object, candidate_index: int | None) -> dict[str, object]:
    if candidate_index is None:
        return {
            "target_support": None,
            "background_id": None,
            "background_penalty": None,
            "merge_likelihood": None,
        }
    return {
        "target_support": _sequence_value(frame.target_supports, candidate_index),
        "background_id": frame.background_ids[candidate_index] if candidate_index < len(frame.background_ids) else None,
        "background_penalty": _sequence_value(frame.background_penalties, candidate_index),
        "merge_likelihood": _sequence_value(frame.merge_likelihoods, candidate_index),
    }


def _first_bad_frame(
    path: Mapping[int, Point],
    gt_by_frame: Mapping[int, Point],
    *,
    threshold: float,
) -> int | None:
    for frame in sorted(int(frame) for frame in gt_by_frame):
        point = path.get(frame)
        if point is None:
            return frame
        gt = gt_by_frame[frame]
        if _dist(point, gt) > float(threshold):
            return frame
    return None


def _nearest_center_index(candidates: Sequence[Candidate], gt: Point | None) -> int | None:
    if gt is None or not candidates:
        return None
    return min(range(len(candidates)), key=lambda index: _dist((candidates[index][0], candidates[index][1]), gt))


def _nearest_box_index(candidates: Sequence[Candidate], gt: Point | None) -> int | None:
    if gt is None or not candidates:
        return None
    return min(range(len(candidates)), key=lambda index: _dist(box_internal_point(gt, candidates[index]), gt))


def _sequence_value(values: Sequence[float], index: int) -> float | None:
    return float(values[index]) if index < len(values) else None


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _fmt_float(value: object) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if not math.isfinite(number):
        return "-"
    return f"{number:.2f}"


def _fmt_bool(value: object) -> str:
    return "Y" if bool(value) else ""


def _fmt_any(value: object) -> str:
    return "-" if value is None else str(value)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="첫 실패 프레임 후보 feature를 덤프합니다.")
    parser.add_argument("names", nargs="*")
    parser.add_argument("--out", default="03_output/2026-06-27_task49_candidate_feature_dump_v1.md")
    args = parser.parse_args(argv)

    rows = feature_dump_rows(names=args.names or None)
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
