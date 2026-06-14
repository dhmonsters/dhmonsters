# GT(사용자 빨간점 라벨) 기반 ByteTracker 추적 정확도 채점 — _gt_frames/<name>/f*.png의
# 빨간 점을 진짜 도형 위치로 읽어, 현재 ByteTracker 재생 track과 평균 오차(px) 산출.
import cv2, json, sys, math, glob, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker

ROOT = os.path.dirname(os.path.abspath(__file__))


def red_mark(bgr):
    """빨간 점(GT) 중심 검출 — 핑크 커서(H140~170)와 구분되는 순수 빨강."""
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


def load_gt(name, min_f=50):
    gt = {}
    for p in sorted(glob.glob(os.path.join(ROOT, '_gt_frames', name, 'f*.png'))):
        fi = int(os.path.basename(p)[1:4])
        g = red_mark(cv2.imread(p))
        if g and fi >= min_f:
            gt[fi] = g
    return gt


def run_bytetrack(name):
    """솔버와 동일 흐름(흰색우선+nudge+ByteTrack) 재생, 프레임별 track 반환."""
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
    bt = ByteTracker(); lockd = False; wp = None; out = {}
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        via = False
        if lockd and big and wc:
            tg = next((t for t in bt._tracks if t.tid == bt._tid), None)
            if tg and (wc[0] - tg.x) ** 2 + (wc[1] - tg.y) ** 2 <= 1225:
                bt.nudge(wc[0], wc[1]); via = True
        pos = bt.update(grays[i], dets)
        if not lockd:
            if wc and wp and (wc[0] - wp[0]) ** 2 + (wc[1] - wp[1]) ** 2 <= 225:
                bt.lock(wc[0], wc[1]); lockd = True; pos = wc; via = True
            if wc:
                wp = wc
            track = pos if lockd else None
        else:
            track = wc if via else pos
        out[i] = track
    return out


if __name__ == "__main__":
    names = sys.argv[1:] or [os.path.basename(d) for d in
                             sorted(glob.glob(os.path.join(ROOT, '_gt_frames', '*')))
                             if os.path.isdir(d)]
    for name in names:
        gt = load_gt(name)
        if not gt:
            print(f"{name}: GT 없음"); continue
        res = run_bytetrack(name)
        errs = [math.hypot(res[fi][0] - g[0], res[fi][1] - g[1])
                for fi, g in gt.items() if res.get(fi)]
        if errs:
            print(f"{name}: GT {len(gt)}프레임, 평균오차 {np.mean(errs):.0f}px "
                  f"(최대 {max(errs):.0f})")
