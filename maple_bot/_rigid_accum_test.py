# 강체 위반 누적 추적기 프로토타입 — 검출 후보별 '강체 별자리 위반 잔차'를 시간 누적,
# 가장 꾸준히 위반하는(머물며 어긋나는) 트랙=타겟. GT 무관 배포형. 16판 채점.
import cv2, json, sys, math, glob, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.constellation_tracker import ConstellationTracker
from _constellation_score import to_gray_half, bg_flow_dD
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
THR = 40

R_WIN = 70.0      # 타겟 주변 후보 고려 반경(px)
ASSOC = 24.0      # 트랙-검출 연관 게이트(px, 예측위치 기준)
PRUNE_MISS = 2    # 이 프레임 수 미갱신 트랙 제거(검출 공백 coast 허용)
DECAY = 0.92      # 누적 위반 감쇠(오래된 이력 서서히 잊음, 데칼 잔여 억제)
VEL_A = 0.5       # 트랙 속도 EMA
SWITCH = 1.25     # 타겟 전환 히스테리시스(현 타겟 cum 대비 배수)


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
    ct = ConstellationTracker()
    if frs:
        ct.set_bounds(frs[0].shape[1], frs[0].shape[0])
    prepped = False; lastwc = None; prev_g = None
    tracks = []          # 활성 트랙들
    tt = None            # 커밋된 타겟 트랙
    tg = None            # 현재 타겟 추정 [x,y]
    out = {}
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        if big and wc:
            ct.prep_observe(dets, bg_flow_dD(prev_g, frs[i])); lastwc = wc
            out[i] = wc; tg = [wc[0], wc[1]]
        else:
            if not prepped and lastwc is not None and ct._prep_frames >= 20:
                ct.finalize_catalog(lastwc[0], lastwc[1]); prepped = True
                tt = Track(lastwc[0], lastwc[1], 0.0)   # 타겟 트랙 시드
                tracks = [tt]; tg = [lastwc[0], lastwc[1]]
            if prepped and tt is not None:
                dp = np.asarray([[c[0], c[1]] for c in dets], float) if dets else np.empty((0, 2))
                if dp.shape[0]:
                    ct._D = ct._register(dp)
                    preds = ct._preds()
                    if preds.shape[0]:
                        resid = np.array([float(np.min(np.hypot(preds[:, 0] - d[0], preds[:, 1] - d[1]))) for d in dp])
                    else:
                        resid = np.zeros(dp.shape[0])
                    for t in tracks:
                        t.cum *= DECAY; t.miss += 1
                    # 모션 예측 위치 기준 연관(가까운 트랙부터)
                    used = set()
                    order = sorted(range(dp.shape[0]),
                                   key=lambda j: (dp[j, 0] - tt.x) ** 2 + (dp[j, 1] - tt.y) ** 2)
                    for j in order:
                        best, bd = None, ASSOC ** 2
                        for t in tracks:
                            if id(t) in used:
                                continue
                            px, py = t.predict()
                            d2 = (px - dp[j, 0]) ** 2 + (py - dp[j, 1]) ** 2
                            if d2 < bd:
                                bd, best = d2, t
                        if best is not None:
                            best.hit(dp[j, 0], dp[j, 1], resid[j]); used.add(id(best))
                        elif (dp[j, 0] - tt.x) ** 2 + (dp[j, 1] - tt.y) ** 2 <= R_WIN ** 2:
                            tracks.append(Track(dp[j, 0], dp[j, 1], resid[j]))
                # tt 미갱신이면 coast(예측 위치로 이동)
                if tt.miss > 0:
                    tt.x, tt.y = tt.predict()
                # tt 제외 트랙 정리(창 밖/오래 미갱신)
                tracks = [t for t in tracks if t is tt or
                          (t.miss <= PRUNE_MISS and (t.x - tt.x) ** 2 + (t.y - tt.y) ** 2 <= R_WIN ** 2)]
                # 히스테리시스 전환 — 창 안 더 꾸준한 위반자가 충분히 우세하면 타겟 교체
                cands = [t for t in tracks if t is not tt
                         and (t.x - tt.x) ** 2 + (t.y - tt.y) ** 2 <= R_WIN ** 2]
                if cands:
                    bt = max(cands, key=lambda t: t.cum)
                    if bt.cum > max(tt.cum, 1.0) * SWITCH:
                        tt = bt
                tg = [tt.x, tt.y]
                out[i] = (tg[0], tg[1])
        prev_g = to_gray_half(frs[i])
    return out


def main():
    names = sys.argv[1:] or sorted(os.path.basename(d) for d in
                                   glob.glob(os.path.join(ROOT, '_gt_frames', '*'))
                                   if os.path.isdir(d))
    ok = 0; total = 0; means = []
    print(f"=== 강체 위반 누적 추적기 GT 채점 (≤{THR}px=성공) ===")
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
