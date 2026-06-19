# 임의 점 추적(KLT) — 시작 시 타겟에 점을 찍어 광류로 따라가기. 원(꼭지점 없음) 대응.
# 가설: 흰색 시작 시 타겟 위 특징점들을 잡아 Lucas-Kanade로 추적 → 점들이 도형을 따라감.
# 검출·모양 불요. 점이 배경으로 새는지/도형에 붙는지 GT로 검증.
import cv2, sys, os, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))

LK = dict(winSize=(21, 21), maxLevel=3,
          criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01))


def run(name, init_r=22, reseed=True):
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
        print(f"{name}: GT 없음"); return None
    f0 = min(gt)
    cx, cy = gt[f0]

    # 초기 점들 — 타겟 위 특징점(goodFeatures) + 중심점. 없으면 격자.
    mask = np.zeros(grays[f0].shape, np.uint8)
    cv2.circle(mask, (int(cx), int(cy)), init_r, 255, -1)
    pts = cv2.goodFeaturesToTrack(grays[f0], 30, 0.01, 4, mask=mask)
    if pts is None:
        pts = np.array([[[cx, cy]]], np.float32)
    pts = np.vstack([pts.reshape(-1, 2), [[cx, cy]]]).astype(np.float32).reshape(-1, 1, 2)

    center = (cx, cy); errs = []
    for i in range(f0 + 1, len(frs)):
        npts, st, err = cv2.calcOpticalFlowPyrLK(grays[i-1], grays[i], pts, None, **LK)
        if npts is None:
            break
        good = npts[st.ravel() == 1]
        if len(good) >= 3:
            # 중앙값 중심(이상점 강건). 중심서 너무 먼 점(>40px) 제거 = 배경 샌 점
            med = np.median(good.reshape(-1, 2), axis=0)
            d = np.linalg.norm(good.reshape(-1, 2) - med, axis=1)
            keep = good.reshape(-1, 2)[d < 40]
            if len(keep) >= 3:
                center = tuple(np.median(keep, axis=0))
                pts = keep.astype(np.float32).reshape(-1, 1, 2)
            else:
                pts = good.reshape(-1, 1, 2)
        else:
            pts = npts
        # 점 부족하면 현재 중심 주변 재시드(흰색 소실 후 특징 줄어듦)
        if reseed and len(pts) < 8:
            m = np.zeros(grays[i].shape, np.uint8)
            cv2.circle(m, (int(center[0]), int(center[1])), init_r, 255, -1)
            extra = cv2.goodFeaturesToTrack(grays[i], 20, 0.01, 4, mask=m)
            if extra is not None:
                pts = np.vstack([pts.reshape(-1, 2), extra.reshape(-1, 2)]).astype(np.float32).reshape(-1, 1, 2)
        if i in gt:
            errs.append(math.hypot(center[0]-gt[i][0], center[1]-gt[i][1]))
    return (np.mean(errs), max(errs), len(errs)) if errs else None


if __name__ == "__main__":
    shape = {'000_0615_022618':'원','000_0615_042024':'원','000_0614_114417':'원',
             '000_0615_025624':'원','000_0615_015619':'원','000_0615_035137':'별',
             '000_0614_220518':'세모','000_0615_062325':'네모'}
    print("=== KLT 점추적 — 시작 타겟에 점 찍고 광류 추적 ===")
    for nm in (sys.argv[1:] or shape):
        r = run(nm)
        if r:
            print(f"  {nm} ({shape.get(nm,'?')}) | 평균 {r[0]:.0f}px 최대 {r[1]:.0f} (n{r[2]})")
