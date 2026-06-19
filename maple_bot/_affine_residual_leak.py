# 어파인 누적 잔차 leak 측정 — 빠졌던 세 조건 적용.
# (1) 순간 dot 아닌 '누적 위치 잔차'(K프레임 잔차벡터 합의 크기 = 배경에서 순 이탈)
# (2) 겹침(occlusion) 프레임 제외(타겟이 다른 트랙 14px 내)
# (3) CMC 안정화 좌표계(ByteTracker cmc=True의 어파인 H로 warp)
import cv2, sys, os, json, math
import numpy as np
from collections import deque, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
KWIN = 8       # 누적 잔차 윈도우
OCC_R = 14     # 겹침 제외 반경(NMS floor)


def warp(H, x, y):
    if H is None:
        return None
    return (H[0,0]*x + H[0,1]*y + H[0,2], H[1,0]*x + H[1,1]*y + H[1,2])


def run(name, detail=False):
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

    bt = ByteTracker(cmc=True)    # (3) CMC 안정화 좌표계 — 어파인 H 매 프레임 추정
    lockd = False; wp = None
    prev_tpos = None              # 타겟 트랙 직전 위치
    prev_gt = None
    tk_res = deque(maxlen=KWIN)   # 타겟 잔차 벡터(누적용)
    gt_res = deque(maxlen=KWIN)
    rows_out = []                 # (fi, tk_cum, gt_cum, occluded, phase)
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        if lockd and big and wc:
            tg0 = next((t for t in bt._tracks if t.tid == bt._tid), None)
            if tg0 and (wc[0]-tg0.x)**2 + (wc[1]-tg0.y)**2 <= 1225:
                bt.nudge(wc[0], wc[1])
        bt.update(grays[i], dets)
        if not lockd:
            if wc and wp and (wc[0]-wp[0])**2 + (wc[1]-wp[1])**2 <= 225:
                bt.lock(wc[0], wc[1]); lockd = True
            if wc:
                wp = wc
        H = bt._H
        tg = next((t for t in bt._tracks if t.tid == bt._tid), None)

        # (2) 겹침 판정 — 타겟이 다른 트랙 OCC_R 내
        occluded = False
        if tg is not None:
            for t in bt._tracks:
                if t.tid != bt._tid and t.miss == 0 and \
                        (t.x-tg.x)**2 + (t.y-tg.y)**2 <= OCC_R**2:
                    occluded = True; break

        # (1) 누적 잔차 — 잔차벡터 = 실제 - 어파인예측(배경따라갔을 위치)
        tk_cum = gt_cum = None
        if tg is not None and prev_tpos is not None and H is not None and not occluded:
            pr = warp(H, prev_tpos[0], prev_tpos[1])
            if pr:
                tk_res.append((tg.x - pr[0], tg.y - pr[1]))
                sx = sum(v[0] for v in tk_res); sy = sum(v[1] for v in tk_res)
                tk_cum = math.hypot(sx, sy)
        elif occluded:
            tk_res.clear()   # 겹침 구간은 누적 리셋(오염 방지)
        if i in gt and prev_gt is not None and H is not None and not occluded:
            pr = warp(H, prev_gt[0], prev_gt[1])
            if pr:
                gt_res.append((gt[i][0]-pr[0], gt[i][1]-pr[1]))
                sx = sum(v[0] for v in gt_res); sy = sum(v[1] for v in gt_res)
                gt_cum = math.hypot(sx, sy)

        phase = "백" if i <= 24 else "투" if i >= 56 else " "
        rows_out.append((i, tk_cum, gt_cum, occluded, phase))
        if tg is not None:
            prev_tpos = (tg.x, tg.y)
        if i in gt:
            prev_gt = gt[i]

    print(f"\n=== {name} === 어파인 누적잔차(K{KWIN}, 겹침제외, CMC좌표) — 배경서 순이탈(px)")
    if detail:
        print("  f  | 타겟트랙 누적 | GT 누적 | 겹침")
        for fi, tc, gc, occ, ph in rows_out:
            if fi >= 56:
                ts = f"{tc:5.1f}" if tc is not None else "  -  "
                gs = f"{gc:5.1f}" if gc is not None else "  -  "
                print(f"  {fi:3d}{ph}|   {ts}      | {gs}   | {'★' if occ else ''}")
    for label, cond in [("투명(f≥56)", lambda f: f >= 56)]:
        tc = [r[1] for r in rows_out if cond(r[0]) and r[1] is not None]
        gc = [r[2] for r in rows_out if cond(r[0]) and r[2] is not None]
        occ_n = sum(1 for r in rows_out if cond(r[0]) and r[3])
        ts = f"타겟트랙 중앙{np.median(tc):.1f} p75 {np.percentile(tc,75):.1f}(n{len(tc)})" if tc else "타겟-"
        gs = f"GT 중앙{np.median(gc):.1f} p75 {np.percentile(gc,75):.1f}(n{len(gc)})" if gc else "GT-"
        print(f"  [{label}] {ts} | {gs} | 겹침제외 {occ_n}f")


if __name__ == "__main__":
    run("000_0615_035137", detail=True)
    for nm in ["000_0614_124417", "000_0615_042024", "000_0614_220518"]:
        run(nm)
