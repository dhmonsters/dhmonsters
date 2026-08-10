# 투명 도형 강체 별자리 추적 — 배경 데칼은 강체(상대거리 불변) 템플릿이 통째 평행이동.
# 별자리를 lock 시점 고정 템플릿으로 보관, 매 프레임 단일 평행이동 D로 전체 정합(멤버 불멸).
# 정합에서 빠지는 아웃라이어 = 타겟. 판별을 '타겟 순간값'이 아니라 '데칼 강체 일치 투표'에 둔다.
from __future__ import annotations

import math
import numpy as np

CT_INLIER_TOL = 14.0    # 데칼 정합 인라이어 허용(px) — (템플릿+D) 대 검출 거리
CT_TGT_GATE   = 30.0    # 타겟 후보 게이트(px), miss 비례 확대
CT_TGT_MISS_K = 8.0     # miss당 게이트 확대
CT_GATE_MISS_CAP = 4    # 게이트 확대 miss 상한
CT_VEL_ALPHA  = 0.6     # 타겟 속도 EMA(클수록 직전 유지)
CT_VEL_MAX    = 16.0    # 타겟 이미지속도 상한(px/f)
CT_COAST_DECAY = 0.9    # 미검출 coast 시 속도 감쇠
CT_LOCK_GATE  = 30.0    # lock 시 이 안의 검출은 타겟으로 보고 템플릿서 제외
CT_REG_MAXSTEP = 24.0   # 프레임당 D 변화 상한(배경 ≤~15px/f) — 정합 RANSAC 제약
CT_PREP_CLUSTER_R = 11.0  # 준비단계 글로벌좌표 클러스터 반경(px) — 같은 데칼 묶음
CT_PREP_MINHITS_F = 0.12  # 데칼 인정 최소 출현비(준비 프레임 대비) — 미만은 타겟궤적/잡음


