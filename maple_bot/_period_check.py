# 배경 주기성 측정 — D(t)=밀집광류median 누적. 강체 원형평행이동이면 D가 원을 그리고
# 한 바퀴 후 원점으로 닫힘(주기 T). 준비4초 길이와 T 비교, START 전후 같은 원 반복인지 확인.
import cv2, json, sys, os, glob, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
ROOT = os.path.dirname(os.path.abspath(__file__))


def compute_D(frs):
    """프레임별 밀집광류 median 누적 = 전역 배경이동 D(t). (절반 다운스케일 속도)"""
    D = [np.zeros(2)]
    prev = cv2.cvtColor(cv2.resize(frs[0], None, fx=0.5, fy=0.5), cv2.COLOR_BGR2GRAY)
    for i in range(1, len(frs)):
        cur = cv2.cvtColor(cv2.resize(frs[i], None, fx=0.5, fy=0.5), cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(prev, cur, None, 0.5, 3, 21, 3, 7, 1.5, 0)
        mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
        v = (np.median(flow[..., 0][mag > 1.5]) if (mag > 1.5).sum() > 500 else 0.0,
             np.median(flow[..., 1][mag > 1.5]) if (mag > 1.5).sum() > 500 else 0.0)
        D.append(D[-1] + np.array([v[0] * 2, v[1] * 2]))   # ×2 = 원해상도 보정
        prev = cur
    return np.asarray(D)


def analyze(name):
    jl = f'{ROOT}/_record_debug/{name}.jsonl'
    if not os.path.exists(jl):
        return None
    cap = cv2.VideoCapture(f'{ROOT}/_record_debug/{name}.mp4'); frs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frs.append(f)
    cap.release()
    if len(frs) < 30:
        return None
    # 준비 종료(START) = big 흰색 사라지는 프레임
    prep_end = None
    for i, f in enumerate(frs):
        wb = acquire_white(f)
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if big:
            prep_end = i
    prep_end = (prep_end + 1) if prep_end else 30
    D = compute_D(frs)
    # 원 fitting(전체) + 중심대비 각도 누적으로 회전수·주기 측정
    from _bg_rotation_probe import fit_circle
    fitc = fit_circle([(p[0], p[1]) for p in D])
    if fitc is None:
        return None
    cx, cy, R, rms = fitc
    ang = np.unwrap(np.arctan2(D[:, 1] - cy, D[:, 0] - cx))
    # 준비 구간 회전량(도)
    prep_sweep = math.degrees(abs(ang[min(prep_end, len(ang)-1)] - ang[0]))
    total_sweep = math.degrees(abs(ang[-1] - ang[0]))
    # 주기 = 360° 도는 데 걸린 프레임(준비구간 평균 각속도 기준)
    w = abs(ang[min(prep_end, len(ang)-1)] - ang[0]) / max(prep_end, 1)  # rad/f
    T = (2 * math.pi / w) if w > 1e-4 else 0
    # 닫힘: 준비 끝에서 D가 시작(0) 근처로 돌아오나
    closure = float(np.hypot(D[min(prep_end, len(D)-1), 0], D[min(prep_end, len(D)-1), 1]))
    return dict(name=name, prep_end=prep_end, nfr=len(frs), R=R, rms=rms,
                prep_sweep=prep_sweep, total_sweep=total_sweep, T=T, closure=closure, D=D)


def main():
    names = sys.argv[1:] or sorted(os.path.basename(d) for d in
                                   glob.glob(os.path.join(ROOT, '_gt_frames', '*')) if os.path.isdir(d))
    print(f"{'영상':22s} {'준비f':>5s} {'전체f':>5s} {'반지름':>5s} "
          f"{'준비회전°':>7s} {'전체회전°':>7s} {'주기T(f)':>7s} {'닫힘px':>6s}")
    print("-" * 95)
    plots = []
    for n in names:
        try:
            r = analyze(n)
        except Exception as e:
            print(f"{n}: ERR {e}"); continue
        if not r:
            print(f"{n}: 데이터부족"); continue
        print(f"{r['name']:22s} {r['prep_end']:5d} {r['nfr']:5d} {r['R']:5.0f} "
              f"{r['prep_sweep']:7.0f} {r['total_sweep']:7.0f} {r['T']:7.1f} {r['closure']:6.0f}")
        # D 궤적 플롯(준비=주황, START후=시안)
        D = r['D']; pe = r['prep_end']
        cv = np.full((260, 260, 3), 25, np.uint8)
        off = np.array([130, 130]) - D.mean(0)
        P = (D + off).astype(int)
        for k in range(1, len(P)):
            col = (0, 165, 255) if k <= pe else (255, 200, 0)
            cv2.line(cv, tuple(P[k-1]), tuple(P[k]), col, 1, cv2.LINE_AA)
        cv2.circle(cv, tuple(P[0]), 4, (255, 255, 255), -1)        # 시작점(흰)
        cv2.putText(cv, n[4:], (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
        cv2.putText(cv, f"T{r['T']:.0f} sweep{r['prep_sweep']:.0f}", (4, 252),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        plots.append(cv)
    if plots:
        cols = 4; rn = (len(plots)+cols-1)//cols; pad = 4; s = 260
        grid = np.full((rn*(s+pad)+pad, cols*(s+pad)+pad, 3), 15, np.uint8)
        for k, p in enumerate(plots):
            rr, cc = divmod(k, cols)
            grid[pad+rr*(s+pad):pad+rr*(s+pad)+s, pad+cc*(s+pad):pad+cc*(s+pad)+s] = p
        cv2.imwrite(os.path.join(ROOT, '_period_check.png'), grid)
        print(f"\nD 궤적 플롯(준비=주황, START후=시안) → _period_check.png")


if __name__ == "__main__":
    main()
