# 사용자 순수 아이디어만 검증 — 속도·trilateration·카탈로그매칭 전부 배제.
# 오직 "후보 중 anchor 3개까지 거리지문이 W프레임간 가장 많이 변한 것 = 타겟". 안 잡히면 직전위치 유지.
import cv2, json, sys, os, math, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.constellation_tracker import ConstellationTracker
from _constellation_score import to_gray_half, bg_flow_dD
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
THR = 40
W = 3; SEARCH = 30.0; WARMUP = 4; CHANGE_THR = 9.0; TOL = 14.0


def match_map(ct, dp):
    preds = ct._preds(); used = {}; asg = set()
    for ti in range(preds.shape[0]):
        p = preds[ti]; best, bd = -1, TOL**2
        for j in range(dp.shape[0]):
            if j in asg: continue
            d2 = (dp[j,0]-p[0])**2 + (dp[j,1]-p[1])**2
            if d2 < bd: bd, best = d2, j
        if best >= 0: used[ti] = best; asg.add(best)
    return used


def run(name):
    rows = [json.loads(l) for l in open(f'{ROOT}/_record_debug/{name}.jsonl', encoding='utf-8')]
    cap = cv2.VideoCapture(f'{ROOT}/_record_debug/{name}.mp4'); frs=[]
    while True:
        ok,f=cap.read()
        if not ok: break
        frs.append(f)
    cap.release()
    H, Wd = frs[0].shape[:2]; cen = np.array([Wd/2., H/2.])
    ct = ConstellationTracker(); ct.set_bounds(Wd, H)
    prepped=False; lastwc=None; prev_g=None; out={}
    target=None; anchors=None; buf=[]; det_hist=[]; aL_hist=[]
    for i in range(len(frs)):
        dets=[(c[0],c[1],c[2]) for c in rows[i]['cands'] if c[2]>=0.1]
        wb=acquire_white(frs[i]); wc=None
        big=wb is not None and wb[2]>=50 and wb[3]>=50
        if wb is not None and wb[2]>=20: wc=(wb[0]+wb[2]/2.,wb[1]+wb[3]/2.)
        if big and wc:
            ct.prep_observe(dets,bg_flow_dD(prev_g,frs[i])); lastwc=wc; out[i]=wc
        else:
            if not prepped and lastwc and ct._prep_frames>=20:
                ct.finalize_catalog(lastwc[0],lastwc[1]); prepped=True; target=[lastwc[0],lastwc[1]]
            if prepped:
                dp=np.asarray([[c[0],c[1]] for c in dets],float) if dets else np.empty((0,2))
                ct._D=ct._register(dp); mm=match_map(ct,dp)
                # anchor 선정(워밍업)
                if anchors is None:
                    buf.append({ti:(float(dp[j,0]),float(dp[j,1])) for ti,j in mm.items()})
                    if len(buf)>=WARMUP:
                        cnt={};pos={}
                        for fr in buf:
                            for ti,p in fr.items(): cnt[ti]=cnt.get(ti,0)+1; pos.setdefault(ti,[]).append(p)
                        mpn={ti:np.mean(pos[ti],0) for ti in pos}
                        cand=[ti for ti in cnt if cnt[ti]>=0.6*len(buf) and np.hypot(*(mpn[ti]-cen))>80]
                        if len(cand)<3: cand=sorted(cnt,key=lambda t:-np.hypot(*(mpn[t]-cen)))[:6]
                        if len(cand)>=3:
                            cand.sort(key=lambda t:-np.hypot(*(mpn[t]-cen))); ch=[cand[0]]
                            while len(ch)<3:
                                ch.append(max([t for t in cand if t not in ch],
                                              key=lambda t:min(np.hypot(*(mpn[t]-mpn[c])) for c in ch)))
                            anchors=ch
                        else: anchors=[]
                # live anchor 위치
                live=None; nlive=0
                if anchors:
                    lv=[]
                    pr=ct._preds()
                    for a in anchors:
                        if a in mm: lv.append((float(dp[mm[a],0]),float(dp[mm[a],1]))); nlive+=1
                        else: lv.append((float(pr[a,0]),float(pr[a,1])))
                    live=np.asarray(lv)
                # 순수 선택: 후보 중 anchor 거리지문 변화 최대 = 타겟 (속도·trilat·카탈로그매칭 없음)
                sel=None
                if live is not None and nlive>=2 and len(aL_hist)>=W and aL_hist[-W] is not None:
                    aLp=aL_hist[-W]; tx,ty=target; bestc=CHANGE_THR
                    for r in range(dp.shape[0]):
                        ox,oy=float(dp[r,0]),float(dp[r,1])
                        if (ox-tx)**2+(oy-ty)**2>SEARCH**2: continue
                        p=np.array([ox,oy]); okk=True
                        for k in range(1,W+1):
                            Hh=det_hist[-k]
                            if Hh.shape[0]==0: okk=False;break
                            d2=(Hh[:,0]-p[0])**2+(Hh[:,1]-p[1])**2; j=int(np.argmin(d2))
                            if d2[j]>SEARCH**2: okk=False;break
                            p=Hh[j]
                        if not okk: continue
                        dn=np.hypot(live[:,0]-ox,live[:,1]-oy); dpst=np.hypot(aLp[:,0]-p[0],aLp[:,1]-p[1])
                        chg=float(np.mean(np.abs(dn-dpst)))
                        if chg>bestc: bestc,sel=chg,(ox,oy)
                if sel is not None: target=[sel[0],sel[1]]   # 아니면 직전위치 유지(속도 coast 없음)
                out[i]=tuple(target)
                det_hist.append(dp); aL_hist.append(live)
                if len(det_hist)>W+1: det_hist.pop(0); aL_hist.pop(0)
        prev_g=to_gray_half(frs[i])
    return out


def main():
    names=sorted(os.path.basename(d) for d in glob.glob(f'{ROOT}/_gt_frames/*') if os.path.isdir(d))
    ok=0; means=[]
    print("=== 순수 anchor 거리변화만 (속도·trilat·카탈로그매칭 없음) ===")
    for name in names:
        gt=load_gt(name)
        if not gt: continue
        res=run(name)
        errs=[math.hypot(res[fi][0]-g[0],res[fi][1]-g[1]) for fi,g in gt.items() if res.get(fi)]
        if not errs: print(f"  {name}: 소실"); continue
        m=np.mean(errs); cov=len(errs)/len(gt); suc=m<=THR and cov>=0.9; ok+=suc; means.append(m)
        print(f"  {name}: 평균 {m:3.0f}px 유지{cov*100:3.0f}% [{'성공' if suc else '실패'}]")
    print(f"\n  >>> {ok}/{len(means)} 성공, 평균 {np.mean(means):.0f}px")


if __name__ == "__main__":
    main()
