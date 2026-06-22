# 무손실 클립 + 커서GT — 검출기반 선택변형(v2/v3/v4/v5) + 오라클 채점. 타겟은 검출됨(recall~95%),
# 핵심은 '어느 검출을 타겟으로 고르나'. 각 변형의 선택 로직만 다름. 공통: 카탈로그·정합·아웃라이어.
import cv2, glob, numpy as np, sys, math, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from core.vision.constellation_tracker import ConstellationTracker
from _constellation_score import to_gray_half, bg_flow_dD
ROOT = os.path.dirname(os.path.abspath(__file__))
EXCL = {'000_0621_165634': [(0, 3), (36, 42)], '000_0621_180636': [(97, 107)]}
GATE, MISSK, MISSCAP, VA, VMAX, COAST = 30.0, 8.0, 4, 0.6, 16.0, 0.9
SEARCH, FPW, TOL = 30.0, 3, 14.0


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


def precompute(name):
    base = f'{ROOT}/_record_debug/{name}'
    frs = [cv2.imread(p) for p in sorted(glob.glob(base + '_png/*.png'))]
    rows = [json.loads(l) for l in open(base + '.jsonl', encoding='utf-8')]
    n = min(len(frs), len(rows)); H, W = frs[0].shape[:2]
    ct = ConstellationTracker(); ct.set_bounds(W, H)
    prepped = False; lastwc = None; prev_g = None
    F = []   # 프레임별 dict (transparent만 채움; 그 외 None)
    start = None
    for i in range(n):
        dets = np.asarray([[c[0], c[1]] for c in rows[i]['cands'] if c[2] >= 0.1], float)
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0]+wb[2]/2., wb[1]+wb[3]/2.)
        info = None
        if big and wc:
            ct.prep_observe([(c[0],c[1],c[2]) for c in rows[i]['cands'] if c[2]>=0.1],
                            bg_flow_dD(prev_g, frs[i])); lastwc = wc
        else:
            if not prepped and lastwc and ct._prep_frames >= 20:
                ct.finalize_catalog(lastwc[0], lastwc[1]); prepped = True; start = lastwc
            if prepped:
                ct._D = ct._register(dets)
                preds = ct._preds(); used = set(); mt = {}
                for ti in range(preds.shape[0]):
                    p = preds[ti]; best, bd = -1, TOL**2
                    for j in range(dets.shape[0]):
                        if j in used: continue
                        dd = (dets[j,0]-p[0])**2 + (dets[j,1]-p[1])**2
                        if dd < bd: bd, best = dd, j
                    if best >= 0: used.add(best); mt[ti] = best
                outl = [(float(dets[j,0]),float(dets[j,1])) for j in range(dets.shape[0]) if j not in used]
                info = dict(dets=dets, D=ct._D.copy(), mt=mt, outl=outl, preds=preds)
        F.append(info)
        prev_g = to_gray_half(frs[i])
    return frs, F, start, (W, H)


def select_anchors(F, W, H):
    cen = np.array([W/2., H/2.]); cnt = {}; pos = {}; cntf = 0
    for info in F:
        if info is None or cntf >= 6: continue
        cntf += 1
        for ti, j in info['mt'].items():
            cnt[ti] = cnt.get(ti, 0)+1; pos.setdefault(ti, []).append(info['dets'][j])
    if not cnt: return None
    mpn = {ti: np.mean(pos[ti], 0) for ti in pos}
    cand = [ti for ti in cnt if cnt[ti] >= 3 and np.hypot(*(mpn[ti]-cen)) > 80]
    if len(cand) < 3: cand = sorted(cnt, key=lambda t: -np.hypot(*(mpn[t]-cen)))[:6]
    if len(cand) < 3: return None
    cand.sort(key=lambda t: -np.hypot(*(mpn[t]-cen))); ch = [cand[0]]
    while len(ch) < 3:
        ch.append(max([t for t in cand if t not in ch],
                      key=lambda t: min(np.hypot(*(mpn[t]-mpn[c])) for c in ch)))
    return ch


