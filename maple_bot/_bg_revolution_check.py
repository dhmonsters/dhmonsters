# 배경 운동 모델 판별 — 회전(공통중심·다른반지름) vs 원형평행이동(다른중심·같은반지름) 구분
# 핵심: 데칼들의 원 fitting 반지름이 뭉치면 '빙글빙글=원형 평행이동', 중심이 뭉치면 '단일축 회전'
# 추가: 프레임별 데칼 변위벡터(자기평균 대비)의 방향 일치도 = 단일 전역 offset(t) 존재 여부
import cv2, sys, os, json, math, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
from _bg_rotation_probe import fit_circle
ROOT = os.path.dirname(os.path.abspath(__file__))


def extract_trails(name):
    mp4 = os.path.join(ROOT, '_record_debug', name + '.mp4')
    jl = mp4[:-4] + '.jsonl'
    if not (os.path.exists(mp4) and os.path.exists(jl)):
        return None, None, None
    rows = [json.loads(l) for l in open(jl, encoding='utf-8')]
    cap = cv2.VideoCapture(mp4); frs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frs.append(f)
    cap.release()
    if not frs:
        return None, None, None
    H, W = frs[0].shape[:2]
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frs]
    bt = ByteTracker(); lockd = False; wp = None
    trails = {}
    for i, gray in enumerate(grays):
        r = rows[i] if i < len(rows) else {'cands': []}
        dets = [(c[0], c[1], c[2]) for c in r.get('cands', []) if c[2] >= 0.1]
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
        for t in bt._tracks:
            if t.miss == 0:
                trails.setdefault(t.tid, []).append((i, float(t.x), float(t.y)))
    return trails, (W, H), bt._tid


def phase_alignment(trails, tid_target, nframes):
    """프레임별 각 데칼 변위(자기평균 대비)의 방향 일치도(원형 표준편차, 도). 작을수록 단일 전역 offset."""
    # 장기 데칼만
    long_ids = [tid for tid, p in trails.items()
                if tid != tid_target and len(p) >= 15
                and math.hypot(max(x for _, x, _ in p) - min(x for _, x, _ in p),
                               max(y for _, _, y in p) - min(y for _, _, y in p)) >= 40]
    if len(long_ids) < 3:
        return None
    means = {tid: (np.mean([x for _, x, _ in trails[tid]]),
                   np.mean([y for _, _, y in trails[tid]])) for tid in long_ids}
    pos = {tid: {fi: (x, y) for fi, x, y in trails[tid]} for tid in long_ids}
    spreads = []
    for fi in range(nframes):
        angs = []
        for tid in long_ids:
            if fi in pos[tid]:
                dx = pos[tid][fi][0] - means[tid][0]
                dy = pos[tid][fi][1] - means[tid][1]
                if dx * dx + dy * dy >= 25:  # 변위 5px+ 만
                    angs.append(math.atan2(dy, dx))
        if len(angs) >= 3:
            c = np.mean([math.cos(a) for a in angs]); s = np.mean([math.sin(a) for a in angs])
            R = math.hypot(c, s)  # 1=완전일치 0=무작위
            circ_std = math.degrees(math.sqrt(-2 * math.log(max(R, 1e-9))))
            spreads.append(circ_std)
    return (float(np.median(spreads)), len(long_ids)) if spreads else None


def run(name):
    trails, wh, tid_t = extract_trails(name)
    if trails is None:
        print(f"{name:22s}  (녹화 없음/빈 파일)")
        return
    W, H = wh
    fits = []
    for tid, pts in trails.items():
        if tid == tid_t or len(pts) < 15:
            continue
        xs = [p[1] for p in pts]; ys = [p[2] for p in pts]
        span = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        if span < 40:
            continue
        f = fit_circle([(p[1], p[2]) for p in pts])
        if f is None:
            continue
        cx, cy, r, rms = f
        if r > 2000:  # 사실상 직선(반지름 무한) 제외
            continue
        fits.append((r, cx, cy, rms))
    if len(fits) < 3:
        print(f"{name:22s}  분석트랙<3 (데이터 부족)")
        return
    radii = np.array([f[0] for f in fits])
    cxs = np.array([f[1] for f in fits]); cys = np.array([f[2] for f in fits])
    rms = np.array([f[3] for f in fits])
    r_med = float(np.median(radii)); r_std = float(np.std(radii))
    r_cv = r_std / max(r_med, 1e-6)
    csx = float(np.std(cxs)); csy = float(np.std(cys))
    center_ratio = (csx / W + csy / H) / 2
    ph = phase_alignment(trails, tid_t, max(p[-1][0] for p in trails.values()) + 1)
    ph_s = f"{ph[0]:5.1f}° (n={ph[1]})" if ph else "  n/a"
    # 판정
    radius_tight = r_cv < 0.25
    center_tight = center_ratio < 0.25
    verdict = ("원형평행이동" if radius_tight and not center_tight else
               "단일축회전" if center_tight and not radius_tight else
               "혼합/불명")
    print(f"{name:22s} 트랙{len(fits):2d}  R중앙{r_med:5.1f} Rcv{r_cv:.2f}  "
          f"중심σ비{center_ratio:.2f}  rms중앙{np.median(rms):4.1f}  "
          f"위상일치{ph_s}  → {verdict}")


if __name__ == "__main__":
    names = sys.argv[1:]
    if not names:
        names = sorted(os.path.basename(p)[:-4]
                       for p in glob.glob(os.path.join(ROOT, '_record_debug', '*.mp4')))
    print(f"{'영상':22s} {'트랙':>4s}  {'R중앙':>6s} {'Rcv':>4s}  {'중심σ비':>5s}  "
          f"{'rms':>4s}  {'위상일치(작을수록전역평행)':>12s}")
    print("-" * 110)
    for n in names:
        try:
            run(n)
        except Exception as e:
            print(f"{n:22s}  ERROR {type(e).__name__}: {e}")