class ConstellationTracker:
    """강체 템플릿 정합 추적. template=고정 데칼배치, D=누적 평행이동, target=정합 아웃라이어."""

    def __init__(self, inlier_tol=CT_INLIER_TOL, tgt_gate=CT_TGT_GATE,
                 vel_alpha=CT_VEL_ALPHA):
        self._tol = inlier_tol
        self._gate = tgt_gate
        self._va = vel_alpha
        self.reset()

    def reset(self):
        self._template = None       # (M,2) 데칼 글로벌 위치(고정)
        self._D = np.zeros(2)       # 누적 평행이동
        self._target = None         # [x,y]
        self._vel = [0.0, 0.0]
        self._miss = 0
        self._bounds = None
        self._last_outliers = []
        # 준비단계 카탈로그 상태
        self._prep_D = np.zeros(2)
        self._prep_dets = []        # 프레임별 검출 (M,2)
        self._prep_Dh = []          # 프레임별 누적 D(드리프트 보정 전)
        self._prep_frames = 0

    def set_bounds(self, w, h):
        self._bounds = (float(w), float(h))

    @property
    def locked(self):
        return self._target is not None

    @property
    def center(self):
        return (self._target[0], self._target[1]) if self._target else None

    # ── 잠금: 타겟=흰색중심, 나머지 검출=고정 템플릿 부트스트랩 ──
    def lock(self, x, y, dets=None):
        self._target = [float(x), float(y)]
        self._vel = [0.0, 0.0]
        self._miss = 0
        self._D = np.zeros(2)
        if dets:
            tmpl = [[float(d[0]), float(d[1])] for d in dets
                    if (d[0] - x) ** 2 + (d[1] - y) ** 2 > CT_LOCK_GATE ** 2]
            self._template = np.asarray(tmpl, dtype=np.float64) if tmpl else None

    # ── 준비 4초 단계: 프레임별 검출·누적D 저장(배경 1회전 동안 전 데칼 카탈로그) ──
    # dD = 직전→현재 배경 평행이동(광류 median, 솔버가 계산해 전달).
    def prep_observe(self, dets, dD=(0.0, 0.0)):
        self._prep_D = self._prep_D + np.asarray(dD, dtype=np.float64)
        dpts = np.asarray([[float(c[0]), float(c[1])] for c in dets], dtype=np.float64) \
            if dets else np.empty((0, 2))
        self._prep_dets.append(dpts)
        self._prep_Dh.append(self._prep_D.copy())
        self._prep_frames += 1

    def _build_catalog(self, dets_list, Dlist):
        """프레임별 (검출 - D)를 글로벌좌표로 모아 클러스터링 → 데칼 별자리(or None)."""
        pts = []
        for dpts, Dc in zip(dets_list, Dlist):
            for p in dpts:
                pts.append((p[0] - Dc[0], p[1] - Dc[1]))
        if not pts:
            return None
        pts = np.asarray(pts, dtype=np.float64)
        min_hits = max(5, int(CT_PREP_MINHITS_F * max(self._prep_frames, 1)))
        a = self._cluster(pts, CT_PREP_CLUSTER_R, min_hits)
        return np.asarray(a, dtype=np.float64) if a else None

    # ── START: 2-pass 번들조정으로 드리프트 없는 완전 별자리 구축.
    #    ①광류D로 거친 카탈로그 ②각 준비프레임을 거친 카탈로그에 절대 재정합→누적없는 D'
    #    ③D'로 카탈로그 재구성(데칼 번짐 제거→~실제 데칼 수). 타겟(중앙정지)은 글로벌 이동→클러스터 안 됨 ──
    def finalize_catalog(self, white_x, white_y):
        Dh = np.asarray(self._prep_Dh, dtype=np.float64)
        self._template = self._build_catalog(self._prep_dets, Dh)   # pass1
        if self._template is not None and len(Dh):
            Dp = np.asarray([self._register(d, D0, maxstep=40)
                             for d, D0 in zip(self._prep_dets, Dh)])  # pass2 재정합
            refined = self._build_catalog(self._prep_dets, Dp)
            if refined is not None:
                self._template = refined
                self._D = Dp[-1].copy()
            else:
                self._D = Dh[-1].copy()
        else:
            self._D = Dh[-1].copy() if len(Dh) else self._prep_D.copy()
        self._target = [float(white_x), float(white_y)]
        self._vel = [0.0, 0.0]; self._miss = 0
        return 0 if self._template is None else len(self._template)

    @staticmethod
    def _cluster(pts, r, min_hits):
        used = np.zeros(len(pts), bool); anchors = []
        r2 = r * r
        for i in range(len(pts)):
            if used[i]:
                continue
            d2 = (pts[:, 0] - pts[i, 0]) ** 2 + (pts[:, 1] - pts[i, 1]) ** 2
            idx = np.where((d2 <= r2) & (~used))[0]
            if len(idx) >= min_hits:
                anchors.append(pts[idx].mean(0)); used[idx] = True
            else:
                used[i] = True
        return anchors

    # ── 현재 예측 데칼 위치 = 템플릿 + D ──
    def _preds(self):
        if self._template is None:
            return np.empty((0, 2))
        return self._template + self._D

    # ── 절대 강체 정합(RANSAC) — 고정 템플릿에 가장 많은 검출을 맞추는 D를 D0 주변 ±maxstep서 탐색.
    #    매 프레임 전역 템플릿에 절대 정합 → 드리프트 누적 없음, 오정합 점프 방지 ──
    def _register(self, dpts, D0=None, maxstep=CT_REG_MAXSTEP):
        tmpl = self._template
        prevD = self._D if D0 is None else np.asarray(D0, dtype=np.float64)
        if tmpl is None or dpts.shape[0] == 0:
            return prevD
        tol2 = self._tol ** 2
        ms2 = maxstep ** 2
        base = tmpl + prevD                       # 탐색 중심 예측 위치
        best_D, best_cnt = prevD, -1
        seen = set()
        for i in range(tmpl.shape[0]):
            dd = dpts - base[i]
            for j in range(dpts.shape[0]):
                step = dd[j]
                if step[0] * step[0] + step[1] * step[1] > ms2:
                    continue                       # D 변화 과대 → 후보 제외
                D = prevD + step
                key = (round(D[0]), round(D[1]))
                if key in seen:
                    continue
                seen.add(key)
                P = tmpl + D                       # (M,2)
                diff = P[:, None, :] - dpts[None, :, :]
                mind = (diff[..., 0] ** 2 + diff[..., 1] ** 2).min(axis=1)
                cnt = int((mind <= tol2).sum())
                if cnt > best_cnt:
                    best_cnt, best_D = cnt, D
        return best_D

    def update(self, dets, white_center=None):
        """dets=[(x,y,score),...], white_center=(x,y)|None. 반환 타겟 (x,y)|None."""
        dpts = np.asarray([[float(c[0]), float(c[1])] for c in dets], dtype=np.float64) \
            if dets else np.empty((0, 2))
        # 절대 강체 정합 → D
        self._D = self._register(dpts)
        preds = self._preds()

        # 예측↔검출 그리디 정합 → used det, 아웃라이어
        used = set()
        for p in preds:
            best, bd = -1, self._tol ** 2
            for j in range(dpts.shape[0]):
                if j in used:
                    continue
                dist2 = (dpts[j, 0] - p[0]) ** 2 + (dpts[j, 1] - p[1]) ** 2
                if dist2 < bd:
                    bd, best = dist2, j
            if best >= 0:
                used.add(best)
        outliers = [(float(dpts[j, 0]), float(dpts[j, 1]))
                    for j in range(dpts.shape[0]) if j not in used]
        self._last_outliers = outliers

        if white_center is not None:
            wc = [float(white_center[0]), float(white_center[1])]
            if self._target is not None:
                nv = [wc[0] - self._target[0], wc[1] - self._target[1]]
                self._vel = self._cap_vel(self._va * self._vel[0] + (1 - self._va) * nv[0],
                                          self._va * self._vel[1] + (1 - self._va) * nv[1])
            self._target = wc
            self._miss = 0
            return self.center

        if self._target is None:
            return None

        # 타겟 예측 = 직전 + 이미지속도(배경 D와 독립). 게이트 내 최근접 아웃라이어 선택
        px = self._target[0] + self._vel[0]
        py = self._target[1] + self._vel[1]
        gate = self._gate + min(self._miss, CT_GATE_MISS_CAP) * CT_TGT_MISS_K
        best, bd = None, gate ** 2
        for ox, oy in outliers:
            dist2 = (ox - px) ** 2 + (oy - py) ** 2
            if dist2 < bd:
                bd, best = dist2, (ox, oy)

        if best is not None:
            nv = [best[0] - self._target[0], best[1] - self._target[1]]
            self._vel = self._cap_vel(self._va * self._vel[0] + (1 - self._va) * nv[0],
                                      self._va * self._vel[1] + (1 - self._va) * nv[1])
            self._target = [best[0], best[1]]
            self._miss = 0
        else:
            self._target = [px, py]
            self._vel = [self._vel[0] * CT_COAST_DECAY, self._vel[1] * CT_COAST_DECAY]
            self._miss += 1
        return self.center

    @staticmethod
    def _cap_vel(vx, vy):
        m = math.hypot(vx, vy)
        if m > CT_VEL_MAX:
            vx *= CT_VEL_MAX / m; vy *= CT_VEL_MAX / m

    @staticmethod
    def _cap_vel(vx, vy):
        m = math.hypot(vx, vy)
        if m > CT_VEL_MAX:
            vx *= CT_VEL_MAX / m; vy *= CT_VEL_MAX / m
        return [vx, vy]

    # 진단 호환
    @property
    def _anchors(self):
        return [list(p) for p in self._preds()]
