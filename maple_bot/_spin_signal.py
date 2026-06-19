# 자전(spin) leak 신호 — 타겟만 제자리 회전, 데칼은 방향 고정(사용자 정정).
# 연속 프레임 crop의 회전각(rotational NCC)을 진짜타겟(GT) vs 데칼로 비교.
# 가설: 타겟 |회전각| 큼(자전), 데칼 |회전각| ~0(고정). 죽은 8축과 다른 축.
import cv2, sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
BOX = 40
ANGLES = list(range(-40, 41, 4))   # 탐색 회전각


def prep(frame, cx, cy):
    """crop → 핑크커서 inpaint → gray → 원형마스크 → 정규화."""
    H, W = frame.shape[:2]
    x0 = int(cx - BOX/2); y0 = int(cy - BOX/2)
    if x0 < 0 or y0 < 0 or x0+BOX >= W or y0+BOX >= H:
        return None
    c = frame[y0:y0+BOX, x0:x0+BOX].copy()
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, np.array([140,60,60]), np.array([175,255,255]))
    if m.any():
        m = cv2.dilate(m, np.ones((3,3),np.uint8), 1)
        c = cv2.inpaint(c, m, 3, cv2.INPAINT_TELEA)
    g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # 원형 마스크(배경 모서리 제거)
    yy, xx = np.ogrid[:BOX, :BOX]
    mask = (xx-BOX/2)**2 + (yy-BOX/2)**2 <= (BOX/2)**2
    g = g * mask
    g = (g - g[mask].mean())   # DC 제거
    return g, mask


def best_rot(a, b):
    """a를 회전시켜 b와 가장 잘 맞는 각도(NCC 최대). a,b=(gray,mask)."""
    ga, _ = a; gb, mb = b
    cen = (BOX/2, BOX/2)
    best_ang, best_score = 0, -2
    bn = gb[mb]; bn_norm = np.linalg.norm(bn) + 1e-6
    for ang in ANGLES:
        M = cv2.getRotationMatrix2D(cen, ang, 1.0)
        ra = cv2.warpAffine(ga, M, (BOX, BOX))
        an = ra[mb]
        sc = float(np.dot(an, bn) / (np.linalg.norm(an)*bn_norm + 1e-6))
        if sc > best_score:
            best_score, best_ang = sc, ang
    return best_ang, best_score


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
    gt = load_gt(name, min_f=0)

    # 데칼 위치 추적
    bt = ByteTracker(); lockd = False; wp = None
    decal_pos = {}
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0]+wb[2]/2.0, wb[1]+wb[3]/2.0)
        if lockd and big and wc:
            tg0 = next((t for t in bt._tracks if t.tid == bt._tid), None)
            if tg0 and (wc[0]-tg0.x)**2+(wc[1]-tg0.y)**2 <= 1225:
                bt.nudge(wc[0], wc[1])
        bt.update(grays[i], dets)
        if not lockd:
            if wc and wp and (wc[0]-wp[0])**2+(wc[1]-wp[1])**2 <= 225:
                bt.lock(wc[0], wc[1]); lockd=True
            if wc: wp = wc
        decal_pos[i] = {t.tid:(t.x,t.y) for t in bt._tracks if t.miss==0 and t.tid!=bt._tid}

    print(f"\n=== {name} === 자전 측정 — 연속 프레임 회전각(°) 진짜타겟 vs 데칼")
    print("  f | 타겟회전(score) | 데칼회전 중앙(n) p25 p75")
    tgt_rots = {'백':[], '투':[]}; dec_rots = {'백':[], '투':[]}
    for fi in sorted(gt):
        if (fi-1) not in gt:
            continue
        ph = '백' if fi <= 24 else '투' if fi >= 56 else None
        if ph is None:
            continue
        # 타겟 회전
        a = prep(frs[fi-1], gt[fi-1][0], gt[fi-1][1])
        b = prep(frs[fi], gt[fi][0], gt[fi][1])
        if a is None or b is None:
            continue
        t_ang, t_sc = best_rot(a, b)
        # 데칼 회전 — 직전·현재 둘다 추적된 데칼들
        d_angs = []
        common = set(decal_pos[fi-1]) & set(decal_pos[fi])
        for tid in list(common)[:12]:
            pa = prep(frs[fi-1], *decal_pos[fi-1][tid])
            pb = prep(frs[fi], *decal_pos[fi][tid])
            if pa is None or pb is None:
                continue
            da, ds = best_rot(pa, pb)
            if ds > 0.3:   # 매칭 신뢰도 낮은 건 제외
                d_angs.append(abs(da))
        if t_sc > 0.3:
            tgt_rots[ph].append(abs(t_ang))
        for x in d_angs:
            dec_rots[ph].append(x)
        ds = f"{np.median(d_angs):4.0f}(n{len(d_angs)})" if d_angs else "  -  "
        print(f"  {fi:3d}{ph}| {abs(t_ang):4.0f} ({t_sc:.2f})    | {ds}")

    print(f"\n  >>> 요약 |회전각| 중앙")
    for ph in ['백', '투']:
        t = tgt_rots[ph]; d = dec_rots[ph]
        ts = f"타겟 {np.median(t):.0f}°(n{len(t)})" if t else "타겟-"
        dd = f"데칼 {np.median(d):.0f}°(n{len(d)})" if d else "데칼-"
        sep = ""
        if t and d and np.median(t) >= 2*max(1,np.median(d)):
            sep = " ★분리"
        print(f"  [{ph}] {ts}  {dd}{sep}")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "000_0615_035137")
