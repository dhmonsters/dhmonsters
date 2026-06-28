# 라이브 temporal selector를 GT JSONL에 직접 재생해 채점합니다.
from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from _selector_shadow_backfill import _load_jsonl
from _selector_shadow_gt_replay_score import frame_shape_from_mp4, load_red_gt
from core.puzzle.live_temporal_selector import LiveTemporalDecision, LiveTemporalSelector


ROOT = Path(__file__).resolve().parent
Point = tuple[float, float]


def replay_live_temporal_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    selector: Any | None = None,
    frame_shape: Sequence[int] | None = None,
    live_max_candidates: int = 24,
    collect_decisions: bool = True,
) -> tuple[dict[int, Point], dict[int, dict[str, object]]]:
    live_selector = selector or LiveTemporalSelector(live_max_candidates=live_max_candidates)
    path: dict[int, Point] = {}
    decisions: dict[int, dict[str, object]] = {}
    seeded = False
    for index, row in enumerate(rows):
        frame_index = int(row.get("i", index) or index)
        primary = _point(row.get("track"))
        white_anchor = None
        if not seeded and primary is not None:
            white_anchor = primary
            seeded = True
        decision = live_selector.update(
            frame_index=frame_index,
            candidates=_candidates(row.get("cands", [])),
            primary_point=primary,
            white_anchor=white_anchor,
            engine_point=_engine_track(row),
            frame_shape=frame_shape,
        )
        if decision.point is not None:
            path[index] = decision.point
        if collect_decisions:
            decisions[index] = _decision_payload(decision)
        else:
            decisions[index] = {
                "selector_record": decision.selector_record is not None,
            }
    return path, decisions


def score_rows_against_gt(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    *,
    selector: Any | None = None,
    frame_shape: Sequence[int] | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    live_max_candidates: int = 24,
    collect_decisions: bool = True,
) -> dict[str, object]:
    path, decisions = replay_live_temporal_rows(
        rows,
        selector=selector,
        frame_shape=frame_shape,
        live_max_candidates=live_max_candidates,
        collect_decisions=collect_decisions,
    )
    frames = [frame for frame in sorted(gt_by_frame) if frame < len(rows)]
    return {
        "frames": len(rows),
        "gt_frames": len(gt_by_frame),
        "scored_frames": len(frames),
        "selected": _score_path(
            path,
            gt_by_frame,
            frames,
            success_px=success_px,
            min_coverage=min_coverage,
        ),
        "selector_records": sum(1 for item in decisions.values() if item.get("selector_record")),
        "decisions": decisions if collect_decisions else {},
    }


def score_gt_clip(
    name: str,
    *,
    root: Path = ROOT,
    min_gt_frame: int = 50,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    live_max_candidates: int = 24,
    collect_decisions: bool = True,
) -> dict[str, object]:
    rows = _load_jsonl(root / "_record_debug" / f"{name}.jsonl")
    result = score_rows_against_gt(
        rows,
        load_red_gt(name, root=root, min_frame=min_gt_frame),
        frame_shape=frame_shape_from_mp4(name, root=root),
        success_px=success_px,
        min_coverage=min_coverage,
        live_max_candidates=live_max_candidates,
        collect_decisions=collect_decisions,
    )
    return {"name": name, **result}


def score_all_gt_clips(
    *,
    root: Path = ROOT,
    names: Sequence[str] | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    live_max_candidates: int = 24,
    collect_decisions: bool = True,
) -> list[dict[str, object]]:
    if names is None:
        names = [
            path.name
            for path in sorted((root / "_gt_frames").iterdir())
            if path.is_dir()
        ]
    return [
        score_gt_clip(
            name,
            root=root,
            success_px=success_px,
            min_coverage=min_coverage,
            live_max_candidates=live_max_candidates,
            collect_decisions=collect_decisions,
        )
        for name in names
    ]


def summarize(results: Sequence[Mapping[str, object]]) -> dict[str, object]:
    selected = [item.get("selected", {}) for item in results]
    return {
        "success": sum(1 for item in selected if bool(item.get("success", False))),
        "total": len(results),
        "mean": sum(float(item.get("mean", 0.0) or 0.0) for item in selected) / max(1, len(selected)),
    }


def compact_results(results: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    compact = []
    for result in results:
        selected = result.get("selected", {})
        selected_map = selected if isinstance(selected, Mapping) else {}
        compact.append({
            "name": result.get("name", ""),
            "selected": {
                "success": bool(selected_map.get("success", False)),
                "mean": selected_map.get("mean"),
                "max": selected_map.get("max"),
                "coverage": selected_map.get("coverage"),
                "n": selected_map.get("n"),
            },
            "selector_records": result.get("selector_records", 0),
        })
    return compact


def _decision_payload(decision: LiveTemporalDecision) -> dict[str, object]:
    return {
        "point": decision.point,
        "source": decision.source,
        "reason": decision.reason,
        "family": decision.family,
        "selector_record": decision.selector_record,
    }


def _score_path(
    path: Mapping[int, Point],
    gt_by_frame: Mapping[int, Point],
    frames: Sequence[int],
    *,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
) -> dict[str, object]:
    errors = []
    for frame in frames:
        point = path.get(int(frame))
        gt = gt_by_frame.get(int(frame))
        if point is None or gt is None:
            continue
        errors.append(math.hypot(float(point[0]) - float(gt[0]), float(point[1]) - float(gt[1])))
    total = len(frames)
    coverage = float(len(errors)) / float(total) if total else 0.0
    if not errors:
        return {
            "n": 0,
            "coverage": coverage,
            "mean": float("inf"),
            "max": float("inf"),
            "success": False,
        }
    mean_error = float(sum(errors) / len(errors))
    return {
        "n": len(errors),
        "coverage": coverage,
        "mean": mean_error,
        "max": float(max(errors)),
        "success": mean_error <= float(success_px) and coverage >= float(min_coverage),
    }


def _engine_track(row: Mapping[str, object]) -> Point | None:
    engine = row.get("engine")
    if not isinstance(engine, Mapping):
        return None
    return _point(engine.get("track"))


def _candidates(value: object) -> list[tuple[float, float, float, float, float]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    out = []
    for row in value:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) < 2:
            continue
        score = float(row[2]) if len(row) >= 3 else 0.0
        width = float(row[3]) if len(row) >= 4 else 24.0
        height = float(row[4]) if len(row) >= 5 else 24.0
        out.append((float(row[0]), float(row[1]), score, width, height))
    return out


def _point(value: object) -> Point | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--success-px", type=float, default=40.0)
    parser.add_argument("--min-coverage", type=float, default=0.9)
    parser.add_argument("--live-max-candidates", type=int, default=24)
    parser.add_argument("--names", nargs="*")
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    results = score_all_gt_clips(
        names=args.names,
        success_px=args.success_px,
        min_coverage=args.min_coverage,
        live_max_candidates=args.live_max_candidates,
        collect_decisions=not args.summary_only,
    )
    payload = {
        "summary": summarize(results),
        "results": compact_results(results) if args.summary_only else results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
