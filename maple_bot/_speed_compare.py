# 타겟 vs 데칼 — 프레임별 이동거리·속도벡터 비교(035137).
# 거리: 인접 프레임 |Δposition| / 속도벡터: (vx, vy)와 그 angle. 같은가 다른가.
import cv2, sys, os, json, math
import numpy as np
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.byte_tracker import ByteTracker
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))


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
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frs]
    gt = load_gt(name, min_f=0)

    bt = ByteTracker(); lockd = False; wp = None
    decal_pos = defaultdict(dict)   # tid → {fi: (x,y)} (데칼만)
    for i in range(len(frs)):
        dets = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        if lockd and big and wc:
            tg = next((t for t in bt._tracks if t.tid == bt._tid), None)
            if tg and (wc[0] - tg.x) ** 2 + (wc[1] - tg.y) ** 2 <= 1225:
                bt.nudge(wc[0], wc[1])
        bt.update(grays[i], dets)
        if not lockd:
            if wc and wp and (wc[0] - wp[0]) ** 2 + (wc[1] - wp[1]) ** 2 <= 225:
                bt.lock(wc[0], wc[1]); lockd = True
            if wc:
                wp = wc
        for t in bt._tracks:
            if t.miss == 0 and t.tid != bt._tid:
                decal_pos[t.tid][i] = (t.x, t.y)

    print(f"\n=== {name} === 프레임별 타겟(GT) vs 데칼 이동거리·속도벡터")
    print("  f  | GT_dist | 데칼 dist(중앙 p25 p75) | GT_v=(vx,vy) ang  | 데칼 평균_v ang  | "
          "|Δdist| Δang(°)")
    print("     |  (px)   |   (px)                  |        (px/f)     |       (px/f)     |")

    gt_fis = sorted(gt)
    dist_diffs = []
    ang_diffs = []
    speed_ratios = []
    for fi in gt_fis:
        if fi - 1 not in gt:
            continue
        # 타겟 속도벡터
        gvx = gt[fi][0] - gt[fi-1][0]; gvy = gt[fi][1] - gt[fi-1][1]
        gd = math.hypot(gvx, gvy)
        if gd < 0.5:
            continue   # 거의 정지 — 의미 없음
        gang = math.degrees(math.atan2(gvy, gvx))
        # 데칼 속도들 — 같은 (fi-1, fi) 쌍에 양쪽 위치가 있는 트랙
        dvs = []; dds = []
        for tid, pmap in decal_pos.items():
            if (fi-1) in pmap and fi in pmap:
                dvx = pmap[fi][0] - pmap[fi-1][0]
                dvy = pmap[fi][1] - pmap[fi-1][1]
                dd = math.hypot(dvx, dvy)
                if dd < 0.5:
                    continue
                dvs.append((dvx, dvy)); dds.append(dd)
        if len(dvs) < 3:
            continue
        dds_arr = np.array(dds)
        # 데칼 평균 속도벡터
        mvx = float(np.mean([v[0] for v in dvs]))
        mvy = float(np.mean([v[1] for v in dvs]))
        mang = math.degrees(math.atan2(mvy, mvx))
        md = math.hypot(mvx, mvy)
        # 차이
        d_dist = gd - np.median(dds_arr)
        d_ang = ((gang - mang + 180) % 360) - 180   # signed -180..180
        dist_diffs.append(d_dist); ang_diffs.append(d_ang)
        speed_ratios.append(gd / np.median(dds_arr) if np.median(dds_arr) > 0 else 0)
        phase = "백" if fi <= 24 else "투" if fi >= 56 else " "
        print(f"  {fi:3d}{phase}| {gd:5.1f}   | {np.median(dds_arr):4.1f} {np.percentile(dds_arr,25):4.1f} "
              f"{np.percentile(dds_arr,75):4.1f}    | ({gvx:5.1f},{gvy:5.1f}) {gang:+5.0f} | "
              f"({mvx:5.1f},{mvy:5.1f}) {mang:+5.0f} | "
              f"{abs(d_dist):4.1f}    {abs(d_ang):4.0f}")

    print(f"\n  >>> 요약 ({len(dist_diffs)}프레임)")
    dd = np.array(dist_diffs); da = np.array(ang_diffs); sr = np.array(speed_ratios)
    print(f"  |거리 차이|: 중앙 {np.median(np.abs(dd)):.1f}px  p75 {np.percentile(np.abs(dd),75):.1f}  "
          f"최대 {np.max(np.abs(dd)):.1f}")
    print(f"  속도비(타겟/데칼): 중앙 {np.median(sr):.2f}x  p25 {np.percentile(sr,25):.2f}  "
          f"p75 {np.percentile(sr,75):.2f}")
    print(f"  |각도 차이|: 중앙 {np.median(np.abs(da)):.0f}°  p75 {np.percentile(np.abs(da),75):.0f}°  "
          f"최대 {np.max(np.abs(da)):.0f}°")
    # 백/투명 분리
    for label, cond in [("백색(f≤24)", lambda f: f <= 24), ("투명(f≥56)", lambda f: f >= 56)]:
        idxs = [k for k, f in enumerate(gt_fis) if cond(f) and (f-1) in gt
                and len([1 for tid, pm in decal_pos.items() if (f-1) in pm and f in pm]) >= 3]
        # 위 idxs는 gt_fis 인덱스가 아니라 ID라서 다시 매핑이 복잡 — 단순화: 다시 계산
        d_l = []; a_l = []; s_l = []
        for fi in gt_fis:
            if not cond(fi): continue
            if (fi - 1) not in gt: continue
            gvx = gt[fi][0] - gt[fi-1][0]; gvy = gt[fi][1] - gt[fi-1][1]
            gd = math.hypot(gvx, gvy)
            if gd < 0.5: continue
            gang = math.degrees(math.atan2(gvy, gvx))
            dvs = []
            for tid, pmap in decal_pos.items():
                if (fi-1) in pmap and fi in pmap:
                    dvx = pmap[fi][0] - pmap[fi-1][0]; dvy = pmap[fi][1] - pmap[fi-1][1]
                    if math.hypot(dvx, dvy) >= 0.5:
                        dvs.append((dvx, dvy))
            if len(dvs) < 3: continue
            mvx = float(np.mean([v[0] for v in dvs])); mvy = float(np.mean([v[1] for v in dvs]))
            mang = math.degrees(math.atan2(mvy, mvx))
            md_local = math.hypot(mvx, mvy)
            mdds = np.median([math.hypot(v[0], v[1]) for v in dvs])
            d_l.append(gd - mdds)
            a_l.append(((gang - mang + 180) % 360) - 180)
            s_l.append(gd / mdds if mdds > 0 else 0)
        if d_l:
            print(f"  [{label}] n={len(d_l)}: |거리차| 중앙 {np.median(np.abs(d_l)):.1f}px, "
                  f"속도비 중앙 {np.median(s_l):.2f}x, |각도차| 중앙 {np.median(np.abs(a_l)):.0f}°")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "000_0615_035137")
