# 강체 별자리 추적 시각화 — 준비4초(흰색) 인식 움직임=주황, 투명단계 예측 움직임=시안 구분.
# 타겟(초록)·GT(빨강)·커서(분홍). 16판 일괄. 개별 프레임 PNG(_ct_vis_<name>/) + 몽타주(_ct_vis_<name>.png).
import cv2, json, sys, math, os, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.constellation_tracker import ConstellationTracker
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))

C_PREP = (0, 165, 255)    # 주황 = 준비단계 인식
C_PRED = (255, 200, 0)    # 시안 = 투명단계 예측


def viz_one(name):
    gt = load_gt(name, min_f=0)
    jl = f'{ROOT}/_record_debug/{name}.jsonl'
    if not os.path.exists(jl):
        print(f"{name}: 녹화 없음"); return
    rows = [json.loads(l) for l in open(jl, encoding='utf-8')]
    cap = cv2.VideoCapture(f'{ROOT}/_record_debug/{name}.mp4'); frs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frs.append(f)
    cap.release()
    if not frs:
        print(f"{name}: 빈 영상"); return
    H, W = frs[0].shape[:2]
    gtf = [k for k in gt if k >= 40]
    hi = (max(gtf) + 4) if gtf else len(frs) - 1

    ct = ConstellationTracker(); ct.set_bounds(W, H)
    lockd = False; wp = None; lock_i = None; white_end = None
    Dhist = []; Wflag = []                 # lock 이후 프레임별 D, 준비단계 여부
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        is_white = bool(big and wc)
        if not lockd:
            if wc and wp and (wc[0] - wp[0]) ** 2 + (wc[1] - wp[1]) ** 2 <= 225:
                ct.lock(wc[0], wc[1], dets); lockd = True; lock_i = i
            if wc:
                wp = wc
        else:
            ct.update(dets, white_center=wc if is_white else None)
        if lockd:
            Dhist.append(ct._D.copy()); Wflag.append(is_white)
            if not is_white and white_end is None:
                white_end = i
    if lock_i is None:
        print(f"{name}: 잠금 실패"); return
    if white_end is None:
        white_end = lock_i + 1

    # 보여줄 프레임: 준비단계 샘플(매 3f) + 투명단계 전부
    show = list(range(lock_i, white_end, 3)) + list(range(white_end, hi + 1))
    outdir = os.path.join(ROOT, f'_ct_vis_{name}')
    os.makedirs(outdir, exist_ok=True)
    for old in glob.glob(os.path.join(outdir, '*.png')):
        os.remove(old)
    thumbs = []
    tmpl = ct._template
    for i in show:
        k = i - lock_i                     # Dhist 인덱스
        if k < 0 or k >= len(Dhist):
            continue
        vis = frs[i].copy()
        # 데칼 누적 궤적: lock~현재. 세그먼트별 준비=주황 / 예측=시안
        if tmpl is not None:
            for p0 in tmpl:
                for s in range(1, k + 1):
                    a = (int(p0[0] + Dhist[s-1][0]), int(p0[1] + Dhist[s-1][1]))
                    b = (int(p0[0] + Dhist[s][0]), int(p0[1] + Dhist[s][1]))
                    cv2.line(vis, a, b, C_PREP if Wflag[s] else C_PRED, 1, cv2.LINE_AA)
                cx, cy = int(p0[0] + Dhist[k][0]), int(p0[1] + Dhist[k][1])
                if 0 <= cx < W and 0 <= cy < H:
                    cv2.circle(vis, (cx, cy), 3, C_PREP if Wflag[k] else C_PRED, -1)
        g = gt.get(i)
        if g:
            cv2.circle(vis, (int(g[0]), int(g[1])), 8, (0, 0, 255), 2)
        tr = TARGET_CACHE.get((name, i))   # 추적 타겟(사전 재생 캐시)
        if tr:
            cv2.drawMarker(vis, (int(tr[0]), int(tr[1])), (0, 255, 0), cv2.MARKER_CROSS, 20, 2)
            cv2.circle(vis, (int(tr[0]), int(tr[1])), 11, (0, 255, 0), 2)
        phase = "준비(인식)" if Wflag[k] else "투명(예측)"
        err = math.hypot(tr[0]-g[0], tr[1]-g[1]) if (g and tr) else -1
        lab = f"f{i} {phase}" + (f" err{err:.0f}" if err >= 0 else "")
        cv2.putText(vis, lab, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (0, 255, 255), 2, cv2.LINE_AA)
        cv2.imwrite(os.path.join(outdir, f'f{i:03d}.png'), vis)
        thumbs.append(cv2.resize(vis, (340, int(H * 340 / W))))
    if thumbs:
        th, tw = thumbs[0].shape[:2]; cols = 4
        rn = (len(thumbs) + cols - 1) // cols; pad = 4
        grid = np.full((rn*(th+pad)+pad, cols*(tw+pad)+pad, 3), 20, np.uint8)
        for kk, t in enumerate(thumbs):
            r, c = divmod(kk, cols)
            grid[pad+r*(th+pad):pad+r*(th+pad)+th, pad+c*(tw+pad):pad+c*(tw+pad)+tw] = t
        cv2.imwrite(os.path.join(ROOT, f'_ct_vis_{name}.png'), grid)
        print(f"{name}: {len(thumbs)}장 (준비 f{lock_i}~{white_end} + 투명~{hi}) → 폴더+몽타주")


# 타겟 추적 위치를 먼저 재생해 캐시(시각화 루프와 동일 흐름) — 궤적 그림과 분리
TARGET_CACHE = {}


def cache_targets(name):
    rows = [json.loads(l) for l in open(f'{ROOT}/_record_debug/{name}.jsonl', encoding='utf-8')]
    cap = cv2.VideoCapture(f'{ROOT}/_record_debug/{name}.mp4'); frs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frs.append(f)
    cap.release()
    ct = ConstellationTracker(); ct.set_bounds(frs[0].shape[1], frs[0].shape[0])
    lockd = False; wp = None
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        if not lockd:
            if wc and wp and (wc[0] - wp[0]) ** 2 + (wc[1] - wp[1]) ** 2 <= 225:
                ct.lock(wc[0], wc[1], dets); lockd = True
            if wc:
                wp = wc
            tr = ct.center if lockd else None
        else:
            tr = ct.update(dets, white_center=wc if (big and wc) else None)
        if tr:
            TARGET_CACHE[(name, i)] = tr


def main():
    names = sys.argv[1:]
    if not names:
        names = sorted(os.path.basename(d) for d in
                       glob.glob(os.path.join(ROOT, '_gt_frames', '*')) if os.path.isdir(d))
    for n in names:
        try:
            cache_targets(n)
            viz_one(n)
        except Exception as e:
            print(f"{n}: ERROR {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
