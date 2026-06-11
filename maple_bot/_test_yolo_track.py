# 학습된 ShapeYolo 오프라인 검증 — 샘플 영상 핑크 GT 대비 YOLO 단독/융합 측정
# 합격 기준: median < 40px AND <80px >= 90% (residual 43px/88% 상회 목표)
import os, sys, math, time
import cv2, numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from core.shape_yolo import ShapeYolo
from core.vision.vit_shape_tracker import VitShapeTracker, acquire_white

MODEL = os.path.join(ROOT, 'models', 'transparent', 'vittrack.onnx')
dx1r, dx2r, dy1r, dy2r = 0.320, 0.678, 0.265, 0.728
GATE = 120.0   # planet_solver와 동일 — 직전 위치 기준 후보 채택 반경

def pink(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, np.array([140,80,80]), np.array([175,255,255]))
    c, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not c: return None
    b = max(c, key=cv2.contourArea); M = cv2.moments(b)
    if M['m00'] == 0 or cv2.contourArea(b) < 15: return None
    return (M['m10']/M['m00'], M['m01']/M['m00'])

def mask_cursor(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, np.array([140,80,80]), np.array([175,255,255]))
    if cv2.countNonZero(m) == 0: return img, None
    md = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_RECT, (9,9)))
    return cv2.inpaint(img, md, 3, cv2.INPAINT_TELEA), md

def report(tag, err, det_n, total, t_ms):
    a = np.array(err)
    ok40 = (a < 40).mean() * 100
    ok80 = (a < 80).mean() * 100
    md = np.median(a)
    verdict = "합격" if (md < 40 and ok80 >= 90) else "미달"
    print(f'  [{tag:10s}] n={len(a)} median={md:.0f}px p95={np.percentile(a,95):.0f} '
          f'<40px:{ok40:.0f}% <80px:{ok80:.0f}%  검출률={det_n/max(1,total)*100:.0f}%  '
          f'detect={t_ms:.1f}ms  → {verdict}')

def run(video):
    yolo = ShapeYolo()
    if not yolo.enabled:
        print('ShapeYolo 모델 없음 (models/shape_yolo.param/.bin). 학습 후 다시 실행하세요.')
        return

    cap = cv2.VideoCapture(video)
    W = int(cap.get(3)); H = int(cap.get(4))
    dx1=int(W*dx1r); dx2=int(W*dx2r); dy1=int(H*dy1r); dy2=int(H*dy2r)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 336)

    from core.vision.vit_shape_tracker import ResidualMotionDetector
    resd = ResidualMotionDetector()
    inited = False; f = 335
    last = None                 # 융합 추적의 직전 위치(게이트 기준)
    miss = 0                    # 연속 미채택 (게이트 확장용)
    oog_pos = None; oog_run = 0 # 게이트 밖 강한 후보 지속 추적(스냅)
    err_solo = []; err_fused = []
    det_n = 0; res_n = 0; total = 0; t_det = []
    while True:
        f += 1; ok, fr = cap.read()
        if not ok or f > 1300: break
        det = fr[dy1:dy2, dx1:dx2]; gt = pink(det); clean, cmask = mask_cursor(det)
        if not inited:
            bb = acquire_white(clean)
            if bb and bb[2] >= 20:
                inited = True
                last = (bb[0] + bb[2]/2, bb[1] + bb[3]/2)
            continue
        total += 1
        # planet_solver와 동일 — 잔차 상태 매 프레임 갱신 + YOLO 2단 게이트 + 잔차 보정
        gray = cv2.cvtColor(det, cv2.COLOR_BGR2GRAY).astype(np.float32)
        resd.update(gray, cmask)
        t0 = time.time()
        cands = yolo.detect_all(det, score_thr=0.10)
        t_det.append((time.time()-t0)*1000)
        strong = [c for c in cands if c[2] >= 0.50]
        d = lambda c: math.hypot(c[0]-last[0], c[1]-last[1])
        gate = min(280, 110 + 12 * miss)
        ing = [c for c in cands if d(c) <= gate]
        ing_strong = [c for c in ing if c[2] >= 0.50]
        best = None
        if ing_strong:
            best = min(ing_strong, key=d)[:2]
        elif ing:
            best = min(ing, key=d)[:2]
        elif strong:
            og = min(strong, key=d)
            if oog_pos is not None and math.hypot(og[0]-oog_pos[0], og[1]-oog_pos[1]) <= 60:
                oog_run += 1
            else:
                oog_run = 1
            oog_pos = (og[0], og[1])
            if oog_run >= 20:
                best = (og[0], og[1])
        if best is not None:
            det_n += 1
            fused = best
            miss = 0; oog_pos = None; oog_run = 0
        else:
            miss += 1
            rf = resd.find(last[0], last[1])
            if rf is not None:
                rcx, rcy, _ = rf
                rd = math.hypot(rcx-last[0], rcy-last[1])
                if rd > 30:
                    rcx = last[0] + (rcx-last[0])*30/rd
                    rcy = last[1] + (rcy-last[1])*30/rd
                fused = (rcx, rcy)
                res_n += 1
            else:
                fused = last   # 잔차 침묵 — 직전 위치 유지
        last = fused
        if gt:
            err_fused.append(math.hypot(fused[0]-gt[0], fused[1]-gt[1]))
            if best is not None:
                err_solo.append(math.hypot(best[0]-gt[0], best[1]-gt[1]))
    cap.release()
    print(f"(잔차 보정 사용 프레임: {res_n}/{total})")
    print('=== ShapeYolo 오프라인 검증 (기준: residual 융합 median 43px <80px 88%) ===')
    report('YOLO검출만', err_solo, det_n, total, np.mean(t_det))
    report('YOLO+폴백', err_fused, det_n, total, np.mean(t_det))

if __name__ == '__main__':
    run(os.path.join(ROOT, 'sample_transparent_shape.mp4'))
