# 무손실 클립 평가 — 핑크 커서=GT(수동 제외구간 빼고). v2·vortex·⑥ 채점. 인게임 진짜 성능 비교.
import cv2, glob, numpy as np, sys, math, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.constellation_tracker import ConstellationTracker
from core.vision.vortex_tracker import VortexTracker
from _constellation_score import to_gray_half, bg_flow_dD
ROOT = os.path.dirname(os.path.abspath(__file__))

# 사용자 지정 GT 제외 구간(커서가 튄/오추적 프레임)
EXCL = {
    '000_0621_165634': [(0, 3), (36, 42)],
    '000_0621_180636': [(97, 107)],
}


def cursor(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    m = cv2.inRange(hsv, np.array([140, 60, 60]), np.array([175, 255, 255]))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cs:
        return None
    c = max(cs, key=cv2.contourArea)
    if cv2.contourArea(c) < 8:
        return None
    M = cv2.moments(c)
    return (M['m10']/M['m00'], M['m01']/M['m00']) if M['m00'] > 0 else None


def eval_clip(name):
    base = f'{ROOT}/_record_debug/{name}'
    frs = [cv2.imread(p) for p in sorted(glob.glob(base + '_png/*.png'))]
    rows = [json.loads(l) for l in open(base + '.jsonl', encoding='utf-8')]
    n = min(len(frs), len(rows))
    H, W = frs[0].shape[:2]
    excl = EXCL.get(name, [])
    def is_excl(i): return any(lo <= i <= hi for lo, hi in excl)
    gtc = [cursor(frs[i]) for i in range(n)]
    seq = []
    for i in range(n):
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0]+wb[2]/2., wb[1]+wb[3]/2.)
        seq.append((wc, big))
    # 채점 대상 = 투명(비 백색) + 커서 GT 있음 + 제외구간 아님
    def valid(i): return gtc[i] and not (seq[i][1] and seq[i][0]) and not is_excl(i)

    # 광류 D + 주기 T (⑥용)
    grays = [cv2.GaussianBlur(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), (3, 3), 0) for f in frs]
    D = [np.zeros(2)]
    for i in range(1, n):
        fl = cv2.calcOpticalFlowFarneback(cv2.resize(grays[i-1], None, fx=.5, fy=.5),
                                          cv2.resize(grays[i], None, fx=.5, fy=.5), None, .5, 3, 21, 3, 7, 1.5, 0)
        mm = np.sqrt(fl[..., 0]**2 + fl[..., 1]**2) > 1.5
        v = (np.median(fl[..., 0][mm])*2 if mm.sum() > 500 else 0,
             np.median(fl[..., 1][mm])*2 if mm.sum() > 500 else 0)
        D.append(D[-1] + np.array(v))
    D = np.array(D)
    bT, bc = None, 1e9
    for T in range(40, 71):
        d = [np.hypot(*(D[i]-D[i-T])) for i in range(T, n)]
        if d and np.mean(d) < bc:
            bc, bT = np.mean(d), T

    def run_v2():
        ct = ConstellationTracker(); ct.set_bounds(W, H); prepped=False; lastwc=None; prev_g=None; out={}
        for i in range(n):
            dets=[(c[0],c[1],c[2]) for c in rows[i]['cands'] if c[2]>=0.1]; wc,big=seq[i]
            if big and wc:
                ct.prep_observe(dets, bg_flow_dD(prev_g, frs[i])); lastwc=wc; out[i]=wc
            else:
                if not prepped and lastwc and ct._prep_frames>=20:
                    ct.finalize_catalog(lastwc[0],lastwc[1]); prepped=True
                out[i]=ct.update(dets) if prepped else None
            prev_g=to_gray_half(frs[i])
        return out

    def run_vortex():
        vt=VortexTracker(); lockd=False; wp=None; out={}
        for i in range(n):
            g=cv2.cvtColor(frs[i],cv2.COLOR_BGR2GRAY); wc,big=seq[i]
            if not lockd:
                if wc and wp and (wc[0]-wp[0])**2+(wc[1]-wp[1])**2<=225: vt.lock(wc[0],wc[1]);lockd=True
                if wc: wp=wc
                out[i]=vt.center
            else:
                out[i]=vt.update(g, white_center=wc if (big and wc) else None)
        return out

    def run_idea6():
        out={}; prepped=False; lastwc=None; target=None; SEARCH=38; JUMP=26
        for i in range(n):
            wc,big=seq[i]
            if big and wc: lastwc=wc; out[i]=wc
            else:
                if not prepped:
                    if lastwc: target=[lastwc[0],lastwc[1]]; prepped=True
                    else: out[i]=None; continue
                j=i-bT if bT else -1
                if 0<=j and target is not None:
                    sh=D[i]-D[j]; warp=cv2.warpAffine(grays[j],np.float32([[1,0,sh[0]],[0,1,sh[1]]]),(W,H))
                    try:
                        (dx,dy),_=cv2.phaseCorrelate(warp.astype(np.float32),grays[i].astype(np.float32))
                        if abs(dx)<20 and abs(dy)<20: warp=cv2.warpAffine(grays[j],np.float32([[1,0,sh[0]+dx],[0,1,sh[1]+dy]]),(W,H))
                    except cv2.error: pass
                    res=cv2.absdiff(grays[i],warp).astype(np.float32)
                    res[cv2.dilate((warp>200).astype(np.uint8),np.ones((9,9),np.uint8))>0]=0
                    res=cv2.GaussianBlur(res,(0,0),4)
                    tx,ty=int(target[0]),int(target[1])
                    x0,x1=max(0,tx-SEARCH),min(W,tx+SEARCH); y0,y1=max(0,ty-SEARCH),min(H,ty+SEARCH)
                    win=res[y0:y1,x0:x1]
                    if win.size:
                        w=win.copy(); w[w<0.6*w.max()]=0
                        if w.sum()>0:
                            ys,xs=np.mgrid[0:win.shape[0],0:win.shape[1]]
                            nx,ny=x0+(xs*w).sum()/w.sum(), y0+(ys*w).sum()/w.sum()
                            dd=math.hypot(nx-target[0],ny-target[1])
                            if dd>JUMP: nx=target[0]+(nx-target[0])*JUMP/dd; ny=target[1]+(ny-target[1])*JUMP/dd
                            target=[nx,ny]
                out[i]=tuple(target) if target else None
        return out

    res = {}
    for tag, fn in [("v2 별자리", run_v2), ("vortex   ", run_vortex), ("⑥ 주기차분", run_idea6)]:
        out = fn()
        e = [math.hypot(out[i][0]-gtc[i][0], out[i][1]-gtc[i][1]) for i in range(n) if valid(i) and out.get(i)]
        res[tag] = (np.mean(e), np.median(e), max(e), len(e)) if e else None
    return res, bT, sum(1 for i in range(n) if valid(i))


def main():
    print("=== 무손실 클립 + 커서GT(수동 제외구간) 채점 ===")
    for name in EXCL:
        if not os.path.isdir(f'{ROOT}/_record_debug/{name}_png'):
            print(f"\n[{name}] PNG 없음 — 건너뜀"); continue
        res, bT, nv = eval_clip(name)
        print(f"\n[{name}] 주기T{bT}, 채점프레임 {nv}개")
        for tag, r in res.items():
            if r: print(f"  {tag}: 평균 {r[0]:3.0f}px 중앙 {r[1]:3.0f} 최대 {r[2]:3.0f} ({r[3]}f)")
            else: print(f"  {tag}: 평가불가")


if __name__ == "__main__":
    main()
