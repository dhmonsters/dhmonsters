# 투명도형 MHT solver를 녹화 후보와 GT 프레임으로 오프라인 채점합니다.
from __future__ import annotations

import csv
import io
import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from core.vision.transparent_mht_solver import MhtCandidate, MhtFrame, SolverConfig, solve_mht
import _panel_score_sweep as score_sweep
import _path_family_oracle as path_oracle
import _phase_catalog_score as phase_catalog
from _homography_track import violation


ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "03_output"
THR = 40.0
Point = Tuple[float, float]
RawCandidate = Tuple[float, float, float, float, float]


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _finite_box(candidate: RawCandidate) -> bool:
    return (
        math.isfinite(float(candidate[2]))
        and math.isfinite(float(candidate[3]))
        and float(candidate[2]) > 0.0
        and float(candidate[3]) > 0.0
    )


def candidate_from_tuple(
    candidate: RawCandidate,
    *,
    bg_center: Optional[Point] = None,
    motion_score: float = 0.0,
    viol_score: float = 0.0,
    bg_score: float = 0.0,
) -> MhtCandidate:
    cx, cy, w, h, score = candidate[:5]
    return MhtCandidate(
        float(cx),
        float(cy),
        float(score),
        float(w),
        float(h),
        bg_center=bg_center,
        motion_score=float(motion_score),
        viol_score=float(viol_score),
        bg_score=float(bg_score),
    )


def stable_prep_end_from_big_frames(
    big_frames: Sequence[int],
    *,
    min_run: int = 20,
    max_gap: int = 2,
) -> int:
    ordered = sorted(int(frame) for frame in big_frames)
    if not ordered:
        return 0

    run = [ordered[0]]
    for frame in ordered[1:]:
        if frame - run[-1] <= int(max_gap) + 1:
            run.append(frame)
            continue
        if len(run) >= int(min_run):
            break
        run = [frame]
    return run[-1] + 1 if len(run) >= int(min_run) else ordered[-1] + 1


def detect_stable_prep(frames_raw) -> Tuple[int, Dict[int, Point]]:
    white: Dict[int, Point] = {}
    big_frames = []
    for frame_i, frame in enumerate(frames_raw):
        wb = phase_catalog.acquire_white(frame)
        if wb is None:
            continue
        wc = (float(wb[0] + wb[2] / 2.0), float(wb[1] + wb[3] / 2.0))
        white[frame_i] = wc
        if wb[2] >= 50 and wb[3] >= 50:
            big_frames.append(frame_i)
    return stable_prep_end_from_big_frames(big_frames), white


def background_center(candidate: RawCandidate, expected: Sequence[RawCandidate]) -> Optional[Point]:
    if not expected:
        return None
    cx, cy = float(candidate[0]), float(candidate[1])
    best = min(expected, key=lambda item: _dist((cx, cy), (float(item[0]), float(item[1]))))
    distance = _dist((cx, cy), (float(best[0]), float(best[1])))
    gate = 18.0
    if _finite_box(candidate):
        gate = max(gate, 0.35 * max(float(candidate[2]), float(candidate[3])))
    if distance > gate:
        return None
    return (float(best[0]), float(best[1]))


def _candidate_scores(
    cands: Sequence[RawCandidate],
    expected: Sequence[RawCandidate],
    prev_dp,
    cur_dp,
    bx: float,
    by: float,
):
    viol_map = violation(prev_dp, cur_dp) if prev_dp is not None else {}
    motion_raw = []
    viol_raw = []
    det_raw = []
    for idx, cand in enumerate(cands):
        vx, vy = score_sweep.nearest_prev_motion(prev_dp, cand)
        motion_raw.append(math.hypot(vx - bx, vy - by))
        viol_raw.append(viol_map.get(idx, 0.0))
        det_raw.append(float(cand[4]))
    return (
        score_sweep.rank_to_ten(motion_raw),
        score_sweep.rank_to_ten(viol_raw),
        score_sweep.rank_to_ten(det_raw),
        [score_sweep.background_score(cand, expected) for cand in cands],
    )


