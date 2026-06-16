# CMC 진단 — 녹화별로 어파인 소스(데칼/ORB/외삽/none) 분포 + dtheta·이동량 통계
import cv2, json, sys, glob, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
import core.vision.byte_tracker as BT
from core.vision.byte_tracker import ByteTracker

ROOT = os.path.dirname(os.path.abspath(__file__))

# _estimate_cmc 래핑 — 소스/추정 로깅
_orig = ByteTracker._estimate_cmc
def _wrap(self, prev_pos, prev_gray, cur_gray):
    src = _orig(self, prev_pos, prev_gray, cur_gray)
    H = self._H
    if H is not None:
        dth = float(np.degrees(np.arctan2(H[1, 0], H[0, 0])))
        tx, ty = float(H[0, 2]), float(H[1, 2])
    else:
        dth = tx = ty = 0.0
    self._log.append((src, dth, tx, ty))
    return src
ByteTracker._estimate_cmc = _wrap


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
    bt = ByteTracker(); bt._log = []; lockd = False; wp = None
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
    return bt._log


if __name__ == "__main__":
    for name in sys.argv[1:]:
        log = run(name)
        from collections import Counter
        cnt = Counter(s for s, *_ in log)
        dths = [d for s, d, *_ in log if s in ("decal", "orb")]
        trs = [(tx ** 2 + ty ** 2) ** 0.5 for s, d, tx, ty in log if s in ("decal", "orb")]
        print(f"\n{name}: {len(log)}프레임  소스={dict(cnt)}")
        if dths:
            print(f"  dtheta(도): 평균{np.mean(dths):.2f} 최대{max(dths,key=abs):.2f}  "
                  f"이동량(px): 평균{np.mean(trs):.1f} 최대{max(trs):.1f}")
