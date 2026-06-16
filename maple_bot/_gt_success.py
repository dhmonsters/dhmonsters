# GT 성공율 집계 — 16판 전체. 평균오차 ≤THR=성공(도형 크기 이내로 따라감). 소실(추적None)도 명시.
import sys, os, glob, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from _gt_score import load_gt, run_bytetrack
ROOT = os.path.dirname(os.path.abspath(__file__))
THR = 40   # 성공 임계(평균오차 px)


def main():
    names = sorted(os.path.basename(d) for d in
                   glob.glob(os.path.join(ROOT, '_gt_frames', '*'))
                   if os.path.isdir(d))
    ok = 0
    print(f"=== GT 성공율 (평균오차 ≤{THR}px = 성공) ===")
    for name in names:
        gt = load_gt(name)
        if not gt:
            print(f"  {name}: GT 라벨 없음"); continue
        res = run_bytetrack(name)
        errs = [math.hypot(res[fi][0] - g[0], res[fi][1] - g[1])
                for fi, g in gt.items() if res.get(fi)]
        if not errs:
            print(f"  {name}: GT {len(gt)}f — 추적 전구간 소실  [실패]"); continue
        m = np.mean(errs); mx = max(errs)
        cov = len(errs) / len(gt)   # GT 중 추적 유지 비율
        suc = m <= THR and cov >= 0.9
        if suc:
            ok += 1
        print(f"  {name}: GT {len(gt)}f, 평균 {m:3.0f}px 최대 {mx:3.0f} "
              f"추적유지 {cov*100:3.0f}%  [{'성공' if suc else '실패'}]")
    print(f"\n  >>> {ok}/{len(names)} 성공")


if __name__ == "__main__":
    main()
