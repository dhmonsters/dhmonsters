# 배경 회전 구조 진단(035137) — 가설: 큰 회전체의 호이고 중심이 5x5 창 밖에 있음.
# 측정 1: 데칼 trail 누적 시각화(직선이냐 호냐) | 2: 프레임간 ID 유지율(RANSAC outlier 위험)
# 3: 각 장기 트랙에 원 fitting → 중심들이 공통점에 수렴하면 큰 회전체 확정.
import cv2, sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
ROOT = os.path.dirname(os.path.abspath(__file__))


def fit_circle(pts):
    """대수적 원 fitting — x²+y²+ax+by+c=0 최소제곱. 반환 (cx,cy,r,잔차RMS)."""
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
    # 잔차 RMS
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) - r
    rms = float(np.sqrt(np.mean(d ** 2)))
    return cx, cy, r, rms


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
    H, W = frs[0].shape[:2]
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frs]
    # ByteTracker로 ID 부여 — trail 추적
    bt = ByteTracker(); lockd = False; wp = None
    trails = {}             # tid → [(fi, x, y), ...]
    prev_tids = set(); ret_cnts = []   # ID 유지율
    for i, gray in enumerate(grays):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        if lockd and big and wc:
            tg = next((t for t in bt._tracks if t.tid == bt._tid), None)
            if tg and (wc[0] - tg.x) ** 2 + (wc[1] - tg.y) ** 2 <= 1225:
                bt.nudge(wc[0], wc[1])
        bt.update(gray, dets)
        if not lockd:
            if wc and wp and (wc[0] - wp[0]) ** 2 + (wc[1] - wp[1]) ** 2 <= 225:
                bt.lock(wc[0], wc[1]); lockd = True
            if wc:
                wp = wc
        cur_tids = {t.tid for t in bt._tracks if t.miss == 0}
        for t in bt._tracks:
            if t.miss == 0:
                trails.setdefault(t.tid, []).append((i, float(t.x), float(t.y)))
        if prev_tids:
            kept = len(prev_tids & cur_tids) / max(1, len(prev_tids))
            ret_cnts.append(kept)
        prev_tids = cur_tids

    # ── 측정 2: ID 유지율 ──
    print(f"\n=== {name} (총 {len(frs)}프레임, det {W}x{H}) ===")
    print(f"측정2 — 프레임간 ID 유지율: 평균 {np.mean(ret_cnts)*100:.1f}% "
          f"(<80%면 ID교체로 H추정 오염 위험)")

    # ── 측정 3: 장기(≥10프레임) 데칼 트랙에 원 fitting ──
    print(f"\n측정3 — 장기(≥10f) 데칼 트랙 원 fitting:")
    fits = []
    for tid, pts in trails.items():
        if tid == bt._tid or len(pts) < 10:
            continue
        # 트랙이 거의 정지(스팬<20px)면 회전 호 아님 → 스킵
        xs = [p[1] for p in pts]; ys = [p[2] for p in pts]
        span = math.hypot(max(xs)-min(xs), max(ys)-min(ys))
        if span < 20:
            continue
        f = fit_circle([(p[1], p[2]) for p in pts])
        if f is None:
            continue
        cx, cy, r, rms = f
        fits.append((tid, len(pts), span, cx, cy, r, rms))
    fits.sort(key=lambda x: -x[1])
    print(f"  분석 가능 트랙 {len(fits)}개:")
    for tid, n, span, cx, cy, r, rms in fits[:10]:
        outside = "★창밖" if (cx < 0 or cx > W or cy < 0 or cy > H) else "창안"
        print(f"    tid{tid:3d} {n}f span{span:3.0f}px → 중심({cx:6.0f},{cy:6.0f})"
              f"=R{r:5.0f} rms{rms:4.1f} {outside}")
    # 공통 중심 수렴?
    if len(fits) >= 3:
        cxs = np.array([f[3] for f in fits])
        cys = np.array([f[4] for f in fits])
        # 트랙 길이 가중 평균
        ws = np.array([f[1] for f in fits], dtype=float)
        mx = float(np.average(cxs, weights=ws)); my = float(np.average(cys, weights=ws))
        sx = float(np.sqrt(np.average((cxs-mx)**2, weights=ws)))
        sy = float(np.sqrt(np.average((cys-my)**2, weights=ws)))
        print(f"  중심 분포: 평균({mx:.0f},{my:.0f}) σ=({sx:.0f},{sy:.0f})  "
              f"창크기({W},{H})  ratio σ/창={sx/W:.2f},{sy/H:.2f}")
        if sx / W < 0.3 and sy / H < 0.3:
            print(f"  >>> ★ 중심이 한 점에 수렴(σ작음) — 큰 회전체 확정")
        else:
            print(f"  >>> 중심 산포 큼 — 단일 회전체 가설 약함")

    # ── 측정 1: trail 시각화 ──
    canvas = np.full((H, W, 3), 30, dtype=np.uint8)
    rng = np.random.RandomState(42)
    for tid, pts in trails.items():
        if len(pts) < 5:
            continue
        col = tuple(int(c) for c in rng.randint(60, 256, 3))
        pp = np.array([(int(p[1]), int(p[2])) for p in pts], dtype=np.int32)
        for j in range(1, len(pp)):
            cv2.line(canvas, tuple(pp[j-1]), tuple(pp[j]), col, 1, cv2.LINE_AA)
        cv2.circle(canvas, tuple(pp[-1]), 2, col, -1)
    # 타겟 trail 강조
    if bt._tid is not None and bt._tid in trails:
        pp = np.array([(int(p[1]), int(p[2])) for p in trails[bt._tid]], dtype=np.int32)
        for j in range(1, len(pp)):
            cv2.line(canvas, tuple(pp[j-1]), tuple(pp[j]), (0, 0, 255), 2, cv2.LINE_AA)
    out = os.path.join(ROOT, f"_bg_trails_{name}.png")
    cv2.imwrite(out, canvas)
    print(f"\n측정1 — trail 시각화: {out}  (빨간=타겟, 색별=데칼 ID)")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "000_0615_035137")
