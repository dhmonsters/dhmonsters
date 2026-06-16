# leak 신호 측정 — 현재 추적 트랙 vel vs 배경 운동장(bg vel) 동조도(K=5 누적).
# 가설: 샌 트랙(035137)=배경 동조(잔차↓), 안 샌 트랙(124417/042024)=이탈(잔차↑) → leak 트리거.
import cv2, sys, glob, os, math, json
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))


def run(name, f0, f1):
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
    bt = ByteTracker(); lockd = False; wp = None; resid_hist = []
    print(f"\n=== {name} f{f0}~{f1} ===  trk_vel / bg_vel / ang° / |Δvel| / K5누적잔차 / GT오차")
    accum = []
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
        tg = next((t for t in bt._tracks if t.tid == bt._tid), None)
        if tg is None:
            continue
        bvx, bvy = bt._bgvx, bt._bgvy
        dvx, dvy = tg.vx - bvx, tg.vy - bvy
        resid = math.hypot(dvx, dvy)
        resid_hist.append(resid)
        if len(resid_hist) > 5:
            resid_hist.pop(0)
        k5 = float(np.mean(resid_hist))
        ts = math.hypot(tg.vx, tg.vy); bs = math.hypot(bvx, bvy)
        if ts > 1e-6 and bs > 1e-6:
            ang = math.degrees(math.acos(max(-1, min(1, (tg.vx*bvx+tg.vy*bvy)/(ts*bs)))))
        else:
            ang = -1
        if f0 <= i <= f1:
            g = gt.get(i)
            ge = f"{math.hypot(tg.x-g[0],tg.y-g[1]):3.0f}" if g else " - "
            print(f"  f{i}: trk({tg.vx:5.1f},{tg.vy:5.1f}) bg({bvx:5.1f},{bvy:5.1f}) "
                  f"ang{ang:4.0f} |Δ|{resid:4.1f} K5{k5:4.1f} GT{ge}")
            accum.append(k5)
    if accum:
        print(f"  >>> 구간 K5누적잔차 평균 {np.mean(accum):.1f}  (낮음=배경동조=샘 / 높음=이탈=안샘)")


if __name__ == "__main__":
    print("샌 트랙(035137) vs 안 샌 트랙(124417/042024)")
    run("000_0615_035137", 60, 66)
    run("000_0614_124417", 72, 80)
    run("000_0615_042024", 96, 104)
