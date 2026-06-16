# anchor N 측정 — anchor=트랙위치(N프레임 전)가 진짜 타겟 orphan vs 데칼 orphan 중 어느 쪽
# 최근접인지. N 작으면 새는 위치 오염, 크면 stale. 진짜 타겟이 안정적으로 최근접인 N 탐색.
import cv2, sys, glob, os, math, json
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
NS = [3, 5, 8]


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
    bt = ByteTracker(); lockd = False; wp = None; hist = {}
    print(f"\n=== {name} f{f0}~{f1} ===  anchor=트랙위치(N전). ★=진짜타겟 orphan")
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
        if tg:
            hist[i] = (tg.x, tg.y)
        if not (f0 <= i <= f1):
            continue
        g = gt.get(i)
        orph = [t for t in bt._tracks if t.tid != bt._tid and t.age <= 4
                and t.score > 0.6 and t.miss == 0]
        if not orph:
            print(f" f{i}: orphan 0개"); continue
        # 진짜 타겟 orphan = GT 최근접 orphan
        tgt_o = min(orph, key=lambda t: (t.x-g[0])**2 + (t.y-g[1])**2) if g else None
        line = f" f{i}: orphan {len(orph)}개 | "
        for N in NS:
            a = hist.get(i - N)
            if a is None:
                line += f"N{N}:- "; continue
            nearest = min(orph, key=lambda t: (t.x-a[0])**2 + (t.y-a[1])**2)
            hit = "★" if (tgt_o and nearest.tid == tgt_o.tid) else "✗"
            ad = math.hypot(nearest.x-a[0], nearest.y-a[1])
            line += f"N{N}:{hit}{ad:3.0f}px "
        # 진짜 타겟 orphan의 GT거리(이게 작아야 tgt_o가 실제 타겟)
        if tgt_o and g:
            line += f"| 타겟orphan GT거리{math.hypot(tgt_o.x-g[0],tgt_o.y-g[1]):3.0f}"
        print(line)


if __name__ == "__main__":
    run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
