# 특정 프레임 구간 정밀 덤프 — GT·트랙·최근접후보·트랙속도로 매칭 실패 지점 규명
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
    bt = ByteTracker(); lockd = False; wp = None
    print(f"\n=== {name} f{f0}~{f1} ===")
    print("  i  GT(x,y)     track(x,y)  오차 trk_vel    GT최근접후보(거리,score)  "
          "trkRel  GT트랙(rel,score,거리)  trk5px강검출  검출연속  state")
    _pnd = [None]   # 직전 프레임 따라가는 트랙의 최근접 검출 위치
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        via = False
        if lockd and big and wc:
            tg = next((t for t in bt._tracks if t.tid == bt._tid), None)
            if tg and (wc[0] - tg.x) ** 2 + (wc[1] - tg.y) ** 2 <= 1225:
                bt.nudge(wc[0], wc[1]); via = True
        pos = bt.update(grays[i], dets)
        if not lockd:
            if wc and wp and (wc[0] - wp[0]) ** 2 + (wc[1] - wp[1]) ** 2 <= 225:
                bt.lock(wc[0], wc[1]); lockd = True; pos = wc; via = True
            if wc:
                wp = wc
            track = pos if lockd else None
        else:
            track = wc if via else pos
        if not (f0 <= i <= f1):
            continue
        tg = next((t for t in bt._tracks if t.tid == bt._tid), None)
        g = gt.get(i)
        # GT 최근접 후보(진짜 타겟 검출이 존재하는지)
        gc = ""
        if g and dets:
            cd = min(dets, key=lambda c: (c[0]-g[0])**2 + (c[1]-g[1])**2)
            gc = f"({math.hypot(cd[0]-g[0],cd[1]-g[1]):4.0f}px,{cd[2]:.2f})"
        gs = f"({g[0]:3.0f},{g[1]:3.0f})" if g else "    -    "
        ts = f"({track[0]:3.0f},{track[1]:3.0f})" if track else "    -    "
        er = f"{math.hypot(track[0]-g[0],track[1]-g[1]):4.0f}" if (g and track) else "  - "
        vel = f"({tg.vx:5.1f},{tg.vy:5.1f})" if tg else "      -     "
        # (a) 트랙이 따라가는 것의 rel_ema  (b) GT 최근접 트랙(진짜 타겟)의 rel,score,거리
        trel = f"{tg.rel_ema:5.1f}" if tg else "  -  "
        gtt = ""
        if g and bt._tracks:
            gk = min(bt._tracks, key=lambda t: (t.x - g[0]) ** 2 + (t.y - g[1]) ** 2)
            gd = math.hypot(gk.x - g[0], gk.y - g[1])
            gtt = f"(rel{gk.rel_ema:4.1f},s{gk.score:.2f},{gd:3.0f}px)"
        # (a) 따라가는 트랙 최근접 검출 거리+score(허공 coast면 거리 큼/약검출)
        a = "  -   "
        nd = None
        if tg and dets:
            nd = min(dets, key=lambda c: (c[0]-tg.x)**2 + (c[1]-tg.y)**2)
            a = f"{math.hypot(nd[0]-tg.x, nd[1]-tg.y):3.0f}px/s{nd[2]:.2f}"
        # (b) 따라가는 트랙 매칭검출이 직전과 연속인가(직전 최근접+트랙속도 예측 10px내)
        b = "-"
        if tg and nd is not None and _pnd[0] is not None:
            px, py = _pnd[0][0] + tg.vx, _pnd[0][1] + tg.vy
            b = "연속" if (nd[0]-px)**2 + (nd[1]-py)**2 <= 100 else "갈아탐"
        if tg and nd is not None:
            _pnd[0] = (nd[0], nd[1])
        print(f"  {i:3d} {gs} {ts} {er} {vel} {gc:24s} {trel}  {gtt:24s} "
              f"{a:6s} {b:6s} {bt._state}")


if __name__ == "__main__":
    run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
