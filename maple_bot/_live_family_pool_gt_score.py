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
    include_occlusion_variants: bool = False,
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
    candidate_sets: Mapping[int, Sequence[Sequence[float]]] | None = None,
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
    if include_occlusion_variants:
        paths.update(occlusion_variant_paths(
            paths,
            frames=frames,
            expected_by_frame=expected_by_frame or {},
            candidate_sets=candidate_sets or candidate_sets_from_rows(rows),
        ))
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


def occlusion_variant_paths(
    paths: Mapping[str, Mapping[int, Point]],
    *,
    frames: Sequence[int],
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]],
    candidate_sets: Mapping[int, Sequence[Sequence[float]]],
) -> dict[str, dict[int, Point]]:
    variants: dict[str, dict[int, Point]] = {}
    normalized_candidates = {
        int(frame): _normalize_candidate_set(candidates)
        for frame, candidates in candidate_sets.items()
    }
    for family, path in paths.items():
        corrected = _correct_occlusion_path(
            dict(path),
            frames,
            expected_by_frame=expected_by_frame,
            candidate_sets=normalized_candidates,
        )
        if corrected:
            variants[f"{family}_occlusion_state"] = corrected
    return variants


def candidate_sets_from_rows(
    rows: Sequence[Mapping[str, object]],
) -> dict[int, list[Candidate]]:
    return {
        int(index): _candidates(row.get("cands", []))
        for index, row in enumerate(rows)
    }


def _correct_occlusion_path(
    observed_path: Mapping[int, Point],
    frames: Sequence[int],
    *,
    expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]],
    candidate_sets: Mapping[int, Sequence[Candidate]],
    enter_distance: float = 12.0,
    release_distance: float = 10.0,
    bg_pos_tol: float = 18.0,
    release_bg_pos_tol: float = 6.0,
    max_coast_frames: int = 5,
) -> dict[int, Point]:
    corrected: dict[int, Point] = {}
    previous: Point | None = None
    velocity: Point = (0.0, 0.0)
    coasting = False
    coast_count = 0

    for frame in frames:
        frame = int(frame)
        observed = observed_path.get(frame)
        if observed is None:
            if previous is None:
                continue
            predicted = _predict_point(previous, velocity)
            corrected[frame] = predicted
            previous = predicted
            coasting = True
            coast_count += 1
            continue

        observed = (float(observed[0]), float(observed[1]))
        if previous is None:
            corrected[frame] = observed
            previous = observed
            continue

        predicted = _predict_point(previous, velocity)
        expected = expected_by_frame.get(frame, [])
        candidates = candidate_sets.get(frame, [])

        if coasting:
            release = _best_occlusion_release(
                predicted,
                candidates,
                expected,
                release_distance=release_distance,
                release_bg_pos_tol=release_bg_pos_tol,
            )
            if release is not None:
                corrected[frame] = release
                velocity = _point_velocity(previous, release)
                previous = release
                coasting = False
                coast_count = 0
                continue
            if coast_count < int(max_coast_frames):
                corrected[frame] = predicted
                previous = predicted
                coast_count += 1
                continue

        if _matches_expected_background(observed, expected, pos_tol=bg_pos_tol) and _dist(observed, predicted) >= float(enter_distance):
            corrected[frame] = predicted
            previous = predicted
            coasting = True
            coast_count = 1
            continue

        corrected[frame] = observed
        velocity = _point_velocity(previous, observed)
        previous = observed
        coasting = False
        coast_count = 0

    return corrected


def _best_occlusion_release(
    predicted: Point,
    candidates: Sequence[Candidate],
    expected_background: Sequence[tuple[int, Sequence[float]]],
    *,
    release_distance: float,
    release_bg_pos_tol: float,
) -> Point | None:
    best: tuple[float, float, Point] | None = None
    for candidate in candidates:
        point = (float(candidate[0]), float(candidate[1]))
        if _matches_expected_background(point, expected_background, pos_tol=release_bg_pos_tol):
            continue
        distance = _dist(point, predicted)
        if distance > float(release_distance):
            continue
        item = (distance, -float(candidate[2]), point)
        if best is None or item < best:
            best = item
    return None if best is None else best[2]


