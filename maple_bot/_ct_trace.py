# 강체 별자리 추적 진단 — 턴 구간에서 GT 근처에 아웃라이어(타겟 검출) 있는데 못 고르나 확인.
import cv2, json, sys, math, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.constellation_tracker import ConstellationTracker
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))


def near(pts, g, r=25):
    return [f"({p[0]:.0f},{p[1]:.0f})" for p in pts
            if g and math.hypot(p[0] - g[0], p[1] - g[1]) <= r]


def main(name, lo, hi):
    gt = load_gt(name, min_f=0)
    mp4 = os.path.join(ROOT, '_record_debug', name + '.mp4')
    rows = [json.loads(l) for l in open(mp4[:-4] + '.jsonl', encoding='utf-8')]
    cap = cv2.VideoCapture(mp4); frs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frs.append(f)
    cap.release()
    ct = ConstellationTracker(); ct.set_bounds(frs[0].shape[1], frs[0].shape[0])
    lockd = False; wp = None
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        if not lockd:
            if wc and wp and (wc[0] - wp[0]) ** 2 + (wc[1] - wp[1]) ** 2 <= 225:
                ct.lock(wc[0], wc[1], dets); lockd = True
            if wc:
                wp = wc
            tr = ct.center if lockd else None
        else:
            tr = ct.update(dets, white_center=wc if (big and wc) else None)
        g = gt.get(i)
        if lockd and lo <= i <= hi:
            gerr = math.hypot(tr[0]-g[0], tr[1]-g[1]) if (g and tr) else -1
            ts = f"({tr[0]:5.0f},{tr[1]:5.0f})" if tr else "None"
            outl = getattr(ct, '_last_outliers', [])
            # GT 근처에 검출(아웃라이어/전체) 있나
            allnear = near(dets, g)
            outnear = near(outl, g)
            gstr = f"GT({g[0]:.0f},{g[1]:.0f})" if g else "GT-"
            print(f"f{i:3d} det{len(dets):2d} anc{len(ct._anchors):2d} miss{ct._miss} "
                  f"tgt{ts} err{gerr:4.0f} {gstr} GT근처검출{allnear} 아웃{outnear}")


if __name__ == "__main__":
    nm = sys.argv[1] if len(sys.argv) > 1 else "000_0615_035137"
    lo = int(sys.argv[2]) if len(sys.argv) > 2 else 52
    hi = int(sys.argv[3]) if len(sys.argv) > 3 else 72
    main(nm, lo, hi)
