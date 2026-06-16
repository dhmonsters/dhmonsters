# occlusion 진단 — 녹화 cands(NMS 후)에서 후보 중심거리 floor + 타겟 근접 시 후보수 변화 측정
# Codex 질문: 겹침 중 NMS로 뭉치나(후보수↓) vs 둘 다 잡히나. 답에 따라 길C 트리거가 갈림.
import json, sys, glob, os, math
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.abspath(__file__))


def load(name):
    jf = os.path.join(ROOT, '_record_debug', name + '.jsonl')
    return [json.loads(l) for l in open(jf, encoding='utf-8')]


def analyze(name):
    rows = load(name)
    allmin = []          # 프레임별 최소 쌍거리
    near_hist = {5: 0, 10: 0, 15: 0, 20: 0, 25: 0}  # 두 후보가 X px 내인 프레임수
    seq = []             # (i, n_cands, min_pair_dist, track_to_nearest_decal)
    for fi, r in enumerate(rows):
        cs = [(c[0], c[1]) for c in r.get('cands', []) if c[2] >= 0.1]
        n = len(cs)
        mind = 1e9
        for a in range(n):
            for b in range(a + 1, n):
                d = math.hypot(cs[a][0] - cs[b][0], cs[a][1] - cs[b][1])
                mind = min(mind, d)
        if n >= 2:
            allmin.append(mind)
            for k in near_hist:
                if mind <= k:
                    near_hist[k] += 1
        # 타겟(track)에서 가장 가까운 '다른' 후보까지 거리
        tk = r.get('track')
        t2d = 1e9
        if tk:
            for c in cs:
                d = math.hypot(c[0] - tk[0], c[1] - tk[1])
                if d > 3:    # 타겟 자신 제외(거의 0인 것)
                    t2d = min(t2d, d)
        seq.append((fi, n, mind if n >= 2 else None, t2d))
    return allmin, near_hist, seq, len(rows)


if __name__ == "__main__":
    names = sys.argv[1:]
    for name in names:
        allmin, near, seq, nf = analyze(name)
        print(f"\n=== {name} ({nf}프레임) ===")
        if allmin:
            print(f"후보 최소쌍거리(px): 중앙 {np.median(allmin):.1f}  "
                  f"5%분위 {np.percentile(allmin,5):.1f}  최소 {min(allmin):.1f}")
            print(f"두 후보 X px 내로 근접한 프레임수: {near}")
        # 타겟이 데칼에 근접(≤30px = occlusion 접근)하는 순간 후보수(n)가 줄어드는지(뭉침)
        print("  occlusion 접근 순간(tgt→최근접데칼 ≤30px): i / 후보수n / 거리")
        prev_close = False
        for i, n, mp, t2d in seq:
            close = t2d <= 30
            if close or (prev_close and not close):   # 접근 중 + 분리 직후 1프레임
                t2s = f"{t2d:6.1f}" if t2d < 1e8 else "   -  "
                print(f"  i={i:3d}  n={n:2d}  tgt→데칼 {t2s}")
            prev_close = close
