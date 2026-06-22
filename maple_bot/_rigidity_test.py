# 배경 강체성 판정 — ID 무관 밀집 광류 기반. 강체 평행이동이면 전역 median 광류 뺀 잔차가 균일(0).
# 측정: ①median-병진 잔차 p90/|m| (작으면 균일=강체) ②affine 회전각·스케일 ③회전모델 ω가 잔차 추가설명 여부
import cv2, sys, os, glob, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.abspath(__file__))


def frame_pairs(name, n_pairs=12, gap=2):
    mp4 = os.path.join(ROOT, '_record_debug', name + '.mp4')
    if not os.path.exists(mp4):
        return None
    cap = cv2.VideoCapture(mp4); frs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frs.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
    cap.release()
    if len(frs) < 40:
        return None
    # 움직임 시작 후(준비4초~) 구간에서 균등 샘플
    start = min(30, len(frs) - gap - 1)
    idxs = np.linspace(start, len(frs) - gap - 1, n_pairs).astype(int)
    return [(frs[i], frs[i + gap]) for i in idxs], frs[0].shape


def analyze(name):
    pr = frame_pairs(name)
    if pr is None:
        print(f"{name:22s}  (녹화 없음/짧음)")
        return
    pairs, shp = pr
    H, W = shp
    ys, xs = np.mgrid[0:H, 0:W]
    res_ratios = []; rot_degs = []; scales = []; rot_gain = []
    for a, b in pairs:
        flow = cv2.calcOpticalFlowFarneback(a, b, None, 0.5, 3, 21, 3, 7, 1.5, 0)
        fx = flow[..., 0]; fy = flow[..., 1]
        mag = np.sqrt(fx * fx + fy * fy)
        # 텍스처 있는 배경 픽셀만(흐름 유효) — 너무 작은 흐름 제외
        valid = mag > 2.0
        if valid.sum() < 2000:
            continue
        mx = np.median(fx[valid]); my = np.median(fy[valid])
        m_mag = math.hypot(mx, my)
        if m_mag < 1.0:
            continue
        rx = fx - mx; ry = fy - my            # 병진 제거 잔차
        rmag = np.sqrt(rx * rx + ry * ry)
        # 타겟·노이즈 아웃라이어 배제: 잔차 p90(상위10%는 타겟 등)
        p90 = np.percentile(rmag[valid], 90)
        res_ratios.append(p90 / m_mag)
        # 회전모델 ω 적합: rx≈-ω(y-cy), ry≈ω(x-cx). 잔차를 ω가 얼마나 더 줄이나
        vv = valid & (rmag < np.percentile(rmag[valid], 95))   # 타겟 제외하고 회전 적합
        Y = ys[vv].astype(np.float32); X = xs[vv].astype(np.float32)
        cy0, cx0 = H / 2, W / 2
        A = np.stack([-(Y - cy0), (X - cx0)], 1).reshape(-1)     # [dydx] stacked
        bvec = np.concatenate([rx[vv], ry[vv]])
        Amat = np.concatenate([-(Y - cy0), (X - cx0)])[:, None]
        try:
            w, *_ = np.linalg.lstsq(Amat, bvec, rcond=None)
            omega = float(w[0])
        except Exception:
            omega = 0.0
        pred = np.concatenate([-(Y - cy0) * omega, (X - cx0) * omega])
        before = np.sqrt(np.mean(bvec ** 2))
        after = np.sqrt(np.mean((bvec - pred) ** 2))
        rot_gain.append(1 - after / max(before, 1e-6))      # 회전이 잔차 줄인 비율
        rot_degs.append(math.degrees(omega))                 # 프레임당 회전각(근사)
        # affine(부분) — 회전/스케일 직접
        pts0 = np.stack([xs[vv][::50], ys[vv][::50]], 1).astype(np.float32)
        pts1 = pts0 + np.stack([fx[vv][::50], fy[vv][::50]], 1)
        if len(pts0) >= 10:
            M, _ = cv2.estimateAffinePartial2D(pts0, pts1, method=cv2.RANSAC)
            if M is not None:
                sc = math.hypot(M[0, 0], M[1, 0]); ang = math.degrees(math.atan2(M[1, 0], M[0, 0]))
                scales.append(sc); rot_degs[-1] = ang
    if not res_ratios:
        print(f"{name:22s}  (광류 유효 부족)")
        return
    rr = np.median(res_ratios); rg = np.median(rot_gain) if rot_gain else 0
    rd = np.median([abs(d) for d in rot_degs]) if rot_degs else 0
    sc = np.median(scales) if scales else 1.0
    verdict = ("강체-병진" if rr < 0.30 and rg < 0.25 else
               "회전성분有" if rg >= 0.25 else
               "비강체/잡음")
    print(f"{name:22s} 잔차비p90/|m| {rr:.2f}  회전이득 {rg:+.2f}  "
          f"|회전각|/f {rd:4.1f}°  스케일 {sc:.3f}  → {verdict}")


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(os.path.basename(p)[:-4]
                                   for p in glob.glob(os.path.join(ROOT, '_record_debug', '*.mp4')))
    print(f"{'영상':22s} {'잔차비(작을수록강체)':>10s}  {'회전이득(클수록회전)':>10s}  "
          f"{'|회전각|/f':>8s}  {'스케일':>5s}")
    print("-" * 100)
    for n in names:
        try:
            analyze(n)
        except Exception as e:
            print(f"{n:22s}  ERROR {type(e).__name__}: {e}")
