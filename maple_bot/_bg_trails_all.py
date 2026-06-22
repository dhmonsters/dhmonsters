# 전 녹화 데칼 trail 몽타주 — 각 판 궤도를 한 장 그리드로. 데칼 원 fitting 중심(노란점)도 표시.
# 목적: '단일 축 회전(중심 한 점 수렴)' vs '원형 평행이동(중심 흩어짐)' 육안 확인.
import cv2, os, math, glob
import numpy as np
from _bg_revolution_check import extract_trails
from _bg_rotation_probe import fit_circle
ROOT = os.path.dirname(os.path.abspath(__file__))


def render(name, thumb_w=340):
    trails, wh, tid_t = extract_trails(name)
    if trails is None:
        return None
    W, H = wh
    canvas = np.full((H, W, 3), 30, dtype=np.uint8)
    rng = np.random.RandomState(42)
    centers = []
    for tid, pts in trails.items():
        if len(pts) < 5:
            continue
        col = tuple(int(c) for c in rng.randint(60, 256, 3))
        pp = np.array([(int(p[1]), int(p[2])) for p in pts], dtype=np.int32)
        for j in range(1, len(pp)):
            cv2.line(canvas, tuple(pp[j - 1]), tuple(pp[j]), col, 1, cv2.LINE_AA)
        # 데칼 원 중심
        if tid != tid_t and len(pts) >= 15:
            xs = [p[1] for p in pts]; ys = [p[2] for p in pts]
            span = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
            if span >= 40:
                f = fit_circle([(p[1], p[2]) for p in pts])
                if f and f[2] < 2000:
                    centers.append((f[0], f[1]))
    # 데칼 중심들(노란점) + 평균중심(시안 큰점)
    for cx, cy in centers:
        if 0 <= cx < W and 0 <= cy < H:
            cv2.circle(canvas, (int(cx), int(cy)), 3, (0, 220, 220), -1)
    if centers:
        mx = int(np.mean([c[0] for c in centers])); my = int(np.mean([c[1] for c in centers]))
        if 0 <= mx < W and 0 <= my < H:
            cv2.drawMarker(canvas, (mx, my), (255, 255, 0), cv2.MARKER_CROSS, 22, 2)
    # 타겟 trail 빨강 강조
    if tid_t is not None and tid_t in trails:
        pp = np.array([(int(p[1]), int(p[2])) for p in trails[tid_t]], dtype=np.int32)
        for j in range(1, len(pp)):
            cv2.line(canvas, tuple(pp[j - 1]), tuple(pp[j]), (0, 0, 255), 2, cv2.LINE_AA)
    # 개별 풀해상도 PNG 저장(035137 스타일 + 노란 중심점)
    cv2.imwrite(os.path.join(ROOT, f"_bg_trails_{name}.png"), canvas)
    thumb = cv2.resize(canvas, (thumb_w, int(H * thumb_w / W)))
    cv2.putText(thumb, name[4:], (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(thumb, f"decals:{len(centers)}", (4, thumb.shape[0] - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 220, 220), 1, cv2.LINE_AA)
    return thumb


def main():
    names = sorted(os.path.basename(p)[:-4]
                   for p in glob.glob(os.path.join(ROOT, '_record_debug', '*.mp4')))
    thumbs = []
    for n in names:
        try:
            t = render(n)
            if t is not None:
                thumbs.append(t)
                print("rendered", n)
        except Exception as e:
            print("skip", n, type(e).__name__, e)
    if not thumbs:
        print("no thumbs"); return
    th, tw = thumbs[0].shape[:2]
    cols = 5
    rows = (len(thumbs) + cols - 1) // cols
    pad = 6
    grid = np.full((rows * (th + pad) + pad, cols * (tw + pad) + pad, 3), 15, dtype=np.uint8)
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        y = pad + r * (th + pad); x = pad + c * (tw + pad)
        grid[y:y + th, x:x + tw] = t
    out = os.path.join(ROOT, "_bg_trails_ALL.png")
    cv2.imwrite(out, grid)
    print("saved", out, grid.shape)


if __name__ == "__main__":
    main()
