# 커서 비상관화 합격 게이트 — lure 오검출 / 커서제거 생존 / 원본 생존 3종 측정
# 기준: lure 강한 오검출 <=10%, 커서제거 GT 강한 유지 >=80%, 원본 GT 강한 유지 >=95%
import os, sys, glob, math, random
import cv2, numpy as np

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.shape_yolo import ShapeYolo


def load_label(p):
    shape = None; mouse = None
    for l in open(p, encoding="utf-8"):
        t = l.split()
        if not t:
            continue
        if t[0] == "1" and shape is None:
            shape = tuple(float(v) for v in t[1:5])
        if t[0] == "0" and mouse is None:
            mouse = tuple(float(v) for v in t[1:5])
    return shape, mouse


def main():
    yolo = ShapeYolo()
    if not yolo.enabled:
        print("모델 없음"); return
    rng = random.Random(7)
    imgs = sorted(glob.glob("dataset_yolo/images/val/*.png"))
    rng.shuffle(imgs)

    # 커서 패치 풀
    patches = []
    for ip in imgs:
        lp = ip.replace("images", "labels").replace(".png", ".txt")
        if not os.path.exists(lp):
            continue
        _, mo = load_label(lp)
        if mo is None:
            continue
        im = cv2.imread(ip); h, w = im.shape[:2]
        mx, my, mw, mh = mo[0]*w, mo[1]*h, mo[2]*w, mo[3]*h
        x1, y1, x2, y2 = int(mx-mw/2), int(my-mh/2), int(mx+mw/2), int(my+mh/2)
        if x2-x1 > 8 and y2-y1 > 8 and x1 >= 0 and y1 >= 0 and x2 <= w and y2 <= h:
            patches.append(im[y1:y2, x1:x2].copy())
        if len(patches) >= 10:
            break

    n = 0; lure_strong = 0; rm_kept = 0; orig_kept = 0
    for ip in imgs[:80]:
        lp = ip.replace("images", "labels").replace(".png", ".txt")
        if not os.path.exists(lp):
            continue
        sh, mo = load_label(lp)
        if sh is None or mo is None:
            continue
        im = cv2.imread(ip); h, w = im.shape[:2]
        gx, gy = sh[0]*w, sh[1]*h
        n += 1

        # 1) 원본 GT 강한 검출
        if any(math.hypot(c[0]-gx, c[1]-gy) < 50 and c[2] >= 0.5
               for c in yolo.detect_all(im, score_thr=0.2)):
            orig_kept += 1

        # 2) lure — 가짜 커서를 GT에서 150px 이상 떨어진 곳에 합성
        for _ in range(20):
            px, py = rng.randint(40, w-40), rng.randint(40, h-40)
            if math.hypot(px-gx, py-gy) >= 150:
                break
        pa = patches[rng.randrange(len(patches))]
        ph, pw = pa.shape[:2]
        x1, y1 = max(0, px-pw//2), max(0, py-ph//2)
        im2 = im.copy()
        im2[y1:y1+ph, x1:x1+pw] = pa[:im2.shape[0]-y1, :im2.shape[1]-x1]
        if any(math.hypot(c[0]-px, c[1]-py) < 60 and c[2] >= 0.5
               for c in yolo.detect_all(im2, score_thr=0.2)):
            lure_strong += 1

        # 3) 커서 제거 후 GT 생존
        mx, my, mw, mh = mo[0]*w, mo[1]*h, mo[2]*w, mo[3]*h
        mask = np.zeros((h, w), np.uint8)
        cv2.rectangle(mask, (int(mx-mw/2-4), int(my-mh/2-4)),
                      (int(mx+mw/2+4), int(my+mh/2+4)), 255, -1)
        clean = cv2.inpaint(im, mask, 5, cv2.INPAINT_TELEA)
        if any(math.hypot(c[0]-gx, c[1]-gy) < 50 and c[2] >= 0.5
               for c in yolo.detect_all(clean, score_thr=0.2)):
            rm_kept += 1

    def verdict(v, op, t):
        ok = (v <= t) if op == "<=" else (v >= t)
        return "합격" if ok else "미달"

    print(f"n={n}  (이전 모델: lure 71% / 커서제거 45% / 원본 100%)")
    print(f"1) 원본 GT 강한 유지   : {orig_kept/n*100:5.0f}%  (기준 >=95%) → {verdict(orig_kept/n*100,'>=',95)}")
    print(f"2) lure 강한 오검출    : {lure_strong/n*100:5.0f}%  (기준 <=10%) → {verdict(lure_strong/n*100,'<=',10)}")
    print(f"3) 커서제거 GT 강한 유지: {rm_kept/n*100:5.0f}%  (기준 >=80%) → {verdict(rm_kept/n*100,'>=',80)}")


if __name__ == "__main__":
    main()