def load_mht_frames(name: str) -> List[MhtFrame]:
    frames_raw = phase_catalog.load_frames(name)
    rows = phase_catalog.load_rows(name)
    wrows = phase_catalog.load_wrows(name)
    prep_end, white = phase_catalog.detect_prep(frames_raw)
    csets = phase_catalog.candidate_sets(rows, wrows, white)
    period, _period_score = phase_catalog.estimate_period_lag(csets, prep_end)
    grays = [cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) for frame in frames_raw]

    out: List[MhtFrame] = []
    prev_dp = None
    prev_gray = None
    for frame_i, cands in enumerate(csets):
        bx = by = 0.0
        if prev_gray is not None and frame_i < len(grays) and prev_gray.shape == grays[frame_i].shape:
            (bx, by), _ = cv2.phaseCorrelate(prev_gray, grays[frame_i])
        if frame_i < len(grays):
            prev_gray = grays[frame_i]

        cur_dp = np.asarray([[c[0], c[1]] for c in cands], dtype=float) if cands else np.empty((0, 2))
        if frame_i < prep_end:
            anchor = white.get(frame_i)
            out.append(MhtFrame(frame_i, [], anchor=anchor))
            prev_dp = cur_dp
            continue

        lag = phase_catalog.choose_local_lag(csets, frame_i, period, prep_end)
        expected = csets[frame_i - lag] if frame_i - lag >= 0 else []
        motion_scores, viol_scores, _det_scores, bg_scores = _candidate_scores(
            cands,
            expected,
            prev_dp,
            cur_dp,
            bx,
            by,
        )
        converted = [
            candidate_from_tuple(
                cand,
                bg_center=background_center(cand, expected),
                motion_score=motion_scores[idx],
                viol_score=viol_scores[idx],
                bg_score=bg_scores[idx],
            )
            for idx, cand in enumerate(cands)
        ]
        out.append(MhtFrame(frame_i, converted))
        prev_dp = cur_dp
    return out


def run_clip(name: str, config: Optional[SolverConfig] = None) -> Dict[int, Point]:
    return solve_mht(load_mht_frames(name), config=config)


def score_clip(name: str, config: Optional[SolverConfig] = None):
    gt = phase_catalog.load_gt(name)
    if not gt:
        return None
    path = run_clip(name, config=config)
    score = path_oracle.score_path(path, gt)
    score["name"] = name
    return score


def score_all(config: Optional[SolverConfig] = None):
    rows = []
    for name in phase_catalog.names_from_gt():
        row = score_clip(name, config=config)
        if row:
            rows.append(row)
    return rows


def summarize(rows):
    return {
        "success": sum(1 for row in rows if row["success"]),
        "total": len(rows),
        "mean": float(np.mean([row["mean"] for row in rows])) if rows else float("nan"),
    }


def csv_text(rows):
    fields = ["name", "mean", "max", "covered", "coverage", "success"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row[field] for field in fields})
    return buf.getvalue()


def markdown_text(rows):
    summary = summarize(rows)
    lines = [
        "# 2026-06-24 Transparent MHT Replay Score",
        "",
        f"- result: {summary['success']}/{summary['total']} success, mean error {summary['mean']:.1f}px.",
        f"- success threshold: mean error <= {THR:.0f}px and coverage >= 90%.",
        "",
        "| clip | mean | max | coverage | result |",
        "|---|---:|---:|---:|---|",
    ]
    for row in rows:
        status = "OK" if row["success"] else "FAIL"
        lines.append(
            f"| {row['name']} | {row['mean']:.1f}px | {row['max']:.1f}px | "
            f"{row['coverage'] * 100:.0f}% | {status} |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(rows):
    OUT_DIR.mkdir(exist_ok=True)
    version = 1
    while True:
        md_path = OUT_DIR / f"2026-06-24_transparent_mht_replay_score_v{version}.md"
        csv_path = OUT_DIR / f"2026-06-24_transparent_mht_replay_score_v{version}.csv"
        if not md_path.exists() and not csv_path.exists():
            break
        version += 1
    try:
        md_path.write_text(markdown_text(rows), encoding="utf-8")
        csv_path.write_text(csv_text(rows), encoding="utf-8")
    except PermissionError:
        return None, None
    return md_path, csv_path


def main():
    rows = score_all()
    summary = summarize(rows)
    print(f"transparent_mht: {summary['success']}/{summary['total']} mean={summary['mean']:.1f}px")
    for row in rows:
        print(f"{row['name']}: {row['mean']:.1f}px {'OK' if row['success'] else 'FAIL'}")
    md_path, csv_path = write_outputs(rows)
    if md_path and csv_path:
        print(f"saved: {md_path}")
        print(f"saved: {csv_path}")
    else:
        print("saved: skipped by current filesystem permission")
    print("\n=== CSV ===")
    print(csv_text(rows))


if __name__ == "__main__":
    main()
