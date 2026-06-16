# 재획득 오발 추적 — bt._tid 전환 시점·전환 전후 위치·GT오차 로깅(정상판 오발 규명)
import cv2, sys, glob, os, math, json
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))


def run(name):
    os.environ["REACQ_ON"] = "1"
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
    bt = ByteTracker(); lockd = False; wp = None; prev_tid = None
    print(f"\n=== {name} === 재획득(tid 전환) 이벤트")
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
        # 전환 감지 위해 update 전 tid 보관
        before = bt._tid
        bt.update(grays[i], dets)
        if not lockd:
            if wc and wp and (wc[0] - wp[0]) ** 2 + (wc[1] - wp[1]) ** 2 <= 225:
                bt.lock(wc[0], wc[1]); lockd = True
            if wc:
                wp = wc
        if lockd and bt._tid != before and before is not None:
            tg = next((t for t in bt._tracks if t.tid == bt._tid), None)
            g = gt.get(i)
            ge = f"GT오차 {math.hypot(tg.x-g[0], tg.y-g[1]):.0f}" if (g and tg) else "GT-"
            anc = bt._anchor_hist[0] if bt._anchor_hist else None
            print(f"  f{i}: tid {before}→{bt._tid}  새위치({tg.x:.0f},{tg.y:.0f}) "
                  f"age{tg.age} s{tg.score:.2f} {ge}  anchor={anc}")


if __name__ == "__main__":
    for n in sys.argv[1:]:
        run(n)
