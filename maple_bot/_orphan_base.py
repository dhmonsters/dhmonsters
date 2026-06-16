# orphan 베이스레이트 — 정상 추적 구간에 young+고정+강 orphan이 상시 몇 개 뜨나(오발 위험 측정)
import cv2, sys, glob, os, math, json
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
ROOT = os.path.dirname(os.path.abspath(__file__))
ANCHOR_MAX = 100


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
    bt = ByteTracker(); lockd = False; wp = None
    counts = []       # 프레임별 orphan 수(타겟 제외)
    near = []         # 프레임별 타겟트랙 100px 내 orphan 수
    nframes = 0
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
            continue
        tg = next((t for t in bt._tracks if t.tid == bt._tid), None)
        if tg is None:
            continue
        nframes += 1
        orph = [t for t in bt._tracks if t.tid != bt._tid and t.age <= 4
                and t.score > 0.6 and t.miss == 0]
        counts.append(len(orph))
        near.append(sum(1 for t in orph
                        if (t.x - tg.x) ** 2 + (t.y - tg.y) ** 2 <= ANCHOR_MAX ** 2))
    if not counts:
        print(f"{name}: 잠금 없음"); return
    c = np.array(counts); n = np.array(near)
    print(f"{name}: 잠금 {nframes}f | orphan/f 평균 {c.mean():.2f} "
          f"(≥1: {100*(c>=1).mean():.0f}%) | 타겟100px내 orphan ≥1: {100*(n>=1).mean():.0f}% "
          f"평균 {n.mean():.2f}")


if __name__ == "__main__":
    names = sys.argv[1:] or [os.path.basename(p)[:-4] for p in
                             sorted(glob.glob(os.path.join(ROOT, '_record_debug', '*.mp4')))]
    for nm in names:
        try:
            run(nm)
        except Exception as e:
            print(f"{nm}: 오류 {e}")
