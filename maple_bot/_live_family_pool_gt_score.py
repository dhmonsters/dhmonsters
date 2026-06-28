# 라이브 후보 가족이 GT 구간을 끝까지 덮을 수 있는지 빠르게 채점합니다.
from __future__ import annotations

import argparse
import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from _selector_shadow_backfill import _load_jsonl
from _selector_shadow_gt_replay_score import load_red_gt
from core.vision.transparent_live_family_pool import TransparentLiveFamilyPool


ROOT = Path(__file__).resolve().parent
Point = tuple[float, float]
Candidate = tuple[float, float, float, float, float]


def replay_live_family_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    family_pool: Any | None = None,
    live_max_candidates: int = 24,
) -> dict[str, dict[int, Point]]:
    pool = family_pool or TransparentLiveFamilyPool(
        window=24,
        min_frames=8,
        enable_bg_mht=False,
        enable_raw_mht=False,
        enable_phase_mht=False,
        enable_guarded_decal_identity=True,
    )
    paths: dict[str, dict[int, Point]] = {}
    seeded = False
    for index, row in enumerate(rows):
        frame_index = int(row.get("i", index) or index)
        primary = _point(row.get("track"))
        white_anchor = None
        live_candidates = _limit_candidates(_candidates(row.get("cands", [])), live_max_candidates)
        if not seeded and primary is not None:
            white_anchor = primary
            live_candidates = []
            seeded = True
        decision = pool.update(
            frame_index,
            candidates=live_candidates,
            white_anchor=white_anchor,
        )
        points = dict(decision.points)
        if primary is not None:
            points["panel_default_center_mild_state_mild"] = primary
        engine = _engine_track(row)
        if engine is not None:
            points["phase_catalog_center_mild_state_mild"] = engine
        for family, point in points.items():
            paths.setdefault(str(family), {})[index] = (float(point[0]), float(point[1]))
    return paths


def best_family_score(
    rows: Sequence[Mapping[str, object]],
    gt_by_frame: Mapping[int, Point],
    *,
    family_pool: Any | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    live_max_candidates: int = 24,
) -> dict[str, object]:
    frames = [frame for frame in sorted(gt_by_frame) if frame < len(rows)]
    paths = replay_live_family_rows(
        rows,
        family_pool=family_pool,
        live_max_candidates=live_max_candidates,
    )
    best: dict[str, object] | None = None
    for family, path in paths.items():
        score = _score_path(
            path,
            gt_by_frame,
            frames,
            success_px=success_px,
            min_coverage=min_coverage,
        )
        item = {
            "family": family,
            **score,
        }
        if best is None or _score_rank(item) > _score_rank(best):
            best = item
    if best is None:
        return {
            "family": "",
            "n": 0,
            "coverage": 0.0,
            "mean": float("inf"),
            "max": float("inf"),
            "success": False,
        }
    return best


def score_clip(
    name: str,
    *,
    root: Path = ROOT,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    min_gt_frame: int = 50,
    live_max_candidates: int = 24,
    family_pool: Any | None = None,
) -> dict[str, object]:
    rows = _load_jsonl(root / "_record_debug" / f"{name}.jsonl")
    gt = load_red_gt(name, root=root, min_frame=min_gt_frame)
    return {
        "name": name,
        "frames": len(rows),
        "gt_frames": len(gt),
        "best_family": best_family_score(
            rows,
            gt,
            success_px=success_px,
            min_coverage=min_coverage,
            live_max_candidates=live_max_candidates,
            family_pool=family_pool,
        ),
    }


def score_all(
    *,
    root: Path = ROOT,
    names: Sequence[str] | None = None,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    live_max_candidates: int = 24,
    fast_mode: bool = False,
) -> list[dict[str, object]]:
    if names is None:
        names = [
            path.name
            for path in sorted((root / "_gt_frames").iterdir())
            if path.is_dir()
        ]
    results = []
    for name in names:
        pool = _fast_family_pool() if fast_mode else None
        results.append(score_clip(
            str(name),
            root=root,
            success_px=success_px,
            min_coverage=min_coverage,
            live_max_candidates=live_max_candidates,
            family_pool=pool,
        ))
    return results


def _fast_family_pool() -> TransparentLiveFamilyPool:
    return TransparentLiveFamilyPool(
        window=16,
        min_frames=6,
        enable_phase_catalog=False,
        enable_bg_mht=False,
        enable_phase_mht=False,
        enable_raw_mht=False,
        enable_guarded_decal_identity=False,
        raw_rank_families=8,
        raw_continuity_families=8,
        raw_beam_families=4,
        raw_beam_spawn=4,
        raw_max_candidates_per_frame=16,
    )


def summarize(results: Sequence[Mapping[str, object]]) -> dict[str, object]:
    total = len(results)
    success = 0
    for result in results:
        score = result.get("best_family")
        if isinstance(score, Mapping) and bool(score.get("success", False)):
            success += 1
    return {"success": success, "total": total}


def _score_path(
    path: Mapping[int, Point],
    gt_by_frame: Mapping[int, Point],
    frames: Sequence[int],
    *,
    success_px: float,
    min_coverage: float,
) -> dict[str, object]:
    errors = []
    for frame in frames:
        point = path.get(int(frame))
        gt = gt_by_frame.get(int(frame))
        if point is None or gt is None:
            continue
        errors.append(math.hypot(point[0] - gt[0], point[1] - gt[1]))
    coverage = len(errors) / len(frames) if frames else 0.0
    if not errors:
        return {
            "n": 0,
            "coverage": coverage,
            "mean": float("inf"),
            "max": float("inf"),
            "success": False,
        }
    mean = sum(errors) / len(errors)
    return {
        "n": len(errors),
        "coverage": coverage,
        "mean": mean,
        "max": max(errors),
        "success": mean <= success_px and coverage >= min_coverage,
    }


def _score_rank(score: Mapping[str, object]) -> tuple[int, int, float, float]:
    return (
        int(bool(score.get("success", False))),
        int(float(score.get("coverage", 0.0) or 0.0) * 1000),
        -float(score.get("mean", float("inf"))),
        -float(score.get("max", float("inf"))),
    )


def _limit_candidates(candidates: Sequence[Candidate], limit: int) -> list[Candidate]:
    return sorted(candidates, key=lambda row: row[2], reverse=True)[: max(1, int(limit))]


def _engine_track(row: Mapping[str, object]) -> Point | None:
    engine = row.get("engine")
    if not isinstance(engine, Mapping):
        return None
    return _point(engine.get("track"))


def _candidates(value: object) -> list[Candidate]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    out = []
    for row in value:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) < 2:
            continue
        try:
            score = float(row[2]) if len(row) >= 3 else 0.0
            width = float(row[3]) if len(row) >= 4 else 24.0
            height = float(row[4]) if len(row) >= 5 else 24.0
            out.append((float(row[0]), float(row[1]), score, width, height))
        except (TypeError, ValueError):
            continue
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
    parser.add_argument("--fast-mode", action="store_true")
    parser.add_argument("--names", nargs="*")
    args = parser.parse_args()
    results = score_all(
        names=args.names,
        success_px=args.success_px,
        min_coverage=args.min_coverage,
        live_max_candidates=args.live_max_candidates,
        fast_mode=args.fast_mode,
    )
    print(json.dumps({"summary": summarize(results), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