def _matches_expected_background(
    point: Point,
    expected_background: Sequence[tuple[int, Sequence[float]]],
    *,
    pos_tol: float,
) -> bool:
    return any(
        _candidate_position_distance(point, expected) <= float(pos_tol)
        for _bg_id, expected in expected_background
    )


def _candidate_position_distance(point: Point, expected: Sequence[float]) -> float:
    if len(expected) < 4:
        return _dist(point, (float(expected[0]), float(expected[1])))
    half_w = float(expected[2]) / 2.0
    half_h = float(expected[3]) / 2.0
    dx = max(0.0, abs(float(point[0]) - float(expected[0])) - half_w)
    dy = max(0.0, abs(float(point[1]) - float(expected[1])) - half_h)
    return math.hypot(dx, dy)


def _predict_point(point: Point, velocity: Point) -> Point:
    return (float(point[0]) + float(velocity[0]), float(point[1]) + float(velocity[1]))


def _point_velocity(previous: Point, current: Point) -> Point:
    return (float(current[0]) - float(previous[0]), float(current[1]) - float(previous[1]))


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def score_clip(
    name: str,
    *,
    root: Path = ROOT,
    success_px: float = 40.0,
    min_coverage: float = 0.9,
    min_gt_frame: int = 50,
    live_max_candidates: int = 24,
    family_pool: Any | None = None,
    include_occlusion_variants: bool = False,
) -> dict[str, object]:
    rows = _load_jsonl(root / "_record_debug" / f"{name}.jsonl")
    gt = load_red_gt(name, root=root, min_frame=min_gt_frame)
    frames = [frame for frame in sorted(gt) if frame < len(rows)]
    expected_by_frame = (
        expected_background_for_clip(name, frames=frames)
        if include_occlusion_variants
        else {}
    )
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
            include_occlusion_variants=include_occlusion_variants,
            expected_by_frame=expected_by_frame,
            candidate_sets=candidate_sets_from_rows(rows) if include_occlusion_variants else None,
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
    include_occlusion_variants: bool = False,
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
            include_occlusion_variants=include_occlusion_variants,
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
        raw_rank_families=16,
        raw_continuity_families=16,
        raw_beam_families=6,
        raw_beam_spawn=6,
        raw_max_candidates_per_frame=24,
    )


def expected_background_for_clip(
    name: str,
    *,
    frames: Sequence[int],
) -> Mapping[int, Sequence[tuple[int, Sequence[float]]]]:
    try:
        from _background_identity_signal import load_expected_background_with_ids

        expected, _meta = load_expected_background_with_ids(str(name), list(frames))
        return expected
    except Exception:
        return {}


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


def _normalize_candidate_set(candidates: Sequence[Sequence[float]]) -> list[Candidate]:
    return [
        candidate
        for row in candidates
        for candidate in [_candidate(row)]
        if candidate is not None
    ]


def _candidate(row: Sequence[float]) -> Candidate | None:
    if len(row) < 2:
        return None
    try:
        score = float(row[2]) if len(row) >= 3 else 0.0
        width = float(row[3]) if len(row) >= 4 else 24.0
        height = float(row[4]) if len(row) >= 5 else 24.0
        return (float(row[0]), float(row[1]), score, width, height)
    except (TypeError, ValueError):
        return None


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
    parser.add_argument("--occlusion-variants", action="store_true")
    parser.add_argument("--names", nargs="*")
    args = parser.parse_args()
    results = score_all(
        names=args.names,
        success_px=args.success_px,
        min_coverage=args.min_coverage,
        live_max_candidates=args.live_max_candidates,
        fast_mode=args.fast_mode,
        include_occlusion_variants=args.occlusion_variants,
    )
    print(json.dumps({"summary": summarize(results), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
