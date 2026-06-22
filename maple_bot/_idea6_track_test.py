# ⑥ 주기 차분 라이브 추적 채점 — 검출 무관. 잔차이미지(frame[t]−정렬frame[t−T])에서
# 직전위치 근처 peak(가중 무게중심)를 타겟으로. 6/16 천장 넘는지 확인.
import cv2, json, sys, os, math, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from _period_check import compute_D
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))
THR = 40
SEARCH = 38      # 직전위치 주변 탐색 반경
JUMP = 26        # 프레임당 최대 이동(노이즈 점프 억제)


def run(name):
    rows = [json.loads(l) for l in open(f'{ROOT}/_record_debug/{name}.jsonl', encoding='utf-8')]
    cap = cv2.VideoCapture(f'{ROOT}/_record_debug/{name}.mp4'); frs=[]
    while True:
        ok,f=cap.read()
        if not ok: break
        frs.append(f)
    cap.release()
    H, Wd = frs[0].shape[:2]
    grays = [cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY),(3,3),0) for f in frs]
    D = compute_D(frs)
    bestT,bc=None,1e9
    for T in range(40,71):
        d=[np.hypot(*(D[i]-D[i-T])) for i in range(T,len(D))]
        if d and np.mean(d)<bc: bc,bestT=np.mean(d),T
    out={}; prepped=False; lastwc=None; target=None
    for i in range(len(frs)):
        wb=acquire_white(frs[i]); wc=None
        big=wb is not None and wb[2]>=50 and wb[3]>=50
        if wb is not None and wb[2]>=20: wc=(wb[0]+wb[2]/2.,wb[1]+wb[3]/2.)
        if big and wc:
            lastwc=wc; out[i]=wc
        else:
            if not prepped:
                if lastwc: target=[lastwc[0],lastwc[1]]; prepped=True
                else: out[i]=None; continue
            j=i-bestT if bestT else -1
            if 0<=j and target is not None:
                sh=D[i]-D[j]; M=np.float32([[1,0,sh[0]],[0,1,sh[1]]])
                warp=cv2.warpAffine(grays[j],M,(Wd,H))
                # 정렬 미세보정: 전역 phaseCorrelate로 잔여 시프트 제거(데칼 잔차↓)
                try:
                    (ddx,ddy),_=cv2.phaseCorrelate(warp.astype(np.float32), grays[i].astype(np.float32))
                    if abs(ddx)<20 and abs(ddy)<20:
                        M2=np.float32([[1,0,sh[0]+ddx],[0,1,sh[1]+ddy]])
                        warp=cv2.warpAffine(grays[j],M2,(Wd,H))
                except cv2.error:
                    pass
                res=cv2.absdiff(grays[i],warp).astype(np.float32)
                # 유령 억제: 한 주기 전 흰색 타겟(밝은 픽셀) 위치 잔차 제거
                ghost=cv2.dilate((warp>200).astype(np.uint8), np.ones((9,9),np.uint8))
                res[ghost>0]=0
                res=cv2.GaussianBlur(res,(0,0),4)
                tx,ty=int(target[0]),int(target[1])
                x0,x1=max(0,tx-SEARCH),min(Wd,tx+SEARCH); y0,y1=max(0,ty-SEARCH),min(H,ty+SEARCH)
                win=res[y0:y1,x0:x1]
                if win.size:
                    w=win.copy(); thr=0.6*w.max()
                    w[w<thr]=0
                    if w.sum()>0:
                        ys,xs=np.mgrid[0:win.shape[0],0:win.shape[1]]
                        cx=(xs*w).sum()/w.sum(); cy=(ys*w).sum()/w.sum()
                        nx,ny=x0+cx,y0+cy
                        d=math.hypot(nx-target[0],ny-target[1])
                        if d>JUMP: nx=target[0]+(nx-target[0])*JUMP/d; ny=target[1]+(ny-target[1])*JUMP/d
                        target=[nx,ny]
            out[i]=tuple(target) if target else None
    return out, bestT


def main():
    names=sorted(os.path.basename(d) for d in glob.glob(f'{ROOT}/_gt_frames/*') if os.path.isdir(d))
    ok=0; means=[]
    print("=== ⑥ 주기차분 잔차peak 추적(검출 무관) ===")
    for name in names:
        gt=load_gt(name)
        if not gt: continue
        res,T=run(name)
        errs=[math.hypot(res[fi][0]-g[0],res[fi][1]-g[1]) for fi,g in gt.items() if res.get(fi)]
        if not errs: print(f"  {name}: 소실"); continue
        m=np.mean(errs); cov=len(errs)/len(gt); suc=m<=THR and cov>=0.9; ok+=suc; means.append(m)
        print(f"  {name}: T{T} 평균 {m:3.0f}px 유지{cov*100:3.0f}% [{'성공' if suc else '실패'}]")
    print(f"\n  >>> {ok}/{len(means)} 성공, 평균 {np.mean(means):.0f}px  (v2 6/16·62px 대비)")


if __name__ == "__main__":
    main()
