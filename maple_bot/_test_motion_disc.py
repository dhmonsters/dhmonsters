# 모션 분별 추적 오프라인 검증 — 현행 선택(강0.5+게이트) vs MotionDiscriminator 비교
# 합격: 전체 <80px >= 88% AND 투명후기 <80px 현행 대비 명확 개선 AND max <= 300px
import os, sys, math, time
import cv2, numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from core.shape_yolo import ShapeYolo
from core.vision.motion_discriminator import MotionDiscriminator

dx1r, dx2r, dy1r, dy2r = 0.320, 0.678, 0.265, 0.728


def pink(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, np.array([140, 80, 80]), np.array([175, 255, 255]))
    c, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not c:
        return None
    b = max(c, key=cv2.contourArea)
    M = cv2.moments(b)
    if M["m00"] == 0 or cv2.contourArea(b) < 15:
        return None
    return (M["m10"] / M["m00"], M["m01"] / M["m00"])


def seg_of(f):
    if f <= 450:
        return "흰~페이드"
    if f <= 700:
        return "투명초기"
    return "투명후기"


def select_current(cands, last, miss):
    """현행 솔버 선택 로직 재현 — 강0.5 게이트내 우선, 약 게이트내, 첫검출 강최고."""
    strong = [c for c in cands if c[2] >= 0.50]
    d2 = lambda c: (c[0] - last[0]) ** 2 + (c[1] - last[1]) ** 2
    if last == (0, 0):
        return max(strong, key=lambda c: c[2])[:2] if strong else None
    gate = min(280, 110 + 12 * miss)
    ing = [c for c in cands if d2(c) <= gate * gate]
    ing_strong = [c for c in ing if c[2] >= 0.50]
    if ing_strong:
        return min(ing_strong, key=d2)[:2]
    if ing:
        return min(ing, key=d2)[:2]
    return None


def run(video, mode):
    yolo = ShapeYolo()
    if not yolo.enabled:
        print("모델 없음"); return None
    disc = MotionDiscriminator()
    cap = cv2.VideoCapture(video)
    W, H = int(cap.get(3)), int(cap.get(4))
    dx1, dx2 = int(W * dx1r), int(W * dx2r)
    dy1, dy2 = int(H * dy1r), int(H * dy2r)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 336)
    f = 335
    last = (0, 0)
    miss = 0
    errs = {"흰~페이드": [], "투명초기": [], "투명후기": [], "전체": []}
    t_upd = []
    while True:
        f += 1
        ok, fr = cap.read()
        if not ok or f > 1300:
            break
        det = fr[dy1:dy2, dx1:dx2]
        gt = pink(det)
        cands = yolo.detect_all(det, score_thr=0.10)
        t0 = time.time()
        if mode == "disc":
            gray = cv2.cvtColor(det, cv2.COLOR_BGR2GRAY).astype(np.float32)
            gate = min(280, 110 + 12 * miss)
            lt = None if last == (0, 0) else last
            r = disc.update(gray, cands, lt, gate)
            # 첫 검출은 강한 후보만 (현행과 동일 — 시작 오염 방지)
            if last == (0, 0) and (r is None or r[2] < 0.1):
                strong = [c for c in cands if c[2] >= 0.50]
                r = (strong and max(strong, key=lambda c: c[2])[:2]) or None
                if r:
                    r = (r[0], r[1], 0.0)
            pick = None if r is None else (r[0], r[1])
        else:
            pick = select_current(cands, last, miss)
        t_upd.append((time.time() - t0) * 1000)
        if pick is not None:
            track = pick
            miss = 0
        elif last != (0, 0) and miss < 15:
            track = last
            miss += 1
        else:
            track = last if last != (0, 0) else None
            miss += 1
        if track is not None:
            last = track
        if gt is not None and track is not None:
            e = math.hypot(track[0] - gt[0], track[1] - gt[1])
            errs[seg_of(f)].append(e)
            errs["전체"].append(e)
    cap.release()
    print(f"--- {mode} (처리 {np.mean(t_upd):.1f}ms/f) ---")
    out = {}
    for k in ("흰~페이드", "투명초기", "투명후기", "전체"):
        a = np.array(errs[k])
        if len(a) == 0:
            continue
        out[k] = a
        print(f"  {k:8s} n={len(a):4d} median={np.median(a):5.0f} "
              f"<40px:{(a < 40).mean() * 100:3.0f}% <80px:{(a < 80).mean() * 100:3.0f}% "
              f"max={a.max():4.0f}")
    return out


if __name__ == "__main__":
    vid = os.path.join(ROOT, "sample_transparent_shape.mp4")
    print("=== 모션 분별 vs 현행 선택 ===")
    cur = run(vid, "current")
    dis = run(vid, "disc")
    if cur and dis:
        a, b = cur["전체"], dis["전체"]
        l_cur, l_dis = cur["투명후기"], dis["투명후기"]
        ok80 = (b < 80).mean() >= 0.88
        late_better = (l_dis < 80).mean() > (l_cur < 80).mean()
        no_drift = b.max() <= 300
        print(f"\n[게이트] 전체<80px {(b<80).mean()*100:.0f}%(기준 88) → {'합격' if ok80 else '미달'}"
              f" | 투명후기 개선 {(l_cur<80).mean()*100:.0f}%→{(l_dis<80).mean()*100:.0f}% → {'합격' if late_better else '미달'}"
              f" | max {b.max():.0f}(기준 300) → {'합격' if no_drift else '미달'}")
