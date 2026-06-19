# 국소 운동장 leak 신호 — 트랙 속도 vs 주변 K데칼 평균 속도의 정렬도(dot).
# 가설: 샌 트랙은 국소 데칼장과 정렬(dot>0, 데칼 따라감), 진짜 타겟은 역행(dot<0, 데칼과 반대).
# 회전 공통중심 없음 → 전역평균 대신 트랙 위치 주변 데칼만. 런타임 가능(GT 불요).
import cv2, sys, os, json, math
import numpy as np
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
K = 5   # 국소 데칼 수


def run(name, win=None):
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
    prev = {}                  # tid → (x,y) 직전 위치
    samples = []               # (fi, dot_track, dot_gt, |trkv|, phase)
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
        # 데칼 속도 — 직전 위치 대비
        cur = {t.tid: (t.x, t.y) for t in bt._tracks if t.miss == 0}
        decal_vel = {}
        for tid, (x, y) in cur.items():
            if tid in prev and tid != bt._tid:
                decal_vel[tid] = (x - prev[tid][0], y - prev[tid][1], x, y)
        tg = next((t for t in bt._tracks if t.tid == bt._tid), None)

        def local_field(px, py):
            """위치 (px,py) 주변 K개 데칼의 평균 속도 단위벡터. 부족하면 None."""
            cand = [(math.hypot(v[2]-px, v[3]-py), v[0], v[1]) for v in decal_vel.values()]
            cand = [c for c in cand if math.hypot(c[1], c[2]) >= 0.5]
            if len(cand) < 3:
                return None
            cand.sort(key=lambda c: c[0])
            sel = cand[:K]
            mvx = float(np.mean([c[1] for c in sel])); mvy = float(np.mean([c[2] for c in sel]))
            n = math.hypot(mvx, mvy)
            return (mvx/n, mvy/n) if n > 0.5 else None

        dot_t = dot_g = None
        if tg is not None and tg.tid in prev:
            tvx, tvy = tg.x - prev[tg.tid][0], tg.y - prev[tg.tid][1]
            tn = math.hypot(tvx, tvy)
            lf = local_field(tg.x, tg.y)
            if tn >= 0.5 and lf is not None:
                dot_t = (tvx/tn)*lf[0] + (tvy/tn)*lf[1]
        if i in gt and (i-1) in gt:
            gvx, gvy = gt[i][0]-gt[i-1][0], gt[i][1]-gt[i-1][1]
            gn = math.hypot(gvx, gvy)
            lf = local_field(gt[i][0], gt[i][1])
            if gn >= 0.5 and lf is not None:
                dot_g = (gvx/gn)*lf[0] + (gvy/gn)*lf[1]
        phase = "백" if i <= 24 else "투" if i >= 56 else " "
        samples.append((i, dot_t, dot_g, phase))
        prev = cur

    print(f"\n=== {name} === 트랙·GT 속도 vs 국소 데칼장 dot (양수=데칼동조, 음수=역행)")
    if win:
        print(f"  [상세 f{win[0]}~{win[1]}]  f | track·field | GT·field | phase")
        for fi, dt, dg, ph in samples:
            if win[0] <= fi <= win[1]:
                ds = f"{dt:+.2f}" if dt is not None else "  -  "
                gs = f"{dg:+.2f}" if dg is not None else "  -  "
                print(f"   {fi:3d}{ph} |   {ds}     |  {gs}")
    # 단계별 요약
    for label, cond in [("투명(f≥56)", lambda f: f >= 56), ("백색(f≤24)", lambda f: f <= 24)]:
        dts = [dt for fi, dt, dg, ph in samples if cond(fi) and dt is not None]
        dgs = [dg for fi, dt, dg, ph in samples if cond(fi) and dg is not None]
        ts = f"track중앙{np.median(dts):+.2f}(n{len(dts)})" if dts else "track-"
        gs = f"GT중앙{np.median(dgs):+.2f}(n{len(dgs)})" if dgs else "GT-"
        print(f"  [{label}] {ts}  {gs}")


if __name__ == "__main__":
    # 샌 판(035137)은 상세, 안 샌 판들은 요약
    run("000_0615_035137", win=(56, 71))
    for nm in ["000_0614_124417", "000_0615_042024", "000_0614_220518", "000_0615_000258"]:
        run(nm)
