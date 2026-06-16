# 검출박스 외형 leak 신호 — 035137 진짜 타겟 박스 crop vs 데칼 박스 crop.
# 가설: 투명 글라스 도형의 테두리·굴절 패턴이 미세하게 다름(분류기 val 97.6%지만
# 데칼 구분엔 실패했었음 — 그건 모양 4분류였고, 여기는 같은모양 안 인스턴스 구분).
# 측정: GT(빨간점)에 가장 가까운 검출(=진짜) vs 다른 검출(=데칼)의 crop 특징 비교.
import cv2, sys, os, json, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from _gt_score import load_gt
ROOT = os.path.dirname(os.path.abspath(__file__))


def crop_box(frame, cx, cy, w, h, pad=2):
    H, W = frame.shape[:2]
    x0 = max(0, int(cx - w/2 - pad)); y0 = max(0, int(cy - h/2 - pad))
    x1 = min(W, int(cx + w/2 + pad)); y1 = min(H, int(cy + h/2 + pad))
    if x1 <= x0 or y1 <= y0:
        return None
    return frame[y0:y1, x0:x1]


def edge_stats(crop):
    """crop의 edge 강도·분산 — 테두리/굴절 패턴이 강한지."""
    if crop is None or crop.size == 0:
        return None
    g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Sobel — 테두리 강도
    sx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    sy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(sx**2 + sy**2)
    # Laplacian — 굴절(2차 미분, 림의 굽힘)
    lap = cv2.Laplacian(g, cv2.CV_32F, ksize=3)
    return {
        'edge_mean': float(mag.mean()),
        'edge_std':  float(mag.std()),
        'edge_p90':  float(np.percentile(mag, 90)),
        'lap_std':   float(lap.std()),
        'lap_p90':   float(np.percentile(np.abs(lap), 90)),
        'gray_std':  float(g.std()),   # 내부 명도 분산(굴절/하이라이트)
    }


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
    gt = load_gt(name, min_f=0)

    # GT 프레임에서 진짜 타겟 crop(빨간점 최근접 후보) vs 데칼 crop(나머지) — 단계별 분리
    # 백색(f≤24)과 투명(f≥56)을 따로 측정 — 투명 단계만 진짜 leak 신호.
    print(f"\n=== {name} === 외형 leak — GT 구간 진짜 타겟 vs 데칼(단계 분리)")
    by_phase = {'백색(f≤24)': {'t': [], 'd': []}, '투명(f≥56)': {'t': [], 'd': []}}
    n_tgt_assigned = 0
    for fi in sorted(gt):
        cands = rows[fi].get('cands', [])
        if not cands:
            continue
        g = gt[fi]
        # 진짜 타겟 = GT 최근접(반드시 15px 내 — 아니면 검출 공백이라 스킵)
        cd = min(cands, key=lambda c: (c[0]-g[0])**2 + (c[1]-g[1])**2)
        tgt_dist = math.hypot(cd[0]-g[0], cd[1]-g[1])
        if tgt_dist > 15:
            continue   # 진짜 타겟 검출 자체가 없음
        n_tgt_assigned += 1
        # crop 추출 (jsonl cands=[cx,cy,score]만 있음 → 고정 30px box, 도형 ~25~35px)
        BOX = 30
        phase = '백색(f≤24)' if fi <= 24 else '투명(f≥56)' if fi >= 56 else None
        if phase is None:
            continue
        for c in cands:
            cx, cy, sc = c[0], c[1], c[2]
            crp = crop_box(frs[fi], cx, cy, BOX, BOX, pad=0)
            stats = edge_stats(crp)
            if stats is None:
                continue
            stats['score'] = sc
            if c is cd:
                by_phase[phase]['t'].append(stats)
            else:
                by_phase[phase]['d'].append(stats)
    print(f"  진짜 타겟 검출 할당: {n_tgt_assigned}프레임")
    keys = ['edge_mean', 'edge_std', 'edge_p90', 'lap_std', 'lap_p90', 'gray_std', 'score']
    for phase_name, data in by_phase.items():
        tgt_feats = data['t']; decal_feats = data['d']
        print(f"\n  [{phase_name}] 타겟 {len(tgt_feats)} / 데칼 {len(decal_feats)}")
        if not tgt_feats or not decal_feats:
            print("    데이터 부족"); continue
        print("    특징         | 타겟 중앙          | 데칼 중앙          | Cohen's d | 판정")
        for k in keys:
            t = np.array([f[k] for f in tgt_feats])
            d = np.array([f[k] for f in decal_feats])
            tm = np.median(t); dm = np.median(d)
            pooled = math.sqrt((t.std()**2 + d.std()**2) / 2) or 1e-9
            cd_ = (tm - dm) / pooled
            mark = ('★강분리' if abs(cd_) >= 0.8 else '중분리' if abs(cd_) >= 0.5
                    else '약' if abs(cd_) >= 0.2 else '무')
            print(f"    {k:12s} | {tm:6.2f}             | {dm:6.2f}             | "
                  f"{cd_:+5.2f}    | {mark}")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "000_0615_035137")
