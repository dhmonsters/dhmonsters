# 호모그래피 위반 누적 추적기 — 매 프레임 배경 RANSAC 호모그래피 재투영오차=후보 위반,
# 직전 타겟 윈도우 안에서 트랙별 누적, 가장 꾸준히 위반=타겟. 검출공백 coast. GT무관 배포형.
import cv2, json, sys, os, math, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from _constellation_score import to_gray_half
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
THR = 40
GATE = 26.0; VEL_A = 0.5; MATCH_GATE = 45.0; COAST = 0.9; MIN_VIOL = 6.0


class Track:
    __slots__ = ('x', 'y', 'vx', 'vy', 'cum', 'miss', 'age')
    def __init__(self, x, y, r):
        self.x = x; self.y = y; self.vx = 0.0; self.vy = 0.0
        self.cum = r; self.miss = 0; self.age = 1
    def predict(self):
        return self.x + self.vx, self.y + self.vy
    def hit(self, nx, ny, r):
        self.vx = VEL_A * self.vx + (1 - VEL_A) * (nx - self.x)
        self.vy = VEL_A * self.vy + (1 - VEL_A) * (ny - self.y)
        self.x = nx; self.y = ny; self.cum += r; self.miss = 0; self.age += 1


def violation(prev, cur):
    """배경 RANSAC 호모그래피 재투영오차 = 후보별 강체 위반. (cur_idx→err)."""
    out = {}
    if prev.shape[0] < 8 or cur.shape[0] < 8:
        return out
    pairs = []
    for j in range(cur.shape[0]):
        d2 = (prev[:, 0] - cur[j, 0]) ** 2 + (prev[:, 1] - cur[j, 1]) ** 2
        k = int(np.argmin(d2))
        if d2[k] <= MATCH_GATE ** 2:
            pairs.append((j, prev[k]))
    if len(pairs) < 8:
        return out
    src = np.float32([p for _, p in pairs]).reshape(-1, 1, 2)
    dst = np.float32([cur[j] for j, _ in pairs]).reshape(-1, 1, 2)
    Hm, _ = cv2.findHomography(src, dst, cv2.RANSAC, 4.0)
    if Hm is None:
        return out
    proj = cv2.perspectiveTransform(src, Hm).reshape(-1, 2)
    for k, (j, _) in enumerate(pairs):
        out[j] = float(np.hypot(proj[k, 0] - cur[j, 0], proj[k, 1] - cur[j, 1]))
    return out


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
    prepped = False; lastwc = None; prev_dp = None
    tt = None; tg = None; tracks = []; out = {}
    prep_seen = 0
    for i in range(len(frs)):
        cands = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        dp = np.asarray([[c[0], c[1]] for c in cands], float) if cands else np.empty((0, 2))
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        if big and wc:
            lastwc = wc; prep_seen += 1; out[i] = wc
        else:
            if not prepped and lastwc is not None and prep_seen >= 20:
                prepped = True; tt = Track(lastwc[0], lastwc[1], 0.0); tracks = [tt]; tg = list(lastwc)
            if prepped and tt is not None:
                viol = violation(prev_dp, dp) if prev_dp is not None else {}
                px, py = tt.predict()
                gated = [j for j in range(dp.shape[0])
                         if (dp[j, 0] - px) ** 2 + (dp[j, 1] - py) ** 2 <= GATE ** 2]
                if gated:
                    # 게이트 안 위반 최대 후보(고위반 데칼은 멀어 게이트 밖). 동률·저위반이면 최근접.
                    pick = max(gated, key=lambda j: (viol.get(j, 0.0), -((dp[j, 0] - px) ** 2 + (dp[j, 1] - py) ** 2)))
                    if viol.get(pick, 0.0) < MIN_VIOL:
                        pick = min(gated, key=lambda j: (dp[j, 0] - px) ** 2 + (dp[j, 1] - py) ** 2)
                    tt.hit(dp[pick, 0], dp[pick, 1], 0.0)
                else:
                    tt.x, tt.y = px, py
                    tt.vx *= COAST; tt.vy *= COAST; tt.miss += 1
                out[i] = (tt.x, tt.y)
        prev_dp = dp
    return out


def main():
    names = sys.argv[1:] or sorted(os.path.basename(d) for d in
                                   glob.glob(os.path.join(ROOT, '_gt_frames', '*'))
                                   if os.path.isdir(d))
    ok = 0; total = 0; means = []
    print(f"=== 호모그래피 위반 누적 추적기 GT 채점 (≤{THR}px=성공) ===")
    for name in names:
        gt = load_gt(name)
        if not gt:
            continue
        total += 1
        res = run(name)
        errs = [math.hypot(res[fi][0] - g[0], res[fi][1] - g[1])
                for fi, g in gt.items() if res.get(fi)]
        if not errs:
            print(f"  {name}: 소실 [실패]"); continue
        m = np.mean(errs); mx = max(errs); cov = len(errs) / len(gt)
        means.append(m); suc = m <= THR and cov >= 0.9; ok += suc
        print(f"  {name}: GT {len(gt)}f 평균 {m:3.0f}px 최대 {mx:3.0f} 유지 {cov*100:3.0f}% [{'성공' if suc else '실패'}]")
    if means:
        print(f"\n  >>> {ok}/{total} 성공, 평균 {np.mean(means):.0f}px (vortex 54·⑥ 67·baseline 99 대비)")


if __name__ == "__main__":
    main()
