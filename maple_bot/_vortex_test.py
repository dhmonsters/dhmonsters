# vortex(소용돌이) 트래커 복원 + GT 테스트 — 광류 방향 다양성으로 자전 중심 추적.
# 경쟁 솔버 vortex.exe 디스어셈블리 복원. 검출 없이 물리(타겟만 자전)로 추적.
import cv2, sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))


def compute_vortex(flow, center, search_r, motion_thresh, vortex_thresh, sub_bg=True):
    """광류에서 소용돌이 중심(자전점) 추출. center 주변 search_r 내.
    sub_bg=True면 ROI 내 배경(median) 광류를 빼서 타겟 자전 잔차를 드러냄."""
    rh, rw = flow.shape[:2]
    if sub_bg:
        # ROI 내 median 광류 = 배경 스크롤 → 빼면 타겟 자전이 잔차로 남음
        y0 = max(0, int(center[1]-search_r)); y1 = min(rh, int(center[1]+search_r))
        x0 = max(0, int(center[0]-search_r)); x1 = min(rw, int(center[0]+search_r))
        roi = flow[y0:y1, x0:x1]
        if roi.size:
            mvx = float(np.median(roi[..., 0])); mvy = float(np.median(roi[..., 1]))
            flow = flow.copy()
            flow[..., 0] -= mvx; flow[..., 1] -= mvy
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1], angleInDegrees=True)
    active = (mag > motion_thresh).astype(np.uint8)
    bins = (ang / 45.0).astype(np.uint8) % 8         # 8방향 양자화
    score = np.zeros((rh, rw), np.float32)
    kernel = np.ones((15, 15), np.uint8)
    for b in range(8):
        mask = ((bins == b) & active).astype(np.uint8)
        score += cv2.dilate(mask, kernel)            # 방향별 누적 → 다양성 점수
    rmask = np.zeros((rh, rw), np.uint8)
    cv2.circle(rmask, (int(center[0]), int(center[1])), search_r, 1, -1)
    masked = score * rmask
    pk = float(masked.max())
    # 경쟁 솔버 방식 — 임계 후 최대 contour 중심(moments). 블롭 평균이 노이즈에 안정적.
    _, top = cv2.threshold(masked, vortex_thresh, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(top.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        Mo = cv2.moments(max(cnts, key=cv2.contourArea))
        if Mo['m00'] > 0:
            return (Mo['m10']/Mo['m00'], Mo['m01']/Mo['m00']), pk
    return None, pk


def run(name, motion_thresh=0.6, vortex_thresh=6.0, search_r=70, alpha=0.6, max_speed=40):
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
        print(f"{name}: GT 없음"); return

    # GT 연속 구간마다 재초기화(라벨 공백 구간 드리프트 격리) — 각 구간 첫 GT서 시작
    fis = sorted(gt)
    segs = []; cur = [fis[0]]
    for a, b in zip(fis, fis[1:]):
        if b - a <= 3:
            cur.append(b)
        else:
            segs.append(cur); cur = [b]
    segs.append(cur)

    errs = []; detail = []
    for seg in segs:
        center = list(gt[seg[0]])
        for i in range(seg[0] + 1, seg[-1] + 1):
            flow = cv2.calcOpticalFlowFarneback(grays[i-1], grays[i], None,
                                                0.5, 3, 15, 3, 5, 1.2, 0)
            res, peak = compute_vortex(flow, center, search_r, motion_thresh, vortex_thresh)
            if res is not None:
                # EMA + 속도 클램프
                nx = alpha * center[0] + (1-alpha) * res[0]
                ny = alpha * center[1] + (1-alpha) * res[1]
                d = math.hypot(nx-center[0], ny-center[1])
                if d > max_speed:
                    nx = center[0] + (nx-center[0])*max_speed/d
                    ny = center[1] + (ny-center[1])*max_speed/d
                center = [nx, ny]
            if i in gt:
                e = math.hypot(center[0]-gt[i][0], center[1]-gt[i][1])
                errs.append(e)
                ph = '백' if i <= 24 else '투' if i >= 56 else ' '
                detail.append((i, ph, e, peak, res is not None))
    print(f"\n=== {name} === vortex 추적 vs GT (mt{motion_thresh} vt{vortex_thresh} r{search_r})")
    for i, ph, e, peak, ok in detail:
        print(f"  f{i:3d}{ph} 오차{e:4.0f}px  peak{peak:4.1f} {'' if ok else 'vortex없음'}")
    if errs:
        print(f"  >>> 평균오차 {np.mean(errs):.0f}px  최대 {max(errs):.0f}  (GT {len(errs)}프레임)")


def run_continuous(name, motion_thresh=0.3, vortex_thresh=4.0, search_r=70,
                   alpha=0.6, max_speed=40, winsize=15):
    """재초기화 없이 첫 GT부터 끝까지 연속 추적 — 진짜 성능. (평균, 최대, n) 반환."""
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
    fis = sorted(gt); center = list(gt[fis[0]]); errs = []
    for i in range(fis[0] + 1, len(frs)):
        flow = cv2.calcOpticalFlowFarneback(grays[i-1], grays[i], None,
                                            0.5, 3, winsize, 3, 5, 1.2, 0)
        res, pk = compute_vortex(flow, center, search_r, motion_thresh, vortex_thresh)
        if res is not None:
            nx = alpha*center[0] + (1-alpha)*res[0]; ny = alpha*center[1] + (1-alpha)*res[1]
            d = math.hypot(nx-center[0], ny-center[1])
            if d > max_speed:
                nx = center[0]+(nx-center[0])*max_speed/d; ny = center[1]+(ny-center[1])*max_speed/d
            center = [nx, ny]
        if i in gt:
            errs.append(math.hypot(center[0]-gt[i][0], center[1]-gt[i][1]))
    return (np.mean(errs), max(errs), len(errs)) if errs else None


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "000_0615_035137")
