# 아이디어 ⑥(주기 이미지차분)·⑦(궤도 D 매끄러움)·⑨(후보 국소 광류 curl=자전) 측정.
import cv2, json, sys, os, math, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from _constellation_score import to_gray_half
from _period_check import compute_D
from _bg_rotation_probe import fit_circle
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))


def run(name):
    rows = [json.loads(l) for l in open(f'{ROOT}/_record_debug/{name}.jsonl', encoding='utf-8')]
    cap = cv2.VideoCapture(f'{ROOT}/_record_debug/{name}.mp4'); frs=[]
    while True:
        ok,f=cap.read()
        if not ok: break
        frs.append(f)
    cap.release()
    gt = load_gt(name, min_f=0)
    H, Wd = frs[0].shape[:2]
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frs]
    D = compute_D(frs)                          # 전체 프레임 누적 배경이동(광류)
    dets_all = [[(c[0],c[1]) for c in r['cands'] if c[2]>=0.1] for r in rows]
    prep_end = 0
    for i,f in enumerate(frs):
        wb=acquire_white(f)
        if wb is not None and wb[2]>=50 and wb[3]>=50: prep_end=i

    # ── ⑥ 주기 차분: T 추정(D 자기상관) → frame[t]−정렬(frame[t−T]) 잔차가 GT서 두드러지나 ──
    bestT,bc=None,1e9
    for T in range(40,71):
        d=[np.hypot(*(D[i]-D[i-T])) for i in range(T,len(D))]
        if d and np.mean(d)<bc: bc,bestT=np.mean(d),T
    r6=[]
    if bestT:
        for i in gt:
            j=i-bestT
            if j<0 or i>=len(grays): continue
            sh=D[i]-D[j]; M=np.float32([[1,0,sh[0]],[0,1,sh[1]]])
            warp=cv2.warpAffine(grays[j],M,(Wd,H))
            diff=cv2.absdiff(grays[i],warp).astype(np.float32)
            g=gt[i]; x,y=int(g[0]),int(g[1])
            win=diff[max(0,y-15):y+15,max(0,x-15):x+15]
            if win.size: r6.append(np.mean(win)/(np.median(diff)+1e-3))
    m6=np.median(r6) if r6 else float('nan')

    # ── ⑦ 궤도 매끄러움: D(t)가 원에 얼마나 매끄럽나(fit RMS). 작을수록 예측 정밀(floor↓) ──
    fc=fit_circle([(p[0],p[1]) for p in D[prep_end:]])
    rms7 = fc[3] if fc else float('nan')

    # ── ⑨ 국소 curl(자전): GT 위치 광류 curl vs 데칼 위치 curl. 배경광류 빼고 ──
    tgt_c=[]; dec_c=[]
    for i in gt:
        if i<1 or i>=len(grays): continue
        flow=cv2.calcOpticalFlowFarneback(grays[i-1],grays[i],None,0.5,3,21,3,7,1.5,0)
        fx=flow[...,0]-np.median(flow[...,0]); fy=flow[...,1]-np.median(flow[...,1])
        gy_fx=np.gradient(fx,axis=0); gx_fy=np.gradient(fy,axis=1)
        curl=np.abs(gx_fy-gy_fx)                # |∂fy/∂x − ∂fx/∂y|
        def cwin(x,y):
            w=curl[max(0,y-12):y+12,max(0,x-12):x+12]; return float(np.mean(w)) if w.size else 0
        g=gt[i]; tgt_c.append(cwin(int(g[0]),int(g[1])))
        for (dx,dy) in dets_all[i][:8]:
            if math.hypot(dx-g[0],dy-g[1])>40: dec_c.append(cwin(int(dx),int(dy)))
    m9t=np.median(tgt_c) if tgt_c else float('nan')
    m9d=np.median(dec_c) if dec_c else float('nan')

    print(f"{name:22s} ⑥주기T{bestT} 잔차비{m6:4.1f}x(>1.3↑) | ⑦D원fit_rms{rms7:5.1f}px(작을수록매끄) | "
          f"⑨curl 타겟{m9t:.2f}/데칼{m9d:.2f}={m9t/m9d if m9d>0 else 0:4.1f}x")


def main():
    names=sorted(os.path.basename(d) for d in glob.glob(f'{ROOT}/_gt_frames/*') if os.path.isdir(d))
    for n in names:
        try: run(n)
        except Exception as e: print(f"{n}: ERR {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
