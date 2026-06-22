# 강체 별자리 추적기 GT 채점 — run_bytetrack과 동일 솔버 흐름으로 ConstellationTracker 재생.
# 16판 평균오차·성공수 산출(vortex 54px·baseline 대비). load_gt/red_mark는 _gt_score 재사용.
import cv2, json, sys, math, glob, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.constellation_tracker import ConstellationTracker
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
THR = 40


def to_gray_half(bgr):
    return cv2.cvtColor(cv2.resize(bgr, None, fx=0.5, fy=0.5), cv2.COLOR_BGR2GRAY)


def bg_flow_dD(prev_g, cur_bgr):
    """배경 평행이동 증분 = 밀집광류 median(×2 원해상도 보정). prev 없으면 0."""
    cur_g = to_gray_half(cur_bgr)
    if prev_g is None:
        return (0.0, 0.0)
    flow = cv2.calcOpticalFlowFarneback(prev_g, cur_g, None, 0.5, 3, 21, 3, 7, 1.5, 0)
    mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
    m = mag > 1.5
    if m.sum() < 500:
        return (0.0, 0.0)
    return (float(np.median(flow[..., 0][m]) * 2), float(np.median(flow[..., 1][m]) * 2))


def run_constellation(name):
    mp4 = os.path.join(ROOT, '_record_debug', name + '.mp4')
    rows = [json.loads(l) for l in open(mp4[:-4] + '.jsonl', encoding='utf-8')]
    cap = cv2.VideoCapture(mp4); frs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frs.append(f)
    cap.release()
    ct = ConstellationTracker(); out = {}
    if frs:
        ct.set_bounds(frs[0].shape[1], frs[0].shape[0])
    prepped = False; lastwc = None; prev_g = None
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        if big and wc:
            # 준비(흰색) 단계 — 배경 광류 median으로 dD 계산 후 글로벌좌표 누적(배경 1회전 카탈로그)
            dD = bg_flow_dD(prev_g, frs[i])
            ct.prep_observe(dets, dD); lastwc = wc
            out[i] = wc
        else:
            if not prepped and lastwc is not None and ct._prep_frames >= 20:
                ct.finalize_catalog(lastwc[0], lastwc[1]); prepped = True
            out[i] = ct.update(dets) if prepped else None
        prev_g = to_gray_half(frs[i])
    return out


def main():
    names = sys.argv[1:] or sorted(os.path.basename(d) for d in
                                   glob.glob(os.path.join(ROOT, '_gt_frames', '*'))
                                   if os.path.isdir(d))
    ok = 0; total = 0; means = []
    print(f"=== 강체 별자리 GT 채점 (평균오차 ≤{THR}px = 성공) ===")
    for name in names:
        gt = load_gt(name)
        if not gt:
            print(f"  {name}: GT 라벨 없음"); continue
        total += 1
        res = run_constellation(name)
        errs = [math.hypot(res[fi][0] - g[0], res[fi][1] - g[1])
                for fi, g in gt.items() if res.get(fi)]
        if not errs:
            print(f"  {name}: GT {len(gt)}f — 추적 소실  [실패]"); continue
        m = np.mean(errs); mx = max(errs); cov = len(errs) / len(gt)
        means.append(m)
        suc = m <= THR and cov >= 0.9
        ok += suc
        print(f"  {name}: GT {len(gt)}f, 평균 {m:3.0f}px 최대 {mx:3.0f} "
              f"유지 {cov*100:3.0f}%  [{'성공' if suc else '실패'}]")
    print(f"\n  >>> {ok}/{total} 성공, 16판 평균 {np.mean(means):.0f}px "
          f"(vortex 54px / baseline 99px)")


if __name__ == "__main__":
    main()
