# 다중 심판 앙상블 추적기 프로토타입 — 후보(트랙)별 6심판 점수를 그 프레임 순위정규화(0~1) →
# 가중합 → 트랙별 누적(EMA), 최고 누적 = 타겟. 단일신호 이질성을 합산으로 우회. GT16 채점.
import cv2, json, sys, os, math, glob
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.vision.vit_shape_tracker import acquire_white
from _homography_track import violation
from _constellation_score import to_gray_half
from _gt_score import load_gt
import _phase_catalog_score as phase_catalog
ROOT = os.path.dirname(os.path.abspath(__file__))
THR = 40
_TRACE = None   # dict 주면 프레임별 (tt.x,tt.y,gated) 기록(디버그)

ASSOC = 24.0      # 트랙-검출 연관 게이트(예측위치 기준)
PRUNE_MISS = 2
VEL_A = 0.5
PANEL_DECAY = 0.85   # 누적 패널점수 EMA
JUMP_GATE = 68.0     # 연속성 — tt 위치 주변 이 안의 후보만(병합 중 발산한 분리 타겟 도달용)
INHERIT_R = 72.0     # tt 주변 이 안서 새로 생기는 트랙은 부모 누적점수 상속(분리 cum0 문제 해결)
INHERIT_FRAC = 0.9   # 상속 비율
HEAD_A = 0.7         # heading(진행방향) EMA — 1~2프레임 오염 저항
HEAD_MIN = 3.0       # heading 확립으로 인정할 최소 크기(px)
MOVE_MIN = 6.0       # 방향 판정할 최소 이동(미만은 노이즈, 게이트 통과)
REJECT_COS = -0.2    # 이동·heading 코사인 이 미만이면 거부(역방향=데칼)
REACQ_R = 78.0       # 분리 스파이크 재획득 넓은 반경(드리프트된 tt서 ~70px 타겟 도달)
REACQ_REL = 30.0     # 재획득 후보 배경대비 속도 하한(분리 점프 스파이크)
REACQ_MARGIN = 14.0  # 현 tt보다 이만큼 더 강해야 전환
REACQ_TT_MAX = 20.0  # 현 tt가 데칼처럼 보일 때만(자기 anom 낮음) 재획득 — 정상판(타겟=고anom) 보호
REACQ_AGE = 3        # 재획득 후보는 갓 분리된 새 트랙만(age≤) — 오래된 데칼 오발 차단
AREA_SPIKE = 1.15    # tt 박스면적이 최근중앙의 이 배 넘으면 병합 스파이크
AREA_W = 8           # 박스면적 최근 윈도(프레임)
MERGE_WINDOW = 4     # 박스 스파이크 후 이 프레임 내에서만 재획득 허용(진짜 병합 한정)
USE_MERGE_GATE = False  # 박스면적 스파이크 게이트 — 약신호라 good/bad 재획득 거꾸로 가름(끔)


def _load_wjsonl(path):
    if not os.path.exists(path):
        return None
    return [json.loads(l) for l in open(path, encoding='utf-8')]


USE_BG_JUDGE = False
BG_POS_TOL = 10.0
BG_AREA_TOL = 6.0
BG_ASPECT_TOL = 6.0
BG_PENALTY_W = 1.0
BG_LOCAL_SEARCH = 8


def _box_area_at(wrow, x, y):
    """wrow(재검출 박스들 [cx,cy,w,h,score])에서 (x,y) 최근접 박스 면적. 없으면 0."""
    if not wrow:
        return 0.0
    best, bd = 0.0, 1e18
    for b in wrow:
        d = (b[0] - x) ** 2 + (b[1] - y) ** 2
        if d < bd:
            bd = d; best = b[2] * b[3]
    return best
DWELL_W = 8          # 머묾 측정 윈도(프레임)

# 심판 = anom(raw 검출속도−배경) + viol(강체위반) 2개만. 진단: 나머지는 지터·비점양으로 죽음.
def background_explain_penalty(candidate, expected_background,
                               pos_tol=BG_POS_TOL,
                               area_tol_pct=BG_AREA_TOL,
                               aspect_tol_pct=BG_ASPECT_TOL):
    explained, _ = phase_catalog.explain_background(
        [candidate],
        expected_background,
        pos_tol=pos_tol,
        area_tol_pct=area_tol_pct,
        aspect_tol_pct=aspect_tol_pct,
    )
    if not explained:
        return 0.0
    d = explained[0][2]
    return max(0.0, 1.0 - d / max(pos_tol, 1e-6))


