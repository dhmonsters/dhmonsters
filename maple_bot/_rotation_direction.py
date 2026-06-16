# 데칼 회전 방향 검증 — "시계방향" 가정이 운영상 정확한지.
# 각 트랙 trail에 원 fitting → 인접 프레임 중심기준 각도 변화의 부호로 방향 판정.
# 이미지 좌표(y 아래로 증가)에서 cross>0이 시계방향(화면상 시계).
import cv2, sys, os, json, math
import numpy as np
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
ROOT = os.path.dirname(os.path.abspath(__file__))


def fit_circle(pts):
    P = np.asarray(pts, dtype=np.float64)
    if len(P) < 3:
        return None
    x, y = P[:, 0], P[:, 1]
    A = np.column_stack([x, y, np.ones(len(P))])
    b = -(x ** 2 + y ** 2)
    try:
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    a_, b_, c_ = sol
    cx, cy = -a_ / 2, -b_ / 2
    r2 = (a_ / 2) ** 2 + (b_ / 2) ** 2 - c_
    if r2 <= 0:
        return None
    return cx, cy, math.sqrt(r2)


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

    bt = ByteTracker(); lockd = False; wp = None
    trail = defaultdict(list)
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        if lockd and big and wc:
            tg = next((t for t in bt._tracks if t.tid == bt._tid), None)
            if tg and (wc[0] - tg.x) ** 2 + (wc[1] - tg.y) ** 2 <= 1225:
                bt.nudge(wc[0], wc[1])
        bt.update(grays[i], dets)
        if not lockd:
            if wc and wp and (wc[0] - wp[0]) ** 2 + (wc[1] - wp[1]) ** 2 <= 225:
                bt.lock(wc[0], wc[1]); lockd = True
            if wc:
                wp = wc
        for t in bt._tracks:
            if t.miss == 0:
                trail[t.tid].append((i, float(t.x), float(t.y)))

    # ── 트랙별 회전 방향 판정 ──
    print(f"\n=== {name} === 데칼 회전 방향 검증")
    print("  tid  | n  span  중심          R  | CW샘플 CCW샘플 | 일관도(우세/총) | 판정")
    cw_total = ccw_total = 0
    track_dir = {}     # tid → 판정 결과
    long_tracks = []
    for tid, pts in trail.items():
        if tid == bt._tid or len(pts) < 10:
            continue
        xs = [p[1] for p in pts]; ys = [p[2] for p in pts]
        span = math.hypot(max(xs)-min(xs), max(ys)-min(ys))
        if span < 30:    # 거의 정지한 트랙은 방향 의미 없음
            continue
        f = fit_circle([(p[1], p[2]) for p in pts])
        if f is None:
            continue
        cx, cy, r = f
        # 인접 프레임 각도 변화의 부호 — cross product (이미지 좌표 y↓)
        cw = ccw = 0
        for k in range(1, len(pts)):
            x0, y0 = pts[k-1][1] - cx, pts[k-1][2] - cy
            x1, y1 = pts[k][1] - cx, pts[k][2] - cy
            # 변위가 너무 작으면 노이즈
            if math.hypot(x1-x0, y1-y0) < 1.0:
                continue
            cross = x0 * y1 - y0 * x1   # 이미지좌표(y↓): cross>0이면 화면상 시계방향
            if cross > 0: cw += 1
            else: ccw += 1
        if cw + ccw < 5:
            continue
        dominant = max(cw, ccw)
        consistency = dominant / (cw + ccw)
        direction = "시계(CW)" if cw > ccw else "반시계(CCW)"
        if consistency < 0.7:
            direction = "혼재"
        cw_total += cw; ccw_total += ccw
        track_dir[tid] = direction
        long_tracks.append((tid, len(pts), span, cx, cy, r, cw, ccw, consistency, direction))

    long_tracks.sort(key=lambda x: -x[1])
    for tid, n, span, cx, cy, r, cw, ccw, cons, d in long_tracks[:20]:
        print(f"  {tid:3d}  | {n:3d} {span:4.0f}  ({cx:4.0f},{cy:4.0f}) R{r:4.0f} | "
              f"{cw:5d}  {ccw:5d}   | {cons*100:4.0f}%        | {d}")

    print(f"\n  >>> 전체 인접쌍: 시계 {cw_total}회 / 반시계 {ccw_total}회  "
          f"(시계비율 {cw_total/(cw_total+ccw_total)*100:.1f}%)")
    cw_n = sum(1 for *_, d in long_tracks if d == "시계(CW)")
    ccw_n = sum(1 for *_, d in long_tracks if d == "반시계(CCW)")
    mix_n = sum(1 for *_, d in long_tracks if d == "혼재")
    print(f"  >>> 트랙 단위 판정({len(long_tracks)}개): 시계 {cw_n} / 반시계 {ccw_n} / 혼재 {mix_n}")
    if cw_n > 0 and ccw_n > 0:
        print(f"  >>> ★ 시계·반시계 트랙 공존 — '데칼은 시계방향' 가정 부정")
    elif mix_n / max(1, len(long_tracks)) > 0.3:
        print(f"  >>> ★ 혼재 트랙 비율 높음 — 방향 일관성 약함")
    else:
        print(f"  >>> 우세 방향 단일 — 가정 부분 확증")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "000_0615_035137")
