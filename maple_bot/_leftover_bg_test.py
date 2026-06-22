# 두 전제 측정 — (가)잔여물이 배경D로 움직이는가(=배경)·타겟잔여물은 안움직이는가(구별가능?)
#               (나)준비4초 타겟만 이미지상 정지·데칼은 전부 이동.
import cv2, json, sys, os, math, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.constellation_tracker import ConstellationTracker
from _constellation_score import to_gray_half, bg_flow_dD
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
MATCH = 12.0   # 다음프레임 검출 매칭 허용(px)


def load(name):
    rows = [json.loads(l) for l in open(f'{ROOT}/_record_debug/{name}.jsonl', encoding='utf-8')]
    cap = cv2.VideoCapture(f'{ROOT}/_record_debug/{name}.mp4'); frs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frs.append(f)
    cap.release()
    return rows, frs


def nearest(pt, dets, tol):
    if not dets:
        return None
    d = min(dets, key=lambda c: (c[0]-pt[0])**2 + (c[1]-pt[1])**2)
    return d if (d[0]-pt[0])**2 + (d[1]-pt[1])**2 <= tol*tol else None


def run(name):
    rows, frs = load(name)
    if not frs:
        return
    gt = load_gt(name, min_f=0)
    H, W = frs[0].shape[:2]
    dets_all = [[(c[0], c[1]) for c in r['cands'] if c[2] >= 0.1] for r in rows]
    # 프레임별 배경이동 증분(광류)
    prev_g = None; Dinc = []
    for i in range(len(frs)):
        Dinc.append(np.array(bg_flow_dD(prev_g, frs[i]))); prev_g = to_gray_half(frs[i])

    # 추적기 재생 — 전환경계·프레임별 잔여물 수집
    ct = ConstellationTracker(); ct.set_bounds(W, H)
    prepped = False; lastwc = None; prev_g = None
    outliers_by_f = {}; prep_frames = []
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0]+wb[2]/2., wb[1]+wb[3]/2.)
        if big and wc:
            ct.prep_observe(dets, bg_flow_dD(prev_g, frs[i])); lastwc = wc; prep_frames.append(i)
        else:
            if not prepped and lastwc and ct._prep_frames >= 20:
                ct.finalize_catalog(lastwc[0], lastwc[1]); prepped = True
            if prepped:
                ct.update(dets); outliers_by_f[i] = list(ct._last_outliers)
        prev_g = to_gray_half(frs[i])

    # ── (가) 3프레임 궤적 발산: 잔여물을 누적D로 3프레임 예측해 끝까지 매칭되면 배경 ──
    K = 3; KTOL = 18.0
    def follows_D(o, i):
        """o가 프레임 i부터 누적D 예측을 K프레임 따라가며 매번 검출과 매칭되면 True(=배경)."""
        acc = np.array([o[0], o[1]], dtype=float)
        for k in range(1, K+1):
            if i+k >= len(frs):
                return None
            acc = acc + Dinc[i+k]
            if nearest((acc[0], acc[1]), dets_all[i+k], KTOL) is None:
                return False
        return True
    tot_out = 0; bg_out = 0; nf = 0
    tgt_checked = 0; tgt_bg = 0
    for i, outs in outliers_by_f.items():
        if i+K >= len(frs) or not outs:
            continue
        nf += 1
        for o in outs:
            r = follows_D(o, i)
            if r is None:
                continue
            tot_out += 1; bg_out += int(r)
        g = gt.get(i)
        if g:
            to = min(outs, key=lambda o: (o[0]-g[0])**2 + (o[1]-g[1])**2)
            if (to[0]-g[0])**2 + (to[1]-g[1])**2 <= 30**2:
                r = follows_D(to, i)
                if r is not None:
                    tgt_checked += 1; tgt_bg += int(r)

    # ── (나) 준비 4초: 중앙 도형 vs 데칼 이미지속도 ──
    cen = (W/2., H/2.); cen_sp = []; dec_sp = []
    for k in range(1, len(prep_frames)):
        i0, i1 = prep_frames[k-1], prep_frames[k]
        if i1 != i0+1:
            continue
        d0, d1 = dets_all[i0], dets_all[i1]
        for p in d0:
            m = nearest(p, d1, 30)                  # 같은 도형 추정(최근접)
            if m is None:
                continue
            sp = math.hypot(m[0]-p[0], m[1]-p[1])
            (cen_sp if math.hypot(p[0]-cen[0], p[1]-cen[1]) < 60 else dec_sp).append(sp)
    cen_med = np.median(cen_sp) if cen_sp else float('nan')
    dec_med = np.median(dec_sp) if dec_sp else float('nan')

    print(f"{name:22s} (가)잔여물{tot_out/max(nf,1):4.1f}/f 배경비율{bg_out/max(tot_out,1)*100:3.0f}% "
          f"| 타겟잔여물 D동조 {tgt_bg}/{tgt_checked} "
          f"| (나)중앙속도{cen_med:4.1f} 데칼속도{dec_med:4.1f}px/f")


def main():
    names = sys.argv[1:] or sorted(os.path.basename(d) for d in
                                   glob.glob(os.path.join(ROOT, '_gt_frames', '*')) if os.path.isdir(d))
    print("측정: (가)잔여물 배경비율 클수록 '잔여물=배경' / 타겟잔여물 D동조 낮을수록 '타겟≠배경(구별가능)'")
    print("      (나)중앙속도≪데칼속도 면 '타겟만 정지(정체성확정가능)'")
    print("-" * 120)
    for n in names:
        try:
            run(n)
        except Exception as e:
            print(f"{n}: ERR {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
