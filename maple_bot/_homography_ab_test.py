# 호모그래피 배경정렬 A/B 검증 — A:검출점 재투영오차(점기반,희미함무관) vs B:픽셀잔차.
# 하드판에서 타겟이 데칼 대비 얼마나 분리되나(순위·비율) 측정해 승자 채택.
import cv2, json, sys, os, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
orb = cv2.ORB_create(2000)
bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)


def nn_match(prev, cur, gate=45.0):
    """cur 각 점 → prev 최근접(gate 내). (cur_idx, prev_pt) 리스트."""
    pairs = []
    for j in range(cur.shape[0]):
        d2 = (prev[:, 0] - cur[j, 0]) ** 2 + (prev[:, 1] - cur[j, 1]) ** 2
        k = int(np.argmin(d2))
        if d2[k] <= gate ** 2:
            pairs.append((j, prev[k]))
    return pairs


def patch(field, x, y, r=8):
    H, W = field.shape
    x0, x1 = max(0, int(x) - r), min(W, int(x) + r)
    y0, y1 = max(0, int(y) - r), min(H, int(y) + r)
    p = field[y0:y1, x0:x1]
    return float(np.mean(p)) if p.size else 0.0


def run(name):
    rows = [json.loads(l) for l in open(f'{ROOT}/_record_debug/{name}.jsonl', encoding='utf-8')]
    cap = cv2.VideoCapture(f'{ROOT}/_record_debug/{name}.mp4'); frs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frs.append(f)
    cap.release()
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frs]
    gt = load_gt(name, min_f=0)
    a_ranks = []; a_ratios = []   # A: 검출점 재투영오차
    b_ranks = []; b_ratios = []   # B: 픽셀 잔차
    for i in sorted(gt):
        if i == 0 or i - 1 >= len(frs) or i >= len(frs):
            continue
        cur = np.asarray([[c[0], c[1]] for c in rows[i]['cands'] if c[2] >= 0.1], float)
        prev = np.asarray([[c[0], c[1]] for c in rows[i - 1]['cands'] if c[2] >= 0.1], float)
        if cur.shape[0] < 5 or prev.shape[0] < 5:
            continue
        gx, gy = gt[i]
        tj = int(np.argmin((cur[:, 0] - gx) ** 2 + (cur[:, 1] - gy) ** 2))
        if math.hypot(cur[tj, 0] - gx, cur[tj, 1] - gy) > 25:
            continue   # 타겟 미검출 프레임 제외

        # ---- A: 검출점 RANSAC 호모그래피 → 재투영오차 ----
        pairs = nn_match(prev, cur)
        if len(pairs) >= 8:
            src = np.float32([p for _, p in pairs]).reshape(-1, 1, 2)
            dst = np.float32([cur[j] for j, _ in pairs]).reshape(-1, 1, 2)
            Hm, _ = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
            if Hm is not None:
                proj = cv2.perspectiveTransform(src, Hm).reshape(-1, 2)
                err = {pairs[k][0]: float(np.hypot(proj[k, 0] - cur[pairs[k][0], 0],
                                                   proj[k, 1] - cur[pairs[k][0], 1]))
                       for k in range(len(pairs))}
                if tj in err:
                    te = err[tj]
                    others = [v for j, v in err.items() if j != tj]
                    if others:
                        rank = 1 + sum(1 for v in others if v > te)
                        a_ranks.append((rank, len(others) + 1))
                        a_ratios.append(te / (np.median(others) + 1e-6))

        # ---- B: 픽셀 호모그래피 정렬 → 잔차 ----
        ka, da = orb.detectAndCompute(grays[i - 1], None)
        kb, db = orb.detectAndCompute(grays[i], None)
        if da is not None and db is not None and len(ka) >= 10 and len(kb) >= 10:
            m = bf.match(da, db); m = sorted(m, key=lambda x: x.distance)[:300]
            if len(m) >= 8:
                pa = np.float32([ka[x.queryIdx].pt for x in m]).reshape(-1, 1, 2)
                pb = np.float32([kb[x.trainIdx].pt for x in m]).reshape(-1, 1, 2)
                Hp, _ = cv2.findHomography(pa, pb, cv2.RANSAC, 4.0)
                if Hp is not None:
                    warp = cv2.warpPerspective(grays[i - 1], Hp, (grays[i].shape[1], grays[i].shape[0]))
                    res = cv2.GaussianBlur(cv2.absdiff(grays[i], warp).astype(np.float32), (0, 0), 3)
                    tv = patch(res, gx, gy)
                    dv = [patch(res, cur[j, 0], cur[j, 1]) for j in range(cur.shape[0])
                          if j != tj and math.hypot(cur[j, 0] - gx, cur[j, 1] - gy) > 25]
                    if dv:
                        rank = 1 + sum(1 for v in dv if v > tv)
                        b_ranks.append((rank, len(dv) + 1))
                        b_ratios.append(tv / (np.median(dv) + 1e-6))

    def fmt(ranks, ratios):
        if not ranks:
            return "측정불가"
        top1 = sum(1 for r, n in ranks if r == 1)
        avgrank = np.mean([r for r, _ in ranks])
        return f"타겟1위 {top1}/{len(ranks)}, 평균순위 {avgrank:.1f}, 위반비 {np.median(ratios):.1f}x"
    print(f"[{name}]")
    print(f"  A 검출점: {fmt(a_ranks, a_ratios)}")
    print(f"  B 픽셀  : {fmt(b_ranks, b_ratios)}")


def main():
    names = sys.argv[1:] or ['000_0615_022618', '000_0615_035137', '000_0614_233218',
                             '000_0614_124417', '000_0614_220518']
    print("=== 호모그래피 A/B: 타겟 위반 분리도 (1위↑·위반비↑ 좋음) ===")
    for n in names:
        run(n)


if __name__ == "__main__":
    main()
