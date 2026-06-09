# VitShapeTracker(무동결 복구 루프) 오프라인 검증 — 실제 모듈 import해서 측정
import os, sys, math, time
import cv2, numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from core.vision.vit_shape_tracker import VitShapeTracker, acquire_white

MODEL = os.path.join(ROOT, 'models', 'transparent', 'vittrack.onnx')
dx1r, dx2r, dy1r, dy2r = 0.320, 0.678, 0.265, 0.728

def pink(roi):
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, np.array([140,80,80]), np.array([175,255,255]))
    c, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not c: return None
    b = max(c, key=cv2.contourArea); M = cv2.moments(b)
    if M['m00'] == 0 or cv2.contourArea(b) < 15: return None
    return (M['m10']/M['m00'], M['m01']/M['m00'])

def mask_cursor(img):
    # 오프라인 전용 — 핑크 커서 HSV inpaint (라이브는 GetCursorPos 경로)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, np.array([140,80,80]), np.array([175,255,255]))
    if cv2.countNonZero(m) == 0: return img
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_RECT, (9,9)))
    return cv2.inpaint(img, m, 3, cv2.INPAINT_TELEA)

def run(video, mode):
    cap = cv2.VideoCapture(video)
    W = int(cap.get(3)); H = int(cap.get(4))
    dx1=int(W*dx1r); dx2=int(W*dx2r); dy1=int(H*dy1r); dy2=int(H*dy2r)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 336)
    tr = VitShapeTracker(MODEL, recovery_mode=mode)
    inited = False; err = []; f = 335
    reinit_white = 0; t_upd = []
    while True:
        f += 1; ok, fr = cap.read()
        if not ok or f > 1300: break
        det = fr[dy1:dy2, dx1:dx2]; gt = pink(det); clean = mask_cursor(det)
        if not inited:
            bb = acquire_white(clean)
            if bb and bb[2] >= 20:
                tr.init(clean, bb); inited = True
            continue
        t0 = time.time()
        cx, cy, sc, acc = tr.update(clean)
        t_upd.append((time.time()-t0)*1000)
        if tr.needs_reacquire():
            bb = acquire_white(clean)
            if bb and bb[2] >= 20:
                tr.init(clean, bb); reinit_white += 1
        if gt:
            err.append(math.hypot(cx-gt[0], cy-gt[1]))
    cap.release()
    a = np.array(err)
    print(f'  [{mode:7s}] n={len(a)} '
          f'median={np.median(a):.0f} mean={a.mean():.0f} p90={np.percentile(a,90):.0f} '
          f'<40px:{(a<40).mean()*100:.0f}% <80px:{(a<80).mean()*100:.0f}%  '
          f'white재획득={reinit_white}  update={np.mean(t_upd):.1f}ms')
    return a

print('=== VitShapeTracker 복구 모드 비교 검증 ===')
print('(베이스라인 동결: median 45px, <40px 47%, <80px 57%)')
vid = os.path.join(ROOT, 'sample_transparent_shape.mp4')
for m in ('freeze', 'physics', 'inertia', 'frosted'):
    run(vid, m)
