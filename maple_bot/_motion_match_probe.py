# 운동 동조 진단 — 투명 구간에서 타겟(GT) 속도 vs 배경(phaseCorrelate) 속도의 방향/속도 일치
# Codex 질문: "방향 일치"·"속도 일치"가 분리되나 동시에 오나. 동시면 cost 양항 무력→지연결정 필수.
import cv2, sys, glob, os, math
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.abspath(__file__))


def red_mark(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    m = (cv2.inRange(hsv, np.array([0, 120, 100]), np.array([8, 255, 255]))
         | cv2.inRange(hsv, np.array([174, 120, 100]), np.array([180, 255, 255])))
    c, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not c:
        return None
    b = max(c, key=cv2.contourArea)
    if cv2.contourArea(b) < 8:
        return None
    M = cv2.moments(b)
    return (M["m10"] / M["m00"], M["m01"] / M["m00"]) if M["m00"] else None


def run(name):
    # GT(빨간점) 프레임 인덱스→위치
    gt = {}
    for p in sorted(glob.glob(os.path.join(ROOT, '_gt_frames', name, 'f*.png'))):
        fi = int(os.path.basename(p)[1:4])
        g = red_mark(cv2.imread(p))
        if g:
            gt[fi] = g
    # 배경 변위(phaseCorrelate) — mp4 grays
    cap = cv2.VideoCapture(os.path.join(ROOT, '_record_debug', name + '.mp4'))
    grays = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        grays.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32))
    cap.release()

    print(f"\n=== {name} === GT {len(gt)}프레임")
    print(" i  |tgt_v| ang(tgt,bg)°  Δspeed  →분류")
    both = dir_only = spd_only = neither = 0
    for fi in sorted(gt):
        if (fi - 1) not in gt or fi >= len(grays) or fi < 1:
            continue
        tvx = gt[fi][0] - gt[fi - 1][0]; tvy = gt[fi][1] - gt[fi - 1][1]
        (bvx, bvy), _ = cv2.phaseCorrelate(grays[fi - 1], grays[fi])
        ts = math.hypot(tvx, tvy); bs = math.hypot(bvx, bvy)
        if ts < 1e-6 or bs < 1e-6:
            continue
        cosang = (tvx * bvx + tvy * bvy) / (ts * bs)
        ang = math.degrees(math.acos(max(-1, min(1, cosang))))
        dspd = abs(ts - bs)
        dmatch = ang < 30          # 방향 일치(±30°)
        smatch = dspd < 3.0        # 속도 일치(<3px/f)
        cls = ("동시(BOTH)" if dmatch and smatch else
               "방향만" if dmatch else "속도만" if smatch else "무동조")
        if dmatch and smatch: both += 1
        elif dmatch: dir_only += 1
        elif smatch: spd_only += 1
        else: neither += 1
        print(f"{fi:3d}  {ts:5.1f}  {ang:6.1f}      {dspd:5.1f}   {cls}")
    print(f"  합계: 동시={both} 방향만={dir_only} 속도만={spd_only} 무동조={neither}")


if __name__ == "__main__":
    for n in sys.argv[1:]:
        run(n)
