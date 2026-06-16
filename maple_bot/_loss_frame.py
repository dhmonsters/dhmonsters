# 판별: 각 녹화가 몇 번째 프레임에서 타겟을 잃는지(오차>THR 이후 회복 안 되는 첫 GT 프레임).
import sys, os, glob, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from _gt_score import load_gt, run_bytetrack
ROOT = os.path.dirname(os.path.abspath(__file__))
THR = 40   # 잃음 임계(px)


def loss_frame(name):
    gt = load_gt(name)
    if not gt:
        return name, None, "GT 라벨 없음", []
    res = run_bytetrack(name)
    fis = sorted(gt)
    errs = []
    for fi in fis:
        if res.get(fi):
            e = math.hypot(res[fi][0] - gt[fi][0], res[fi][1] - gt[fi][1])
        else:
            e = float('inf')   # 추적 None = 소실
        errs.append((fi, e))
    # 잃음 = 오차>THR 이후 끝까지 회복(<=THR) 안 되는 첫 프레임
    loss = None
    for k, (fi, e) in enumerate(errs):
        if e > THR and all(ee > THR for _, ee in errs[k:]):
            loss = fi
            break
    return name, loss, None, errs


if __name__ == "__main__":
    names = sorted(os.path.basename(d) for d in
                   glob.glob(os.path.join(ROOT, '_gt_frames', '*')) if os.path.isdir(d))
    print(f"=== 타겟 잃는 프레임 (오차>{THR}px 이후 회복불가 첫 프레임) ===")
    for name in names:
        nm, loss, note, errs = loss_frame(name)
        if note:
            print(f"  {nm}: {note}"); continue
        fis = [fi for fi, _ in errs]
        rng = f"f{fis[0]}~{fis[-1]}"
        seq = " ".join(f"{fi}:{'∞' if e==float('inf') else int(e)}" for fi, e in errs)
        if loss is None:
            print(f"  {nm}: 유지(안 잃음) | GT {rng} | 오차 {seq}")
        elif loss == fis[0]:
            print(f"  {nm}: GT시작({rng}) 이전 이미 잃음(전환/백색단계) | 오차 {seq}")
        else:
            print(f"  {nm}: ★ f{loss}에서 잃음 | GT {rng} | 오차 {seq}")
