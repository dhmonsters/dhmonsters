# 자전 신호 정밀 측정 — log-polar 위상상관(회전 추정 표준). 브루트포스 NCC보다 robust.
# 회전 = 극좌표 변환 후 각도축 shift = phaseCorrelate. response로 신뢰도 가중.
# 누적 회전(net) 측정 — 타겟 자전이 일관되면 누적 큼, noise면 상쇄돼 ~0.
import cv2, sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
BOX = 48
_HANN = cv2.createHanningWindow((BOX, BOX), cv2.CV_32F)


def polar(frame, cx, cy):
    """crop → 커서 inpaint → gray → Hanning → log-polar(각도축=세로)."""
    H, W = frame.shape[:2]
    x0 = int(cx-BOX/2); y0 = int(cy-BOX/2)
    if x0 < 0 or y0 < 0 or x0+BOX >= W or y0+BOX >= H:
        return None
    c = frame[y0:y0+BOX, x0:x0+BOX].copy()
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, np.array([140,60,60]), np.array([175,255,255]))
    if m.any():
        c = cv2.inpaint(c, cv2.dilate(m, np.ones((3,3),np.uint8),1), 3, cv2.INPAINT_TELEA)
    g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY).astype(np.float32)
    g = (g - g.mean()) * _HANN
    p = cv2.warpPolar(g, (BOX, BOX), (BOX/2, BOX/2), BOX/2,
                      cv2.INTER_LINEAR + cv2.WARP_POLAR_LINEAR)
    return p


def rot(pa, pb):
    """두 극좌표 이미지의 각도축 shift → 회전각(°)와 response."""
    (sx, sy), resp = cv2.phaseCorrelate(pa, pb)
    ang = sy / BOX * 360.0   # 세로축 = 각도(0~360)
    if ang > 180: ang -= 360
    if ang < -180: ang += 360
    return ang, resp


def run(name):
    mp4 = os.path.join(ROOT, '_record_debug', name + '.mp4')
    rows = [json.loads(l) for l in open(mp4[:-4] + '.jsonl', encoding='utf-8')]
    cap = cv2.VideoCapture(mp4); frs = []
    while True:
        ok, f = cap.read()
        if not ok: break
        frs.append(f)
    cap.release()
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frs]
    gt = load_gt(name, min_f=0)
    bt = ByteTracker(); lockd=False; wp=None; decal_pos={}
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc=None
        big = wb is not None and wb[2]>=50 and wb[3]>=50
        if wb is not None and wb[2]>=20: wc=(wb[0]+wb[2]/2.0, wb[1]+wb[3]/2.0)
        if lockd and big and wc:
            tg0=next((t for t in bt._tracks if t.tid==bt._tid),None)
            if tg0 and (wc[0]-tg0.x)**2+(wc[1]-tg0.y)**2<=1225: bt.nudge(wc[0],wc[1])
        bt.update(grays[i],dets)
        if not lockd:
            if wc and wp and (wc[0]-wp[0])**2+(wc[1]-wp[1])**2<=225: bt.lock(wc[0],wc[1]); lockd=True
            if wc: wp=wc
        decal_pos[i]={t.tid:(t.x,t.y) for t in bt._tracks if t.miss==0 and t.tid!=bt._tid}

    print(f"\n=== {name} === 자전 정밀(log-polar) — 프레임당 회전°(resp), 누적 회전")
    print("  f | 타겟 회전(resp) | 데칼 회전 중앙(resp) | 타겟누적 데칼누적")
    t_cum=0.0; d_cum=0.0; RESP=0.10
    t_vals={'백':[], '투':[]}; d_vals={'백':[], '투':[]}
    for fi in sorted(gt):
        if (fi-1) not in gt: continue
        ph='백' if fi<=24 else '투' if fi>=56 else None
        if ph is None: continue
        pa=polar(frs[fi-1],gt[fi-1][0],gt[fi-1][1]); pb=polar(frs[fi],gt[fi][0],gt[fi][1])
        if pa is None or pb is None: continue
        t_ang,t_r=rot(pa,pb)
        d_list=[]
        for tid in set(decal_pos[fi-1])&set(decal_pos[fi]):
            da=polar(frs[fi-1],*decal_pos[fi-1][tid]); db=polar(frs[fi],*decal_pos[fi][tid])
            if da is None or db is None: continue
            ang,r=rot(da,db)
            if r>=RESP: d_list.append(ang)
        if t_r>=RESP:
            t_cum+=t_ang; t_vals[ph].append(abs(t_ang))
        if d_list:
            d_cum+=np.median(d_list)
            for x in d_list: d_vals[ph].append(abs(x))
        dmed=f"{np.median(d_list):+5.1f}(n{len(d_list)})" if d_list else "  -  "
        print(f"  {fi:3d}{ph}| {t_ang:+5.1f} ({t_r:.2f})  | {dmed}        | {t_cum:+6.0f}  {d_cum:+6.0f}")

    print(f"\n  >>> 요약 (resp≥{RESP})")
    for ph in ['백','투']:
        t=t_vals[ph]; d=d_vals[ph]
        ts=f"타겟 |회전|중앙 {np.median(t):.1f}°(n{len(t)})" if t else "타겟-"
        ds=f"데칼 |회전|중앙 {np.median(d):.1f}°(n{len(d)})" if d else "데칼-"
        print(f"  [{ph}] {ts}  {ds}")
    print(f"  누적 회전: 타겟 {t_cum:+.0f}°  데칼 {d_cum:+.0f}°  "
          f"(타겟 자전 일관되면 누적 큼, noise면 ~0)")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "000_0615_035137")
