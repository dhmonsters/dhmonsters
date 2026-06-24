# phase-catalog 방식으로 투명 도형 퍼즐 GT를 오프라인 채점하는 스크립트
from __future__ import annotations

import csv
import glob
import io
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent
REC_DIR = ROOT / "_record_debug"
GT_DIR = ROOT / "_gt_frames"
THR = 40.0


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _area(c):
    if not (math.isfinite(c[2]) and math.isfinite(c[3]) and c[2] > 0 and c[3] > 0):
        return float("nan")
    return c[2] * c[3]


def _aspect(c):
    if not (math.isfinite(c[2]) and math.isfinite(c[3]) and c[2] > 0 and c[3] > 0):
        return float("nan")
    return c[2] / max(c[3], 1e-6)


def _pct_delta(a, b):
    if not (math.isfinite(a) and math.isfinite(b)):
        return 0.0
    return abs(a - b) / max((abs(a) + abs(b)) / 2.0, 1e-6) * 100.0


def _shape_ok(candidate, expected, area_tol_pct, aspect_tol_pct):
    area_delta = _pct_delta(_area(candidate), _area(expected))
    aspect_delta = _pct_delta(_aspect(candidate), _aspect(expected))
    return area_delta <= area_tol_pct and aspect_delta <= aspect_tol_pct


def _match_sets(reference, current, max_dist=120.0):
    pairs = []
    for ri, ref in enumerate(reference):
        for ci, cur in enumerate(current):
            d = _dist(ref, cur)
            if d <= max_dist:
                pairs.append((d, ri, ci))
    pairs.sort(key=lambda x: x[0])
    used_r = set()
    used_c = set()
    out = []
    for d, ri, ci in pairs:
        if ri in used_r or ci in used_c:
            continue
        used_r.add(ri)
        used_c.add(ci)
        out.append((d, reference[ri], current[ci]))
    return out


def _lag_score(csets, lag, start):
    scores = []
    for t in range(max(start, lag), len(csets)):
        pairs = _match_sets(csets[t - lag], csets[t])
        if len(pairs) < 2:
            continue
        vals = sorted(p[0] for p in pairs)
        keep = vals[: max(1, int(math.ceil(len(vals) * 0.75)))]
        scores.append(float(np.median(keep)))
    if not scores:
        return None
    return float(np.median(scores))


def estimate_period_lag(csets, prep_end, min_lag=None, max_lag=None):
    """준비 길이를 믿지 않고 후보 집합 반복 오차가 가장 작은 lag를 찾는다."""
    if not csets:
        return 0, float("inf")
    if min_lag is None:
        min_lag = max(2, prep_end - 24)
    if max_lag is None:
        max_lag = min(len(csets) - 1, prep_end + 24)
    best = None
    for lag in range(int(min_lag), int(max_lag) + 1):
        score = _lag_score(csets, lag, prep_end)
        if score is None:
            continue
        item = (score, lag)
        if best is None or item < best:
            best = item
    if best is None:
        return prep_end, float("inf")
    score, lag = best
    return lag, score


def explain_background(candidates, expected_background, pos_tol=10.0,
                       area_tol_pct=6.0, aspect_tol_pct=6.0):
    """현재 후보 중 phase-catalog 배경으로 설명되는 후보와 남는 후보를 나눈다."""
    pairs = []
    for ci, cand in enumerate(candidates):
        for ei, exp in enumerate(expected_background):
            d = _dist(cand, exp)
            if d > pos_tol:
                continue
            if not _shape_ok(cand, exp, area_tol_pct, aspect_tol_pct):
                continue
            pairs.append((d, ci, ei))
    pairs.sort(key=lambda x: x[0])
    used_c = set()
    used_e = set()
    explained = []
    for d, ci, ei in pairs:
        if ci in used_c or ei in used_e:
            continue
        used_c.add(ci)
        used_e.add(ei)
        explained.append((candidates[ci], expected_background[ei], d))
    unexplained = [c for i, c in enumerate(candidates) if i not in used_c]
    return explained, unexplained


def acquire_white(bgr, bright_thr=200, min_area=200, size_cap=60):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, bright_thr, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(cnt) < min_area:
        return None
    x, y, w, h = cv2.boundingRect(cnt)
    cx, cy = x + w / 2.0, y + h / 2.0
    w = min(w, size_cap)
    h = min(h, size_cap)
    return (float(cx - w / 2.0), float(cy - h / 2.0), float(w), float(h))


