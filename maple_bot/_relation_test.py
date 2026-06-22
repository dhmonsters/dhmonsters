# 상대거리 식별 전제 측정(D 무관) — 잔여물을 3프레임 추적하며 '매칭 데칼들과의 거리벡터' 변화량 측정.
# 타겟=거리 크게 변함, 데칼-잔여물=거의 불변 이면 갈림(=설계 유효). D 지터 무관(거리는 평행이동 불변).
import cv2, json, sys, os, math, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.constellation_tracker import ConstellationTracker
from _constellation_score import to_gray_half, bg_flow_dD
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
W = 3          # 거리변화 측정 윈도(프레임)
SEARCH = 25.0  # 잔여물 전방추적 서치범위(타겟 점프 가능거리)
TOL = 14.0     # 데칼 매칭 허용


def match_map(ct, dpts):
    """template_idx → 매칭 det index. (register 후 그리디 최근접)"""
    preds = ct._preds(); used = {}; assigned = set()
    for ti in range(preds.shape[0]):
        p = preds[ti]; best, bd = -1, TOL**2
        for j in range(dpts.shape[0]):
            if j in assigned:
                continue
            d2 = (dpts[j,0]-p[0])**2 + (dpts[j,1]-p[1])**2
            if d2 < bd:
                bd, best = d2, j
        if best >= 0:
            used[ti] = best; assigned.add(best)
    return used, assigned


def run(name):
    rows = [json.loads(l) for l in open(f'{ROOT}/_record_debug/{name}.jsonl', encoding='utf-8')]
    cap = cv2.VideoCapture(f'{ROOT}/_record_debug/{name}.mp4'); frs=[]
    while True:
        ok,f=cap.read()
        if not ok: break
        frs.append(f)
    cap.release()
    gt = load_gt(name, min_f=0)
    # 전 프레임: 검출, 매칭맵(template_idx→pos), 아웃라이어
    ct = ConstellationTracker(); ct.set_bounds(frs[0].shape[1], frs[0].shape[0])
    prepped=False; lastwc=None; prev_g=None
    F = {}   # frame i → dict(dets=np, mmap={ti:pos}, outs=[pos])
    for i in range(len(frs)):
        dets=[(c[0],c[1],c[2]) for c in rows[i]['cands'] if c[2]>=0.1]
        wb=acquire_white(frs[i]); wc=None
        big=wb is not None and wb[2]>=50 and wb[3]>=50
        if wb is not None and wb[2]>=20: wc=(wb[0]+wb[2]/2.,wb[1]+wb[3]/2.)
        if big and wc:
            ct.prep_observe(dets,bg_flow_dD(prev_g,frs[i])); lastwc=wc
        else:
            if not prepped and lastwc and ct._prep_frames>=20:
                ct.finalize_catalog(lastwc[0],lastwc[1]); prepped=True
            if prepped:
                dp=np.asarray([[c[0],c[1]] for c in dets],float) if dets else np.empty((0,2))
                ct._D = ct._register(dp)
                mm, assigned = match_map(ct, dp)
                mpos = {ti: (float(dp[j,0]),float(dp[j,1])) for ti,j in mm.items()}
                outs = [(float(dp[j,0]),float(dp[j,1])) for j in range(dp.shape[0]) if j not in assigned]
                F[i] = dict(dets=dp, mpos=mpos, outs=outs, D=ct._D.copy())
        prev_g=to_gray_half(frs[i])

    def track_fwd(p, i):
        """잔여물 p를 i→i+W 까지 서치범위 내 최근접으로 추적. 각 프레임 위치 리스트(없으면 None)."""
        path=[p]; cur=p
        for k in range(1, W+1):
            if i+k not in F: return None
            dp=F[i+k]['dets']
            if dp.shape[0]==0: return None
            d2=(dp[:,0]-cur[0])**2+(dp[:,1]-cur[1])**2
            j=int(np.argmin(d2))
            if d2[j] > SEARCH**2: return None
            cur=(float(dp[j,0]),float(dp[j,1])); path.append(cur)
        return path

    def dist_change(path, i):
        """path의 각 프레임에서 '공통 매칭데칼들과의 거리' 변화량 평균(거리=D무관)."""
        common = set(F[i]['mpos'])
        for k in range(1, W+1):
            common &= set(F[i+k]['mpos'])
        common = list(common)
        if len(common) < 3:
            return None
        d0 = np.array([math.hypot(path[0][0]-F[i]['mpos'][ti][0], path[0][1]-F[i]['mpos'][ti][1]) for ti in common])
        dW = np.array([math.hypot(path[W][0]-F[i+W]['mpos'][ti][0], path[W][1]-F[i+W]['mpos'][ti][1]) for ti in common])
        return float(np.mean(np.abs(dW - d0)))

    tgt_d=[]; dec_d=[]      # ① 스칼라 거리변화
    tgt_r=[]; dec_r=[]      # ② 강체예측 잔차(방향포함)
    for i in F:
        if i+W not in F: continue
        outs=F[i]['outs']; g=gt.get(i)
        dD = F[i+W]['D'] - F[i]['D']      # 윈도 배경 변위
        for o in outs:
            path=track_fwd(o, i)
            if path is None: continue
            s=dist_change(path, i)
            # ② 강체예측 잔차 = |W프레임 변위 − 배경변위|
            r=math.hypot(path[W][0]-o[0]-dD[0], path[W][1]-o[1]-dD[1])
            is_tgt = g and math.hypot(o[0]-g[0],o[1]-g[1])<=25
            if s is not None:
                (tgt_d if is_tgt else dec_d).append(s)
            (tgt_r if is_tgt else dec_r).append(r)
    def med(a): return np.median(a) if a else float('nan')
    td,dd_=med(tgt_d),med(dec_d); tr,dr=med(tgt_r),med(dec_r)
    print(f"{name:22s} ①거리 타겟{td:5.1f}/데칼{dd_:4.1f}={td/dd_ if dd_>0 else 0:.1f}x   "
          f"②강체잔차 타겟{tr:5.1f}/데칼{dr:4.1f}={tr/dr if dr>0 else 0:.1f}x  (타겟n={len(tgt_r)})")


def main():
    names=sys.argv[1:] or sorted(os.path.basename(d) for d in glob.glob(f'{ROOT}/_gt_frames/*') if os.path.isdir(d))
    print(f"상대거리 변화 측정(W={W}f, D무관): 타겟≫데칼 이면 식별 유효")
    print('-'*110)
    for n in names:
        try: run(n)
        except Exception as e: print(f"{n}: ERR {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
