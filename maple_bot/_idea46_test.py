# 아이디어 ④(anchor 거리지문)·⑥(주기 이미지차분) 분리 측정 비교.
# ④: 멀고 자주 잡히는 데칼 3개를 anchor로, 타겟(GT)·데칼의 anchor까지 거리변화 비교(D무관, NN점프없음).
# ⑥: 주기 T 추정 후 frame[t]−정렬(frame[t−T]) 잔차가 타겟위치서 배경보다 두드러지나.
import cv2, json, sys, os, math, glob
from collections import Counter
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.constellation_tracker import ConstellationTracker
from _constellation_score import to_gray_half, bg_flow_dD
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
W = 3
TOL = 14.0


def match_map(ct, dpts):
    preds = ct._preds(); used = {}; asg = set()
    for ti in range(preds.shape[0]):
        p = preds[ti]; best, bd = -1, TOL**2
        for j in range(dpts.shape[0]):
            if j in asg:
                continue
            d2 = (dpts[j,0]-p[0])**2 + (dpts[j,1]-p[1])**2
            if d2 < bd:
                bd, best = d2, j
        if best >= 0:
            used[ti] = (float(dpts[best,0]), float(dpts[best,1])); asg.add(best)
    return used


def run(name):
    rows = [json.loads(l) for l in open(f'{ROOT}/_record_debug/{name}.jsonl', encoding='utf-8')]
    cap = cv2.VideoCapture(f'{ROOT}/_record_debug/{name}.mp4'); frs=[]
    while True:
        ok,f=cap.read()
        if not ok: break
        frs.append(f)
    cap.release()
    gt = load_gt(name, min_f=0)
    H, Wd = frs[0].shape[:2]; cen = np.array([Wd/2., H/2.])
    ct = ConstellationTracker(); ct.set_bounds(Wd, H)
    prepped=False; lastwc=None; prev_g=None
    F={}; grays={}
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
                ct._D=ct._register(dp)
                F[i]=dict(D=ct._D.copy(), mpos=match_map(ct,dp))
                grays[i]=cv2.cvtColor(frs[i],cv2.COLOR_BGR2GRAY)
        prev_g=to_gray_half(frs[i])
    if len(F)<W+2:
        print(f"{name:22s} 데이터부족"); return

    # ── ④ anchor 거리지문 ──
    nF=len(F); cnt=Counter(); meanp={}
    for f in F.values():
        for ti,p in f['mpos'].items():
            cnt[ti]+=1; meanp.setdefault(ti,[]).append(p)
    cand=[ti for ti in cnt if cnt[ti]>=0.6*nF]
    mp={ti:np.mean(meanp[ti],0) for ti in cand}
    far=[ti for ti in cand if np.hypot(*(mp[ti]-cen))>90]
    # 잘 펼쳐진 3개 greedy(중심서 먼것 우선, 이후 기존anchor서 먼것)
    anchors=[]
    if far:
        far.sort(key=lambda ti:-np.hypot(*(mp[ti]-cen)))
        anchors=[far[0]]
        while len(anchors)<3 and len(anchors)<len(far):
            nxt=max([ti for ti in far if ti not in anchors],
                    key=lambda ti:min(np.hypot(*(mp[ti]-mp[a])) for a in anchors))
            anchors.append(nxt)
    tgt_ch=[]; dec_ch=[]
    if len(anchors)>=3:
        for i in F:
            if i+W not in F: continue
            a0=F[i]['mpos']; aW=F[i+W]['mpos']
            if not all(a in a0 and a in aW for a in anchors): continue
            g=gt.get(i); gW=gt.get(i+W)
            if g and gW:
                d0=[math.hypot(g[0]-a0[a][0],g[1]-a0[a][1]) for a in anchors]
                dW=[math.hypot(gW[0]-aW[a][0],gW[1]-aW[a][1]) for a in anchors]
                tgt_ch.append(np.mean(np.abs(np.array(dW)-np.array(d0))))
            for ti in a0:
                if ti in anchors or ti not in aW: continue
                d0=[math.hypot(a0[ti][0]-a0[a][0],a0[ti][1]-a0[a][1]) for a in anchors]
                dW=[math.hypot(aW[ti][0]-aW[a][0],aW[ti][1]-aW[a][1]) for a in anchors]
                dec_ch.append(np.mean(np.abs(np.array(dW)-np.array(d0))))
    t4=np.median(tgt_ch) if tgt_ch else float('nan')
    d4=np.median(dec_ch) if dec_ch else float('nan')

    # ── ⑥ 주기 이미지차분 ──
    fk=sorted(F); Dv={i:F[i]['D'] for i in F}
    # T 추정: D[t]≈D[t−T] 되는 lag(같은 배경위상)
    bestT, bestc = None, 1e9
    for T in range(40, 71):
        diffs=[np.hypot(*(Dv[i]-Dv[i-T])) for i in fk if (i-T) in Dv]
        if len(diffs)>=5:
            m=np.mean(diffs)
            if m<bestc: bestc, bestT = m, T
    ratios=[]
    if bestT:
        for i in fk:
            j=i-bestT
            if j not in grays or i not in grays: continue
            g=gt.get(i)
            if not g: continue
            sh=Dv[i]-Dv[j]                      # 정렬 시프트
            M=np.float32([[1,0,sh[0]],[0,1,sh[1]]])
            warp=cv2.warpAffine(grays[j], M, (Wd,H))
            diff=cv2.absdiff(grays[i], warp).astype(np.float32)
            x,y=int(g[0]),int(g[1])
            x0,x1=max(0,x-15),min(Wd,x+15); y0,y1=max(0,y-15),min(H,y+15)
            win=diff[y0:y1, x0:x1]
            if win.size==0: continue
            rg=float(np.mean(win)); rb=float(np.median(diff)+1e-3)
            ratios.append(rg/rb)
    r6=np.median(ratios) if ratios else float('nan')

    print(f"{name:22s} ④anchor 타겟{t4:5.1f}/데칼{d4:4.1f}={t4/d4 if d4>0 else 0:4.1f}x  "
          f"(anchor{len(anchors)}개) | ⑥주기T{bestT} 타겟잔차/배경 {r6:4.1f}x")


def main():
    names=sys.argv[1:] or sorted(os.path.basename(d) for d in glob.glob(f'{ROOT}/_gt_frames/*') if os.path.isdir(d))
    print("④anchor: 타겟≫데칼+데칼floor↓(2x→클수록좋음) | ⑥주기: 타겟잔차/배경 >1.3이면 타겟 두드러짐")
    print('-'*120)
    for n in names:
        try: run(n)
        except Exception as e: print(f"{n}: ERR {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