def _candidate_with_shape(bgsets, frame_i, x, y, score):
    if not bgsets or frame_i >= len(bgsets):
        return (float(x), float(y), float("nan"), float("nan"), float(score))
    cands = bgsets[frame_i]
    if not cands:
        return (float(x), float(y), float("nan"), float("nan"), float(score))
    near = min(cands, key=lambda c: (c[0] - x) ** 2 + (c[1] - y) ** 2)
    if math.hypot(near[0] - x, near[1] - y) <= 25.0:
        return near
    return (float(x), float(y), float("nan"), float("nan"), float(score))


W_DEFAULT = dict(j1=1.0, j2=1.0)


def vortex_field(prev8, cur8, mt=0.4):
    """vortex score 필드 — 배경 median 광류 빼고 8방향 집중도 누적. 자전 영역 높음."""
    flow = cv2.calcOpticalFlowFarneback(prev8, cur8, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    flow[..., 0] -= float(np.median(flow[..., 0]))
    flow[..., 1] -= float(np.median(flow[..., 1]))
    mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1], angleInDegrees=True)
    active = (mag > mt).astype(np.uint8)
    bins = (ang / 45.0).astype(np.uint8) % 8
    sc = np.zeros(cur8.shape, np.float32); k = np.ones((15, 15), np.uint8)
    for b in range(8):
        sc += cv2.dilate(((bins == b) & active).astype(np.uint8), k)
    return sc


def _patch(field, x, y, r=8):
    H, W = field.shape
    x0, x1 = max(0, int(x) - r), min(W, int(x) + r)
    y0, y1 = max(0, int(y) - r), min(H, int(y) + r)
    p = field[y0:y1, x0:x1]
    return float(np.mean(p)) if p.size else 0.0


class Track:
    __slots__ = ('tid', 'x', 'y', 'vx', 'vy', 'score', 'age', 'miss', 'panel',
                 'px', 'py', 'hist', 'accel', 'seen', 'fs', 'anom')
    def __init__(self, tid, x, y, score):
        self.tid = tid; self.x = x; self.y = y; self.vx = 0.0; self.vy = 0.0
        self.score = score; self.age = 1; self.miss = 0; self.panel = 0.0
        self.px = x; self.py = y; self.hist = [(x, y)]
        self.accel = 0.0; self.seen = []; self.fs = 0.0; self.anom = 0.0
    def predict(self):
        return self.x + self.vx, self.y + self.vy
    def hit(self, nx, ny, sc):
        ovx, ovy = self.x - self.px, self.y - self.py   # 직전 raw 속도
        nvx, nvy = nx - self.x, ny - self.y             # 현재 raw 속도
        self.accel = math.hypot(nvx - ovx, nvy - ovy)   # 가속도(매끄러움)
        self.vx = VEL_A * self.vx + (1 - VEL_A) * nvx
        self.vy = VEL_A * self.vy + (1 - VEL_A) * nvy
        self.px, self.py = self.x, self.y
        self.x, self.y = nx, ny; self.score = sc; self.age += 1; self.miss = 0
        self.hist.append((nx, ny))
        if len(self.hist) > DWELL_W + 1:
            self.hist.pop(0)


def rank_norm(vals):
    """값 리스트 → 순위 정규화 0~1(클수록 1). 동률 평균순위."""
    n = len(vals)
    if n <= 1:
        return [1.0] * n
    order = np.argsort(np.argsort(vals))   # 0..n-1 순위
    return [o / (n - 1) for o in order]


