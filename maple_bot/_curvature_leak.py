# 곡률 leak 신호 측정 — 동적 슬라이딩 윈도우 원 fitting.
# 측정A: N별 fitting RMS 분포(N 너무 작으면 무조건 적합·N 너무 크면 stale, 분리도 좋은 N 탐색)
# 측정B: 035137 f56~71에서 트랙(샌) RMS vs GT(진짜 타겟) RMS — leak 트리거 분리도.
import cv2, sys, os, json, math
import numpy as np
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
NS = [5, 8, 10, 15]


def fit_circle_rms(pts):
    """직전 N점 원 fitting — RMS만 반환(곡률 일관성 지표). 3점 미만 불가."""
    P = np.asarray(pts, dtype=np.float64)
    if len(P) < 3:
        return None
    x, y = P[:, 0], P[:, 1]
    A = np.column_stack([x, y, np.ones(len(P))])
    b = -(x ** 2 + y ** 2)
    try:
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    a_, b_, c_ = sol
    cx, cy = -a_ / 2, -b_ / 2
    r2 = (a_ / 2) ** 2 + (b_ / 2) ** 2 - c_
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r
    return float(np.sqrt(np.mean(d ** 2)))


def run(name):
    mp4 = os.path.join(ROOT, '_record_debug', name + '.mp4')
    rows = [json.loads(l) for l in open(mp4[:-4] + '.jsonl', encoding='utf-8')]
    cap = cv2.VideoCapture(mp4); frs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frs.append(f)
    cap.release()
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frs]
    gt = load_gt(name, min_f=0)

    bt = ByteTracker(); lockd = False; wp = None
    trail = defaultdict(list)         # tid → [(fi, x, y), ...]
    tgt_tid_per_fi = {}               # fi → 타겟 tid(샌 트랙 추적)
    rms_decal = defaultdict(list)     # N → 모든 비타겟 트랙 RMS 누적
    rms_tgt_track = defaultdict(list) # N → (fi, RMS) 타겟이 따라가는 트랙
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        if lockd and big and wc:
            tg = next((t for t in bt._tracks if t.tid == bt._tid), None)
            if tg and (wc[0] - tg.x) ** 2 + (wc[1] - tg.y) ** 2 <= 1225:
                bt.nudge(wc[0], wc[1])
        bt.update(grays[i], dets)
        if not lockd:
            if wc and wp and (wc[0] - wp[0]) ** 2 + (wc[1] - wp[1]) ** 2 <= 225:
                bt.lock(wc[0], wc[1]); lockd = True
            if wc:
                wp = wc
        tgt_tid_per_fi[i] = bt._tid
        for t in bt._tracks:
            if t.miss == 0:
                trail[t.tid].append((i, float(t.x), float(t.y)))
                for N in NS:
                    if len(trail[t.tid]) >= N:
                        pts = [(p[1], p[2]) for p in trail[t.tid][-N:]]
                        rms = fit_circle_rms(pts)
                        if rms is None:
                            continue
                        if t.tid == bt._tid:
                            rms_tgt_track[N].append((i, rms))
                        else:
                            rms_decal[N].append(rms)

    # 측정 A — N별 데칼 RMS 분포 안정성
    print(f"\n=== {name} === 측정A: N별 데칼 fitting RMS 분포 (안정 N 탐색)")
    print("  N  | 표본수 | 중앙값 |  p25 |  p75 |  p90 |  p95 | (낮을수록 호에 잘맞음)")
    for N in NS:
        a = np.array(rms_decal[N])
        if len(a) == 0:
            print(f"  {N:2d} | 표본 없음"); continue
        print(f"  {N:2d} | {len(a):5d} | {np.median(a):5.1f} | {np.percentile(a,25):4.1f} | "
              f"{np.percentile(a,75):4.1f} | {np.percentile(a,90):4.1f} | {np.percentile(a,95):4.1f}")

    # 측정 B — f56~71 트랙(샌) vs GT(진짜 타겟) 곡률 잔차
    print(f"\n측정B: 035137 GT 구간 — 트랙(샌) RMS vs GT(진짜) RMS")
    gt_seq = sorted(gt.items())   # [(fi, (x,y)), ...]
    print("  N  |          트랙(샌)             |          GT(진짜)             | 분리도")
    print("     | 중앙 평균 p25  p75  최소 최대 | 중앙 평균 p25  p75  최소 최대 | (GT 중앙 / 트랙 중앙)")
    for N in NS:
        # 트랙 RMS — GT 프레임에 해당하는 것만
        gt_fis = {fi for fi, _ in gt_seq}
        tr_in_gt = [r for fi, r in rms_tgt_track[N] if fi in gt_fis]
        # GT RMS — 직전 N개 GT 위치에 fitting
        gt_rms_list = []
        for k in range(N - 1, len(gt_seq)):
            window = gt_seq[k - N + 1:k + 1]
            # 연속 N프레임만(빠진 프레임 있으면 스킵)
            fis = [w[0] for w in window]
            if fis[-1] - fis[0] != N - 1:
                continue
            pts = [w[1] for w in window]
            rms = fit_circle_rms(pts)
            if rms is not None:
                gt_rms_list.append(rms)
        if not tr_in_gt or not gt_rms_list:
            print(f"  {N:2d} | 데이터 부족 (트랙{len(tr_in_gt)} GT{len(gt_rms_list)})")
            continue
        tr = np.array(tr_in_gt); g = np.array(gt_rms_list)
        ratio = np.median(g) / max(0.01, np.median(tr))
        print(f"  {N:2d} | {np.median(tr):4.1f} {np.mean(tr):4.1f} "
              f"{np.percentile(tr,25):4.1f} {np.percentile(tr,75):4.1f} "
              f"{tr.min():4.1f} {tr.max():4.1f} | "
              f"{np.median(g):4.1f} {np.mean(g):4.1f} "
              f"{np.percentile(g,25):4.1f} {np.percentile(g,75):4.1f} "
              f"{g.min():4.1f} {g.max():4.1f} | ratio {ratio:.2f}x "
              f"{'★분리' if ratio >= 2.0 else '약함' if ratio >= 1.3 else '무변별'}")

    # 측정 B 상세 — GT 프레임별 트랙 RMS와 GT RMS 나란히
    print(f"\n측정B 상세(N=8 추천 기본): f별 트랙 RMS vs GT RMS")
    N_show = 8
    tr_map = {fi: r for fi, r in rms_tgt_track[N_show]}
    gt_map = {}
    for k in range(N_show - 1, len(gt_seq)):
        window = gt_seq[k - N_show + 1:k + 1]
        fis = [w[0] for w in window]
        if fis[-1] - fis[0] != N_show - 1:
            continue
        pts = [w[1] for w in window]
        rms = fit_circle_rms(pts)
        if rms is not None:
            gt_map[window[-1][0]] = rms
    print("  f | 트랙RMS | GT RMS | 분리")
    for fi in sorted(set(tr_map) | set(gt_map)):
        if fi not in gt:
            continue
        tr = tr_map.get(fi); gm = gt_map.get(fi)
        mark = ""
        if tr is not None and gm is not None and gm >= 2 * tr:
            mark = "★"
        print(f"  {fi:3d} | {('%.1f' % tr) if tr is not None else '   - '} | "
              f"{('%.1f' % gm) if gm is not None else '   - '} {mark}")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "000_0615_035137")
