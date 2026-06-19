# 하이브리드 추적 — 백색 단계는 밝기추적(정확), 투명 전환 시 vortex 핸드오프.
# vortex 단독의 백색→투명 공백 드리프트(035137) 해결 목적. 전체 16판 GT 재검증.
import cv2, sys, os, math, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from _vortex_test import compute_vortex
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))


def run_hybrid(name, mt=0.4, vt=5.0, r=70, alpha=0.5, max_speed=40, white_gate=60):
    mp4 = os.path.join(ROOT, '_record_debug', name + '.mp4')
    cap = cv2.VideoCapture(mp4); frs = []
    while True:
        ok, f = cap.read()
        if not ok: break
        frs.append(f)
    cap.release()
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frs]
    gt = load_gt(name, min_f=0)
    if not gt:
        return None
    fis = sorted(gt); f0 = fis[0]
    center = list(gt[f0]); errs = []; modes = {'백': 0, 'vortex': 0}
    for i in range(f0 + 1, len(frs)):
        wb = acquire_white(frs[i])
        wc = None
        if wb is not None and wb[2] >= 50 and wb[3] >= 50:
            wc = (wb[0] + wb[2]/2.0, wb[1] + wb[3]/2.0)
        if wc is not None and math.hypot(wc[0]-center[0], wc[1]-center[1]) <= white_gate:
            # 백색 단계 — 밝기 중심으로 정확히 잠금
            center = [wc[0], wc[1]]; modes['백'] += 1
        else:
            # 투명 — vortex 핸드오프(직전 center에서)
            flow = cv2.calcOpticalFlowFarneback(grays[i-1], grays[i], None, 0.5, 3, 15, 3, 5, 1.2, 0)
            res, pk = compute_vortex(flow, center, r, mt, vt)
            if res is not None:
                nx = alpha*center[0] + (1-alpha)*res[0]; ny = alpha*center[1] + (1-alpha)*res[1]
                d = math.hypot(nx-center[0], ny-center[1])
                if d > max_speed:
                    nx = center[0]+(nx-center[0])*max_speed/d; ny = center[1]+(ny-center[1])*max_speed/d
                center = [nx, ny]
            modes['vortex'] += 1
        if i in gt:
            errs.append(math.hypot(center[0]-gt[i][0], center[1]-gt[i][1]))
    return (np.mean(errs), max(errs), len(errs), modes) if errs else None


if __name__ == "__main__":
    shape = {'000_0615_022618':'원','000_0615_042024':'원','000_0614_114417':'원','000_0615_025624':'원','000_0615_015619':'원','000_0615_035137':'별','000_0615_044401':'별','000_0614_220518':'세모','000_0614_204718':'세모','000_0615_062325':'네모','000_0614_124417':'네모','000_0615_000258':'네모','000_0614_111417':'네모','000_0614_185318':'네모','000_0614_233218':'네모','000_0614_121417':'별'}
    bt = {'000_0614_111417':123,'000_0614_114417':120,'000_0614_121417':100,'000_0614_124417':61,'000_0614_185318':102,'000_0614_204718':75,'000_0614_220518':18,'000_0614_233218':76,'000_0615_000258':38,'000_0615_015619':155,'000_0615_022618':999,'000_0615_025624':106,'000_0615_035137':80,'000_0615_042024':63,'000_0615_044401':104,'000_0615_062325':110}
    vtx = {'000_0614_111417':50,'000_0614_114417':38,'000_0614_121417':45,'000_0614_124417':82,'000_0614_185318':21,'000_0614_204718':49,'000_0614_220518':30,'000_0614_233218':38,'000_0615_000258':75,'000_0615_015619':80,'000_0615_022618':76,'000_0615_025624':47,'000_0615_035137':92,'000_0615_042024':62,'000_0615_044401':23,'000_0615_062325':58}
    names = sorted(os.path.basename(d) for d in glob.glob(os.path.join(ROOT, '_gt_frames', '*')) if os.path.isdir(d))
    print("=== 하이브리드(백색밝기→투명vortex) 전체 16판 ===")
    hsum = []; suc = 0
    for nm in names:
        res = run_hybrid(nm)
        if not res:
            print(f"  {nm}: GT부족"); continue
        m, mx, n, md = res
        hsum.append(m)
        if m <= 40: suc += 1
        b = bt.get(nm, 0); vx = vtx.get(nm, 0)
        bs = '소실' if b >= 999 else f'{b}'
        flag = '★' if m <= 40 else ''
        print(f"  {nm} ({shape.get(nm,'?')}) | BT {bs:>4} vortex {vx:3} → hybrid {m:3.0f}px(최대{mx:.0f}) [백{md['백']}/v{md['vortex']}] {flag}")
    print(f"  >>> hybrid 평균 {np.mean(hsum):.0f}px | 성공(≤40px) {suc}/16  (BT 2, vortex 5)")
