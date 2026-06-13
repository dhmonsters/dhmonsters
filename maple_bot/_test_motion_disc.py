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
from core.vision.motion_discriminator import MotionDiscriminator, TargetTracker
from core.vision.vit_shape_tracker import acquire_white

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
    """현행 솔버 선택 로직 재현 — 강0.5 게이트내 우선, 약 게이트내.
    첫 잠금은 호출측이 acquire_white로 처리(전부검출 모델에선 score 최고가 데칼일 수 있음)."""
    strong = [c for c in cands if c[2] >= 0.50]
    d2 = lambda c: (c[0] - last[0]) ** 2 + (c[1] - last[1]) ** 2
    if last == (0, 0):
        return None
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
    white_prev = None   # 흰색 잠금 안정화(2프레임 연속) 비교용
    vel = (0.0, 0.0)    # pred 모드 — 속도 EMA
    prev_gray = None    # cbg 모드 — 배경 변위/동조 판정용
    prev_cands = []
    trk = TargetTracker()   # trk 모드 — 트랙 ID 타겟 락
    rvx = rvy = 0.0     # rel 모드 — 타겟 누적 상대속도(배경 대비)
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
        # 첫 잠금: 흰색 도형(밝기) — 시작 시 타겟만 유일하게 밝다 (사용자 설계 1단계).
        # 팝업 등장 프레임의 플래시 오인 방지: 2프레임 연속 같은 위치(15px)일 때만 잠금
        if last == (0, 0):
            wb = acquire_white(det)
            if wb and wb[2] >= 20:
                wc = (wb[0] + wb[2] / 2, wb[1] + wb[3] / 2)
                if white_prev is not None and math.hypot(wc[0] - white_prev[0],
                                                         wc[1] - white_prev[1]) <= 15:
                    last = wc
                white_prev = wc
        if mode.startswith("pg"):
            # combo60 + 게이트를 속도 크기에 비례 확장 — 급가속 타겟 이탈 방지
            ksp = float(mode[2:]) if len(mode) > 2 else 0.0
            if last == (0, 0):
                pick = None
            else:
                px, py = last[0] + vel[0], last[1] + vel[1]
                spd = math.hypot(vel[0], vel[1])
                gate = min(300, 110 + 12 * miss + ksp * spd)   # last 중심, 속도 비례 확장
                ing = [c for c in cands
                       if (c[0] - last[0]) ** 2 + (c[1] - last[1]) ** 2 <= gate * gate]
                if ing:
                    b = min(ing, key=lambda c: math.hypot(c[0] - px, c[1] - py) - 60.0 * c[2])
                    pick = (b[0], b[1])
                else:
                    pick = None
            if pick is not None and last != (0, 0):
                vel = (vel[0] * 0.6 + (pick[0] - last[0]) * 0.4,
                       vel[1] * 0.6 + (pick[1] - last[1]) * 0.4)
        elif mode.startswith("rel"):
            # 배경 대비 상대운동 매칭: 후보를 '타겟 누적 상대속도'와 일치하는지로 선택.
            # 점수 = 예측거리 + W·|후보의 타겟기준 상대변위 − 타겟 누적상대속도|
            W = float(mode[3:])
            gray = cv2.cvtColor(det, cv2.COLOR_BGR2GRAY).astype(np.float32)
            bx = by = 0.0
            if prev_gray is not None and gray.shape == prev_gray.shape:
                (bx, by), _ = cv2.phaseCorrelate(prev_gray, gray)
            if last == (0, 0):
                pick = None
            else:
                px, py = last[0] + vel[0], last[1] + vel[1]
                gate = min(280, 110 + 12 * miss)
                ing = [c for c in cands
                       if (c[0] - last[0]) ** 2 + (c[1] - last[1]) ** 2 <= gate * gate]
                def _mis(c):
                    rdx = (c[0] - last[0]) - bx
                    rdy = (c[1] - last[1]) - by
                    return math.hypot(rdx - rvx, rdy - rvy)
                if ing:
                    # combo60(예측거리−60·score) 베이스 + 상대운동 불일치 페널티
                    b = min(ing, key=lambda c: math.hypot(c[0] - px, c[1] - py)
                            - 60.0 * c[2] + W * _mis(c))
                    pick = (b[0], b[1])
                else:
                    pick = None
            if pick is not None and last != (0, 0):
                vel = (vel[0] * 0.6 + (pick[0] - last[0]) * 0.4,
                       vel[1] * 0.6 + (pick[1] - last[1]) * 0.4)
                rvx = rvx * 0.7 + ((pick[0] - last[0]) - bx) * 0.3
                rvy = rvy * 0.7 + ((pick[1] - last[1]) - by) * 0.3
            prev_gray = gray
        elif mode == "ud":
            # 사용자 설계: 평소 작은반경 이어가기(score 무관) + 놓침 시만 배경비동조 재획득
            gray = cv2.cvtColor(det, cv2.COLOR_BGR2GRAY).astype(np.float32)
            bx = by = 0.0
            if prev_gray is not None and gray.shape == prev_gray.shape:
                (bx, by), _ = cv2.phaseCorrelate(prev_gray, gray)
            if last == (0, 0):
                pick = None
            else:
                px, py = last[0] + vel[0], last[1] + vel[1]
                near = [c for c in cands
                        if (c[0] - px) ** 2 + (c[1] - py) ** 2 <= 60 ** 2]
                if near:
                    b = min(near, key=lambda c: (c[0] - px) ** 2 + (c[1] - py) ** 2)
                    pick = (b[0], b[1])
                else:
                    # 놓침 — 놓친 위치 80px 내에서 배경과 가장 다르게 움직인 후보
                    wide = [c for c in cands
                            if (c[0] - px) ** 2 + (c[1] - py) ** 2 <= 80 ** 2]
                    def _nonconf(c):
                        if not prev_cands:
                            return 0.0
                        pc = min(prev_cands,
                                 key=lambda p: (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2)
                        return math.hypot((c[0] - pc[0]) - bx, (c[1] - pc[1]) - by)
                    b = max(wide, key=_nonconf) if wide else None
                    pick = (b[0], b[1]) if b is not None else None
            if pick is not None and last != (0, 0):
                vel = (vel[0] * 0.6 + (pick[0] - last[0]) * 0.4,
                       vel[1] * 0.6 + (pick[1] - last[1]) * 0.4)
            prev_gray = gray
            prev_cands = cands
        elif mode == "trk":
            # 트랙 ID 타겟 락 — 매 프레임 트랙 갱신, 흰색 잠금 시 lock, 이후 그 ID 이어감
            gray = cv2.cvtColor(det, cv2.COLOR_BGR2GRAY).astype(np.float32)
            if last != (0, 0) and not trk.locked:
                trk.lock(last[0], last[1])
            r = trk.update(gray, cands)
            pick = r if (trk.locked and r is not None) else None
        elif mode == "disc":
            gray = cv2.cvtColor(det, cv2.COLOR_BGR2GRAY).astype(np.float32)
            gate = min(280, 110 + 12 * miss)
            lt = None if last == (0, 0) else last
            r = disc.update(gray, cands, lt, gate)
            pick = None if r is None else (r[0], r[1])
        elif mode.startswith("cmom"):
            # 결합 + 운동 관성: 점수 = 예측거리 − 60·score + γ·|새속도 − 기존속도|
            # 데칼 갈아타기는 위치가 튀어 속도 급변 → 페널티. 내 트랙 운동만 봄(데칼 조밀 무관).
            gam = float(mode[4:])
            if last == (0, 0):
                pick = None
            else:
                px, py = last[0] + vel[0], last[1] + vel[1]
                d2 = lambda c: (c[0] - last[0]) ** 2 + (c[1] - last[1]) ** 2
                gate = min(280, 110 + 12 * miss)
                ing = [c for c in cands if d2(c) <= gate * gate]
                def _sc(c):
                    base = math.hypot(c[0] - px, c[1] - py) - 60.0 * c[2]
                    nvx, nvy = c[0] - last[0], c[1] - last[1]
                    mom = math.hypot(nvx - vel[0], nvy - vel[1])
                    return base + gam * mom
                b = min(ing, key=_sc) if ing else None
                pick = None if b is None else (b[0], b[1])
            if pick is not None and last != (0, 0):
                vel = (vel[0] * 0.6 + (pick[0] - last[0]) * 0.4,
                       vel[1] * 0.6 + (pick[1] - last[1]) * 0.4)
        elif mode.startswith("cbg"):
            # 결합 + 배경동조 페널티: 점수 = 예측거리 − 60·score + μ·(배경따라 이동?)
            # 데칼은 '직전위치+배경변위=현재'라 conform=True → 페널티. 타겟은 상대이동이라 면제.
            mu = float(mode[3:])
            gray = cv2.cvtColor(det, cv2.COLOR_BGR2GRAY).astype(np.float32)
            bx = by = 0.0
            if prev_gray is not None and gray.shape == prev_gray.shape:
                (bx, by), _ = cv2.phaseCorrelate(prev_gray, gray)
            if last == (0, 0):
                pick = None
            else:
                px, py = last[0] + vel[0], last[1] + vel[1]
                d2 = lambda c: (c[0] - last[0]) ** 2 + (c[1] - last[1]) ** 2
                gate = min(280, 110 + 12 * miss)
                ing = [c for c in cands if d2(c) <= gate * gate]
                def _sc(c):
                    base = math.hypot(c[0] - px, c[1] - py) - 60.0 * c[2]
                    tx, ty = c[0] - bx, c[1] - by
                    conform = any((p[0] - tx) ** 2 + (p[1] - ty) ** 2 <= 8 ** 2
                                  for p in prev_cands)
                    return base + (mu if conform else 0.0)
                b = min(ing, key=_sc) if ing else None
                pick = None if b is None else (b[0], b[1])
            if pick is not None and last != (0, 0):
                vel = (vel[0] * 0.6 + (pick[0] - last[0]) * 0.4,
                       vel[1] * 0.6 + (pick[1] - last[1]) * 0.4)
            prev_gray = gray
            prev_cands = cands
        elif mode.startswith("combo"):
            # 결합: 점수 = 예측거리(px) - λ·score. 거리·score 둘 다 고려
            lam = float(mode[5:])
            if last == (0, 0):
                pick = None
            else:
                px, py = last[0] + vel[0], last[1] + vel[1]
                d2 = lambda c: (c[0] - last[0]) ** 2 + (c[1] - last[1]) ** 2
                gate = min(280, 110 + 12 * miss)
                ing = [c for c in cands if d2(c) <= gate * gate]
                if ing:
                    b = min(ing, key=lambda c: math.hypot(c[0] - px, c[1] - py) - lam * c[2])
                    pick = (b[0], b[1])
                else:
                    pick = None
            if pick is not None and last != (0, 0):
                vel = (vel[0] * 0.6 + (pick[0] - last[0]) * 0.4,
                       vel[1] * 0.6 + (pick[1] - last[1]) * 0.4)
        elif mode.startswith("nf"):
            # score 필터(노이즈 제거) + 예측위치 최근접 (score 순 아님) — 사용자 설계
            sthr = float(mode[2:]) if len(mode) > 2 else 0.5
            if last == (0, 0):
                pick = None
            else:
                px, py = last[0] + vel[0], last[1] + vel[1]
                gate = min(280, 110 + 12 * miss)
                ing = [c for c in cands if c[2] >= sthr
                       and (c[0] - last[0]) ** 2 + (c[1] - last[1]) ** 2 <= gate * gate]
                if ing:
                    b = min(ing, key=lambda c: (c[0] - px) ** 2 + (c[1] - py) ** 2)
                    pick = (b[0], b[1])
                else:
                    pick = None
            if pick is not None and last != (0, 0):
                vel = (vel[0] * 0.6 + (pick[0] - last[0]) * 0.4,
                       vel[1] * 0.6 + (pick[1] - last[1]) * 0.4)
        elif mode == "pred":
            # 속도 예측 선택 — 교차(겹침) 순간 데칼 갈아타기 방지
            if last == (0, 0):
                pick = None
            else:
                px, py = last[0] + vel[0], last[1] + vel[1]
                dp = lambda c: (c[0] - px) ** 2 + (c[1] - py) ** 2
                gate = min(280, 110 + 12 * miss)
                ing = [c for c in cands
                       if (c[0] - last[0]) ** 2 + (c[1] - last[1]) ** 2 <= gate * gate]
                pick = min(ing, key=dp)[:2] if ing else None   # score 우선 제거, 예측 최근접
            if pick is not None and last != (0, 0):
                vel = (vel[0] * 0.6 + (pick[0] - last[0]) * 0.4,
                       vel[1] * 0.6 + (pick[1] - last[1]) * 0.4)
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
    # 갈아타기 이벤트 — 전체 오차열에서 80px 이상 이탈한 '구간(run)' 수 (교차 갈아타기 지표)
    allerr = errs["전체"]
    switches = 0; inrun = False
    for e in allerr:
        if e >= 80 and not inrun:
            switches += 1; inrun = True
        elif e < 40:
            inrun = False
    print(f"--- {mode} (처리 {np.mean(t_upd):.1f}ms/f, 갈아타기 이벤트 {switches}회) ---")
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
    print("=== 트랙 ID 타겟 락 vs 현행 (combo60) ===")
    run(vid, "combo60")           # 기준 — score 가중(데칼 갈아타기)
    for s in (0.3, 0.5, 0.7):
        run(vid, f"nf{s}")        # score 필터 + 예측 최근접 (score 순 아님)
