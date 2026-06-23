# 호모그래피 위반 + 부드러움 전역 최적(Viterbi) 추적 — 1~2프레임 지연 허용 가정.
# 검출 격자에서 "총 위반 최대 + 점프 최소" 궤적을 한 번에 찾음(파편화·순간노이즈에 강건).
import json, sys, os, math, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from _gt_score import load_gt
from _homography_track import violation
ROOT = os.path.dirname(os.path.abspath(__file__))
THR = 40
LAM = 0.8; MAXJUMP = 30.0


def run(name):
    rows = [json.loads(l) for l in open(f'{ROOT}/_record_debug/{name}.jsonl', encoding='utf-8')]
    gt = load_gt(name, min_f=0)
    if not gt:
        return None
    fis = sorted(gt); f0, f1 = fis[0], fis[-1]
    dets = {}; viol = {}; prev = None
    for i in range(f0 - 1, f1 + 1):
        cur = np.asarray([[c[0], c[1]] for c in rows[i]['cands'] if c[2] >= 0.1], float) \
            if i < len(rows) else np.empty((0, 2))
        if i >= f0:
            dets[i] = cur; viol[i] = violation(prev, cur) if prev is not None else {}
        prev = cur
    frames = [i for i in range(f0, f1 + 1) if i in dets and dets[i].shape[0] > 0]
    if not frames:
        return None
    score = {}; back = {}
    i0 = frames[0]
    score[i0] = [viol[i0].get(j, 0.0) for j in range(dets[i0].shape[0])]
    back[i0] = [-1] * dets[i0].shape[0]
    for a, b in zip(frames, frames[1:]):
        da, db = dets[a], dets[b]
        sb = [-1e9] * db.shape[0]; bk = [-1] * db.shape[0]
        for j in range(db.shape[0]):
            ev = viol[b].get(j, 0.0)
            for k in range(da.shape[0]):
                jump = math.hypot(db[j, 0] - da[k, 0], db[j, 1] - da[k, 1])
                if jump > MAXJUMP:
                    continue
                s = score[a][k] + ev - LAM * jump
                if s > sb[j]:
                    sb[j] = s; bk[j] = k
            if bk[j] == -1:
                sb[j] = ev - LAM * MAXJUMP
        score[b] = sb; back[b] = bk
    # 백트랙
    j = int(np.argmax(score[frames[-1]])); path = {}
    for idx in range(len(frames) - 1, -1, -1):
        i = frames[idx]
        path[i] = (dets[i][j, 0], dets[i][j, 1])
        if idx > 0:
            nj = back[i][j]
            if nj < 0:   # 전이 끊김 → 이전프레임 최근접으로 이어붙임
                pj = dets[frames[idx - 1]]
                nj = int(np.argmin((pj[:, 0] - path[i][0]) ** 2 + (pj[:, 1] - path[i][1]) ** 2))
            j = nj
    return path


def main():
    names = sys.argv[1:] or sorted(os.path.basename(d) for d in
                                   glob.glob(os.path.join(ROOT, '_gt_frames', '*'))
                                   if os.path.isdir(d))
    ok = 0; total = 0; means = []
    print(f"=== Viterbi(호모그래피 위반+부드러움) 전역 추적 GT 채점 (≤{THR}px=성공) ===")
    for name in names:
        gt = load_gt(name)
        if not gt:
            continue
        total += 1
        path = run(name)
        if not path:
            print(f"  {name}: 소실 [실패]"); continue
        errs = [math.hypot(path[fi][0] - g[0], path[fi][1] - g[1])
                for fi, g in gt.items() if path.get(fi)]
        if not errs:
            print(f"  {name}: 소실 [실패]"); continue
        m = np.mean(errs); mx = max(errs); cov = len(errs) / len(gt)
        means.append(m); suc = m <= THR and cov >= 0.9; ok += suc
        print(f"  {name}: GT {len(gt)}f 평균 {m:3.0f}px 최대 {mx:3.0f} 유지 {cov*100:3.0f}% [{'성공' if suc else '실패'}]")
    if means:
        print(f"\n  >>> {ok}/{total} 성공, 평균 {np.mean(means):.0f}px (vortex 54·⑥ 67·baseline 99 대비)")


if __name__ == "__main__":
    main()
