# 전체 트랙 덤프 — 재출현 인식 변별력 측정(A:페이드위치 공간기억, B:orphan 성장+데칼orphan수)
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
    bt = ByteTracker(); lockd = False; wp = None; anchor = [None]
    print(f"\n=== {name} f{f0}~{f1} ===  (★=GT최근접 트랙, T=현재타겟tid)")
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
        g = gt.get(i)
        # f58 트랙 위치를 페이드 직전 '마지막 양호 위치(anchor)'로 기억
        if i == 58 and tg:
            anchor[0] = (tg.x, tg.y)
        if not (f0 <= i <= f1):
            continue
        gk = (min(bt._tracks, key=lambda t: (t.x-g[0])**2 + (t.y-g[1])**2)
              if g and bt._tracks else None)
        # 측정 A — anchor 기준 거리
        aT = math.hypot(tg.x-anchor[0][0], tg.y-anchor[0][1]) if (tg and anchor[0]) else -1
        aG = math.hypot(gk.x-anchor[0][0], gk.y-anchor[0][1]) if (gk and anchor[0]) else -1
        gs = f"GT({g[0]:3.0f},{g[1]:3.0f})" if g else "GT  -  "
        print(f"\n f{i}  {gs}  anchor거리: 타겟트랙={aT:3.0f}  GT트랙={aG:3.0f}")
        # 측정 B — young(age≤4)+강(score>0.6)+고정(miss=0) orphan 트랙 나열
        orph = [t for t in bt._tracks if t.age <= 4 and t.score > 0.6 and t.miss == 0]
        print(f"   young+강+고정 orphan {len(orph)}개:")
        for t in sorted(bt._tracks, key=lambda t: -(t.score)):
            if t.age <= 4 and t.score > 0.6 and t.miss == 0:
                mk = ("★" if gk and t.tid == gk.tid else " ") + ("T" if t.tid == bt._tid else " ")
                gdist = math.hypot(t.x-g[0], t.y-g[1]) if g else -1
                print(f"     {mk} tid{t.tid:3d} age{t.age:2d} s{t.score:.2f} "
                      f"rel{t.rel_ema:4.1f} miss{t.miss} ({t.x:3.0f},{t.y:3.0f}) GT거리{gdist:3.0f}")


if __name__ == "__main__":
    run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