def run(name, W=W_DEFAULT):
    mp4 = os.path.join(ROOT, '_record_debug', name + '.mp4')
    rows = [json.loads(l) for l in open(mp4[:-4] + '.jsonl', encoding='utf-8')]
    wrows = _load_wjsonl(mp4[:-4] + '.wjsonl')   # 재검출 박스(w/h) — 면적 스파이크용
    cap = cv2.VideoCapture(mp4); frs = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frs.append(f)
    cap.release()
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in frs]
    bgsets = None; bg_period = 0; bg_prep_end = 0
    if USE_BG_JUDGE:
        bg_prep_end, bg_white = phase_catalog.detect_prep(frs)
        bgsets = phase_catalog.candidate_sets(rows, wrows, bg_white)
        bg_period, _ = phase_catalog.estimate_period_lag(bgsets, bg_prep_end)
    prepped = False; lastwc = None; prev_dp = None
    tracks = []; tt = None; nexttid = 0; out = {}
    prep_seen = 0; pg = None; prev8 = None
    hx = 0.0; hy = 0.0; out_prev = None   # heading(진행방향 EMA), 직전 출력
    area_hist = []; spike_age = 999       # tt 박스면적 이력, 스파이크 후 경과(병합 윈도우)
    for i in range(len(frs)):
        cands = [(c[0], c[1], c[2]) for c in rows[i]['cands'] if c[2] >= 0.1]
        dp = np.asarray([[c[0], c[1]] for c in cands], float) if cands else np.empty((0, 2))
        bx = by = 0.0
        if pg is not None and grays[i].shape == pg.shape:
            (bx, by), _ = cv2.phaseCorrelate(pg, grays[i])
        pg = grays[i]
        wb = acquire_white(frs[i]); wc = None
        big = wb is not None and wb[2] >= 50 and wb[3] >= 50
        if wb is not None and wb[2] >= 20:
            wc = (wb[0] + wb[2] / 2.0, wb[1] + wb[3] / 2.0)
        if big and wc:
            lastwc = wc; prep_seen += 1; out[i] = wc
        else:
            if not prepped and lastwc is not None and prep_seen >= 20:
                prepped = True
                tt = Track(nexttid, lastwc[0], lastwc[1], 1.0); nexttid += 1
                tracks = [tt]
            if prepped and tt is not None:
                viol = violation(prev_dp, dp) if prev_dp is not None else {}
                # 연관(모션예측 NN)
                for t in tracks:
                    t.miss += 1
                used = set()
                order = sorted(range(dp.shape[0]),
                               key=lambda j: (dp[j, 0] - tt.x) ** 2 + (dp[j, 1] - tt.y) ** 2)
                detj_of = {}
                for j in order:
                    bestt, bd = None, ASSOC ** 2
                    for t in tracks:
                        if id(t) in used:
                            continue
                        px, py = t.predict()
                        d2 = (px - dp[j, 0]) ** 2 + (py - dp[j, 1]) ** 2
                        if d2 < bd:
                            bd, bestt = d2, t
                    if bestt is not None:
                        bestt.hit(dp[j, 0], dp[j, 1], cands[j][2]); used.add(id(bestt))
                        detj_of[id(bestt)] = j
                    else:
                        nt = Track(nexttid, dp[j, 0], dp[j, 1], cands[j][2]); nexttid += 1
                        # tt 주변 새 트랙은 부모 누적 상속 — 분리 시 타겟이 cum0으로 지는 것 방지
                        if (dp[j, 0] - tt.x) ** 2 + (dp[j, 1] - tt.y) ** 2 <= INHERIT_R ** 2:
                            nt.panel = INHERIT_FRAC * tt.panel
                        tracks.append(nt); used.add(id(nt)); detj_of[id(nt)] = j
                # tt coast(미갱신)
                if tt.miss > 0:
                    tt.x, tt.y = tt.predict()
                tracks = [t for t in tracks if t is tt or t.miss <= PRUNE_MISS]
                # 검출 이력 갱신(전 트랙) — j4 검출지속성용
                for t in tracks:
                    t.seen.append(1 if t.miss == 0 else 0)
                    if len(t.seen) > DWELL_W:
                        t.seen.pop(0)
                # 활성 후보(이번 프레임 검출됨)
                act = [t for t in tracks if t.miss == 0]
                if act:
                    # anom = raw 검출속도(현재검출 − 직전 최근접검출) − 배경. 트랙px 아닌 raw(진단).
                    j1 = []; j2 = []
                    for t in act:
                        dj = detj_of.get(id(t), -1)
                        if prev_dp is not None and prev_dp.shape[0] and dj >= 0:
                            kk = int(np.argmin((prev_dp[:, 0] - t.x) ** 2 + (prev_dp[:, 1] - t.y) ** 2))
                            vx, vy = t.x - prev_dp[kk, 0], t.y - prev_dp[kk, 1]
                        else:
                            vx, vy = 0.0, 0.0
                        j1.append(math.hypot(vx - bx, vy - by))                # 배경 비동조(raw)
                        j2.append(viol.get(dj, 0.0))                           # 강체 위반
                    expected_bg = []
                    if USE_BG_JUDGE and bgsets is not None and bg_period > 0:
                        lag = phase_catalog.choose_local_lag(
                            bgsets, i, bg_period, bg_prep_end, BG_LOCAL_SEARCH)
                        if i - lag >= 0:
                            expected_bg = bgsets[i - lag]
                    bgp = []
                    for t in act:
                        penalty = 0.0
                        dj = detj_of.get(id(t), -1)
                        if USE_BG_JUDGE and expected_bg and dj >= 0:
                            cand5 = _candidate_with_shape(
                                bgsets, i, t.x, t.y, cands[dj][2])
                            penalty = background_explain_penalty(cand5, expected_bg)
                        bgp.append(penalty)
                    n1, n2 = rank_norm(j1), rank_norm(j2)
                    for k, t in enumerate(act):
                        t.anom = j1[k]                                # raw 배경대비 속도(재획득용)
                        t.fs = W['j1'] * n1[k] + W['j2'] * n2[k] - BG_PENALTY_W * bgp[k]
                        t.panel = PANEL_DECAY * t.panel + t.fs        # 누적(참고)
                    # 연속성 base — tt '위치' 주변 게이트.
                    gated = [t for t in act if (t.x - tt.x) ** 2 + (t.y - tt.y) ** 2 <= JUMP_GATE ** 2]
                    # 방향 일관성 — heading 확립됐으면, tt에서 후보로의 이동이 heading을 크게
                    # 뒤집는(역방향) 후보 거부(데칼). 남으면 그것만, 다 거부면 게이트 유지(coast 유도).
                    hmag = math.hypot(hx, hy)
                    if hmag >= HEAD_MIN:
                        cons = []
                        for t in gated:
                            mx, my = t.x - tt.x, t.y - tt.y
                            mm = math.hypot(mx, my)
                            if mm <= MOVE_MIN or (mx * hx + my * hy) / (mm * hmag) >= REJECT_COS:
                                cons.append(t)
                        if cons:
                            gated = cons
                    if gated:
                        tt = max(gated, key=lambda t: t.panel)   # 누적점수(상속으로 분리 타겟도 공정)
                    # 분리 스파이크 재획득 — 넓은 반경서 배경대비 강한(분리 점프) 검출로 전환.
                    # 현 tt보다 +마진 강해야(정상판 무회귀). 점프상한·게이트 우회.
                    # tt 박스면적 스파이크(병합) 감지 — 재검출 w/h 기반
                    if wrows is not None and i < len(wrows):
                        ar = _box_area_at(wrows[i], tt.x, tt.y)
                        med = np.median(area_hist) if len(area_hist) >= 3 else ar
                        spike_age = 0 if (med > 0 and ar > AREA_SPIKE * med) else spike_age + 1
                        area_hist.append(ar)
                        if len(area_hist) > AREA_W:
                            area_hist.pop(0)
                    merge_ok = (not USE_MERGE_GATE) or wrows is None or spike_age <= MERGE_WINDOW
                    if tt.anom < REACQ_TT_MAX and merge_ok:   # 데칼처럼 보이고 + 병합 직후만 재획득
                        re_best = max(REACQ_REL, tt.anom + REACQ_MARGIN); re_cand = None
                        for t in act:
                            if t is tt or t.age > REACQ_AGE:   # 갓 분리된 새 트랙만(오래된 데칼 오발 차단)
                                continue
                            if (t.x - tt.x) ** 2 + (t.y - tt.y) ** 2 > REACQ_R ** 2:
                                continue
                            if t.anom > re_best:
                                re_best = t.anom; re_cand = t
                        if re_cand is not None:
                            tt = re_cand
                    if _TRACE is not None:
                        _TRACE[i] = (tt.x, tt.y, round(hx, 1), round(hy, 1),
                                     [(round(t.x), round(t.y)) for t in gated])
                out[i] = (tt.x, tt.y)
                if out_prev is not None:   # heading EMA(출력 이동)
                    hx = HEAD_A * hx + (1 - HEAD_A) * (tt.x - out_prev[0])
                    hy = HEAD_A * hy + (1 - HEAD_A) * (tt.y - out_prev[1])
                out_prev = (tt.x, tt.y)
        prev_dp = dp
    return out


def score_clip(name, W=W_DEFAULT):
    gt = load_gt(name)
    if not gt:
        return None
    res = run(name, W)
    errs = [math.hypot(res[fi][0] - g[0], res[fi][1] - g[1])
            for fi, g in gt.items() if res.get(fi)]
    if not errs:
        return None
    return np.mean(errs), len(errs) / len(gt)


def main():
    names = sorted(os.path.basename(d) for d in
                   glob.glob(os.path.join(ROOT, '_gt_frames', '*')) if os.path.isdir(d))
    ok = 0; total = 0; means = []
    print("=== 다중 심판 앙상블 GT 채점 (균등투표, ≤40px=성공) ===")
    for name in names:
        r = score_clip(name)
        if r is None:
            continue
        total += 1; m, cov = r
        suc = m <= THR and cov >= 0.9; ok += suc; means.append(m)
        print(f"  {name}: 평균 {m:3.0f}px 유지 {cov*100:3.0f}% [{'성공' if suc else '실패'}]")
    if means:
        print(f"\n  >>> {ok}/{total} 성공, 평균 {np.mean(means):.0f}px (baseline 88·vortex 54)")


if __name__ == "__main__":
    main()