def main():
    print("=== 무손실 + 커서GT — 검출기반 선택변형 채점 (타겟 검출됨, 선택이 관건) ===")
    for name, ex in EXCL.items():
        if not os.path.isdir(f'{ROOT}/_record_debug/{name}_png'):
            continue
        frs, F, start, (W, H) = precompute(name)
        n = len(F)
        def isx(i): return any(lo <= i <= hi for lo, hi in ex)
        gtc = [cursor(frs[i]) for i in range(n)]
        def valid(i): return F[i] is not None and gtc[i] and not isx(i)
        anchors = select_anchors(F, W, H)

        def score(track):
            e = [math.hypot(track[i][0]-gtc[i][0], track[i][1]-gtc[i][1])
                 for i in range(n) if valid(i) and track.get(i)]
            return (np.mean(e), np.median(e), max(e)) if e else None

        # 공통: 타겟 트랙 유지하며 프레임별 선택
        def run(selfn):
            tg = list(start); vel = [0., 0.]; miss = 0; out = {}
            det_hist = []; aL_hist = []; D_hist = []
            for i in range(n):
                if F[i] is None:
                    continue
                info = F[i]
                liveA = None
                if anchors:
                    lv = []
                    for a in anchors:
                        if a in info['mt']: lv.append(info['dets'][info['mt'][a]])
                        else: lv.append(info['preds'][a])
                    liveA = np.asarray(lv)
                best = selfn(info, tg, vel, miss, det_hist, aL_hist, liveA, D_hist)
                if best is not None:
                    nv = [best[0]-tg[0], best[1]-tg[1]]; m = math.hypot(*nv)
                    if m > VMAX: nv = [nv[0]*VMAX/m, nv[1]*VMAX/m]
                    vel = [VA*vel[0]+(1-VA)*nv[0], VA*vel[1]+(1-VA)*nv[1]]
                    tg = [best[0], best[1]]; miss = 0
                else:
                    tg = [tg[0]+vel[0], tg[1]+vel[1]]; vel = [vel[0]*COAST, vel[1]*COAST]; miss += 1
                out[i] = tuple(tg)
                det_hist.append(info['dets']); aL_hist.append(liveA); D_hist.append(info['D'])
                if len(det_hist) > FPW+1: det_hist.pop(0); aL_hist.pop(0); D_hist.pop(0)
            return out

        def sel_v2(info, tg, vel, miss, dh, ah, lA, Dh):   # 속도 게이트 최근접 아웃라이어
            px, py = tg[0]+vel[0], tg[1]+vel[1]; g = GATE+min(miss, MISSCAP)*MISSK
            best, bd = None, g*g
            for o in info['outl']:
                d = (o[0]-px)**2+(o[1]-py)**2
                if d < bd: bd, best = d, o
            return best

        def sel_v4(info, tg, vel, miss, dh, ah, lA, Dh):   # 강체잔차 최대(변위−배경D, 서치범위, 연속성X)
            if len(dh) < FPW: return sel_v2(info, tg, vel, miss, dh, ah, lA, Dh)
            bgd = info['D'] - Dh[-FPW]; tx, ty = tg; best, bc = None, 9.0
            for o in info['outl']:
                if (o[0]-tx)**2+(o[1]-ty)**2 > SEARCH**2: continue
                p = np.array(o); ok = True
                for k in range(1, FPW+1):
                    Hh = dh[-k]
                    if Hh.shape[0] == 0: ok = False; break
                    j = int(np.argmin((Hh[:,0]-p[0])**2+(Hh[:,1]-p[1])**2))
                    if (Hh[j,0]-p[0])**2+(Hh[j,1]-p[1])**2 > SEARCH**2: ok = False; break
                    p = Hh[j]
                if not ok: continue
                disp = np.array([o[0]-p[0], o[1]-p[1]])
                chg = math.hypot(disp[0]-bgd[0], disp[1]-bgd[1])   # 비강체도(배경 보정)
                if chg > bc: bc, best = chg, o
            return best

        def sel_v5(info, tg, vel, miss, dh, ah, lA, Dh):   # anchor 거리지문 변화 최대(서치범위)
            if lA is None or len(ah) < FPW or ah[-FPW] is None:
                return sel_v2(info, tg, vel, miss, dh, ah, lA, Dh)
            aLp = ah[-FPW]; tx, ty = tg; best, bc = None, 9.0
            for o in info['outl']:
                if (o[0]-tx)**2+(o[1]-ty)**2 > SEARCH**2: continue
                p = np.array(o); ok = True
                for k in range(1, FPW+1):
                    Hh = dh[-k]
                    if Hh.shape[0] == 0: ok = False; break
                    j = int(np.argmin((Hh[:,0]-p[0])**2+(Hh[:,1]-p[1])**2))
                    if (Hh[j,0]-p[0])**2+(Hh[j,1]-p[1])**2 > SEARCH**2: ok = False; break
                    p = Hh[j]
                if not ok: continue
                dn = np.hypot(lA[:,0]-o[0], lA[:,1]-o[1]); dp = np.hypot(aLp[:,0]-p[0], aLp[:,1]-p[1])
                chg = float(np.mean(np.abs(dn-dp)))
                if chg > bc: bc, best = chg, o
            return best

        def oracle():   # GT 최근접 검출(선택 천장)
            out = {}
            for i in range(n):
                if F[i] is None or not gtc[i]: continue
                d = F[i]['dets']
                if d.shape[0] == 0: continue
                j = int(np.argmin((d[:,0]-gtc[i][0])**2+(d[:,1]-gtc[i][1])**2))
                out[i] = (float(d[j,0]), float(d[j,1]))
            return out

        print(f"\n[{name}] anchor {anchors}")
        for tag, fn in [("v2 속도   ", sel_v2), ("v4 강체잔차", sel_v4), ("v5 anchor ", sel_v5)]:
            r = score(run(fn))
            if r: print(f"  {tag}: 평균 {r[0]:3.0f}px 중앙 {r[1]:3.0f} 최대 {r[2]:3.0f}")
        ro = score(oracle())
        if ro: print(f"  오라클(천장): 평균 {ro[0]:3.0f}px 중앙 {ro[1]:3.0f} 최대 {ro[2]:3.0f}")


if __name__ == "__main__":
    main()