def stable_prep_end_from_big_frames(big_frames, min_run=20, max_gap=2):
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


def stable_prep_end_from_white_centers(
    centers,
    run_end,
    center_tol=30.0,
    min_seed=20,
):
    if len(centers) < int(min_seed):
        return int(run_end)
    seed = np.asarray([(x, y) for _, x, y in centers[: int(min_seed)]], dtype=float)
    base = np.median(seed, axis=0)
    last_stable = None
    for frame, x, y in centers:
        if math.hypot(float(x) - base[0], float(y) - base[1]) <= float(center_tol):
            last_stable = int(frame)
            continue
        if last_stable is not None and int(frame) > last_stable + 2:
            break
    if last_stable is None:
        return int(run_end)
    return min(int(run_end), last_stable + 1)


def red_mark(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    mask = (
        cv2.inRange(hsv, np.array([0, 120, 100]), np.array([8, 255, 255]))
        | cv2.inRange(hsv, np.array([174, 120, 100]), np.array([180, 255, 255]))
    )
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    cnt = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(cnt) < 8:
        return None
    mm = cv2.moments(cnt)
    if not mm["m00"]:
        return None
    return (mm["m10"] / mm["m00"], mm["m01"] / mm["m00"])


def load_gt(name, min_f=50):
    gt = {}
    for path in sorted((GT_DIR / name).glob("f*.png")):
        fi = int(path.stem[1:4])
        if fi < min_f:
            continue
        mark = red_mark(cv2.imread(str(path)))
        if mark:
            gt[fi] = mark
    return gt


def load_frames(name):
    cap = cv2.VideoCapture(str(REC_DIR / f"{name}.mp4"))
    frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    cap.release()
    return frames


def load_rows(name):
    return [json.loads(line) for line in open(REC_DIR / f"{name}.jsonl", encoding="utf-8")]


def load_wrows(name):
    path = REC_DIR / f"{name}.wjsonl"
    if not path.exists():
        return None
    return [json.loads(line) for line in open(path, encoding="utf-8")]


def detect_prep(frames):
    big_frames = []
    centers = []
    white = {}
    for i, frame in enumerate(frames):
        wb = acquire_white(frame)
        if wb is None:
            continue
        wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        white[i] = wc
        if wb[2] >= 50 and wb[3] >= 50:
            big_frames.append(i)
            centers.append((i, wc[0], wc[1]))
    run_end = stable_prep_end_from_big_frames(big_frames)
    return stable_prep_end_from_white_centers(centers, run_end), white


def candidate_sets(rows, wrows, white):
    csets = []
    for i, row in enumerate(rows):
        cands = []
        boxes = wrows[i] if wrows is not None and i < len(wrows) else []
        for c in row.get("cands", []):
            if float(c[2]) < 0.1:
                continue
            w = h = float("nan")
            if boxes:
                near = min(boxes, key=lambda b: (float(b[0]) - float(c[0])) ** 2
                           + (float(b[1]) - float(c[1])) ** 2)
                if math.hypot(float(near[0]) - float(c[0]), float(near[1]) - float(c[1])) <= 25.0:
                    w, h = float(near[2]), float(near[3])
            cands.append((float(c[0]), float(c[1]), w, h, float(c[2])))
        wc = white.get(i)
        if wc is not None:
            cands = [c for c in cands if _dist(c, wc) > 45.0]
        csets.append(cands)
    return csets


def choose_local_lag(csets, t, period, prep_end, search=8):
    lo = max(2, period - search)
    hi = min(t, period + search)
    best = None
    for lag in range(lo, hi + 1):
        if t - lag < 0:
            continue
        pairs = _match_sets(csets[t - lag], csets[t])
        if len(pairs) < 4:
            continue
        vals = sorted(p[0] for p in pairs)
        score = float(np.median(vals[: max(1, int(math.ceil(len(vals) * 0.75)))]))
        item = (score, lag)
        if best is None or item < best:
            best = item
    return best[1] if best else period


def choose_target(candidates, unexplained, pred, last, velocity):
    pool = unexplained if unexplained else candidates
    if not pool:
        return None
    if pred is None:
        anchor = last
    else:
        anchor = pred
    if anchor is None:
        return max(pool, key=lambda c: c[4])
    return min(pool, key=lambda c: _dist(c, anchor) - 0.02 * c[4])


def run_clip(name, pos_tol=10.0, area_tol_pct=6.0, aspect_tol_pct=6.0):
    frames = load_frames(name)
    rows = load_rows(name)
    wrows = load_wrows(name)
    prep_end, white = detect_prep(frames)
    csets = candidate_sets(rows, wrows, white)
    period, period_score = estimate_period_lag(csets, prep_end)

    out = {}
    last = None
    vx = vy = 0.0
    explained_counts = []
    unexplained_counts = []

    for i, cands in enumerate(csets):
        if i < prep_end:
            if i in white:
                last = white[i]
                out[i] = last
            continue
        lag = choose_local_lag(csets, i, period, prep_end)
        expected = csets[i - lag] if i - lag >= 0 else []
        explained, unexplained = explain_background(
            cands,
            expected,
            pos_tol=pos_tol,
            area_tol_pct=area_tol_pct,
            aspect_tol_pct=aspect_tol_pct,
        )
        explained_counts.append(len(explained))
        unexplained_counts.append(len(unexplained))
        pred = (last[0] + vx, last[1] + vy) if last is not None else None
        picked = choose_target(cands, unexplained, pred, last, (vx, vy))
        if picked is None:
            if pred is not None:
                last = pred
                vx *= 0.9
                vy *= 0.9
                out[i] = last
            continue
        cur = (picked[0], picked[1])
        if last is not None:
            vx = vx * 0.6 + (cur[0] - last[0]) * 0.4
            vy = vy * 0.6 + (cur[1] - last[1]) * 0.4
        last = cur
        out[i] = cur

    meta = {
        "prep_end": prep_end,
        "period": period,
        "period_delta": period - prep_end,
        "period_score": period_score,
        "explained_median": float(np.median(explained_counts)) if explained_counts else 0.0,
        "unexplained_median": float(np.median(unexplained_counts)) if unexplained_counts else 0.0,
    }
    return out, meta


def score_clip(name):
    gt = load_gt(name)
    if not gt:
        return None
    res, meta = run_clip(name)
    errs = [
        math.hypot(res[fi][0] - g[0], res[fi][1] - g[1])
        for fi, g in gt.items()
        if res.get(fi)
    ]
    if not errs:
        return None
    row = {
        "name": name,
        "gt_frames": len(gt),
        "covered": len(errs),
        "coverage": len(errs) / len(gt),
        "mean": float(np.mean(errs)),
        "max": float(np.max(errs)),
        "success": float(np.mean(errs)) <= THR and len(errs) / len(gt) >= 0.9,
    }
    row.update(meta)
    return row


def csv_text(rows):
    fields = [
        "name", "gt_frames", "covered", "coverage", "mean", "max", "success",
        "prep_end", "period", "period_delta", "period_score",
        "explained_median", "unexplained_median",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buf.getvalue()


def markdown_text(rows):
    ok = sum(1 for r in rows if r["success"])
    avg = float(np.mean([r["mean"] for r in rows])) if rows else float("nan")
    lines = [
        "# 2026-06-24 phase-catalog 오프라인 채점 결과",
        "",
        f"- 성공 기준: 평균오차 {THR:.0f}px 이하, 커버리지 90% 이상.",
        f"- 전체 결과: {ok}/{len(rows)} 성공, 평균오차 {avg:.1f}px.",
        "- 방식: 실제 반복 lag를 찾고, 같은 phase의 배경 후보로 설명되는 후보를 먼저 제거한다.",
        "",
        "| 클립 | 평균오차 | 최대오차 | 결과 | 준비끝 | period | 차이 | 배경설명 | 남음 |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        status = "성공" if row["success"] else "실패"
        lines.append(
            f"| {row['name']} | {row['mean']:.1f}px | {row['max']:.1f}px | {status} | "
            f"{row['prep_end']} | {row['period']} | {row['period_delta']} | "
            f"{row['explained_median']:.1f} | {row['unexplained_median']:.1f} |"
        )
    return "\n".join(lines) + "\n"


def names_from_gt():
    return sorted(path.name for path in GT_DIR.glob("*") if path.is_dir())


def main():
    names = sys.argv[1:] or names_from_gt()
    rows = []
    for name in names:
        row = score_clip(name)
        if row is None:
            print(f"{name}: skipped")
            continue
        rows.append(row)
        status = "OK" if row["success"] else "FAIL"
        print(
            f"{name}: mean={row['mean']:.1f}px max={row['max']:.1f}px "
            f"period={row['period']} delta={row['period_delta']} {status}"
        )
    print("\n=== CSV ===")
    print(csv_text(rows))
    print("=== MARKDOWN ===")
    print(markdown_text(rows))


if __name__ == "__main__":
    main()
