# 투명 도형 주기 차분 추적 — 배경이 주기 T로 반복하니 frame[t]−정렬(frame[t−T])로 배경 상쇄, 타겟만 잔차.
# 검출/연속성 불요. 백색단계는 밝기로 잠금, 투명단계는 잔차 peak(가중 무게중심)로 추적. VortexTracker와 동일 API.
from __future__ import annotations

import cv2
import math
import numpy as np

PT_BUF = 78           # 그레이 ring buffer 길이(주기 최대 ~70 커버)
PT_SEARCH = 38        # 직전 중심 주변 잔차 peak 탐색 반경(px)
PT_JUMP = 26          # 프레임당 최대 이동(노이즈 점프 억제)
PT_TMIN, PT_TMAX = 40, 70   # 주기 T 탐색 범위(프레임)
PT_T_DEFAULT = 55     # 주기 추정 실패 시 기본값


class PeriodicTracker:
    """주기 차분 기반 투명 도형 추적. 배경 주기 반복 상쇄 → 타겟만 잔차로 남음(검출 무관)."""

    def __init__(self, search=PT_SEARCH):
        self._r = search
        self.reset()

    def reset(self):
        self._buf = []                  # 그레이(uint8) ring
        self._Dcum = []                 # buf[i]와 정렬된 누적 배경이동 D
        self._prev = None               # 직전 그레이(D 증분용)
        self._D = np.zeros(2)
        self._center = None
        self._T = None

    def lock(self, x, y):
        """백색 단계 — 밝기 중심으로 잠금."""
        self._center = [float(x), float(y)]

    @property
    def locked(self):
        return self._center is not None

    @property
    def center(self):
        return (self._center[0], self._center[1]) if self._center else None

    def _push(self, gray):
        # 검증된 오프라인 방식 일치: 그레이 블러 + 다운스케일(0.5) 광류 median(×2) 누적
        gb = cv2.GaussianBlur(gray, (3, 3), 0)
        small = cv2.resize(gb, None, fx=0.5, fy=0.5)
        if self._prev is not None:
            fl = cv2.calcOpticalFlowFarneback(self._prev, small, None, 0.5, 3, 21, 3, 7, 1.5, 0)
            mag = np.sqrt(fl[..., 0] ** 2 + fl[..., 1] ** 2)
            m = mag > 1.5
            if m.sum() > 500:
                self._D = self._D + np.array([float(np.median(fl[..., 0][m])) * 2,
                                              float(np.median(fl[..., 1][m])) * 2])
        self._prev = small
        self._buf.append(gb); self._Dcum.append(self._D.copy())
        if len(self._buf) > PT_BUF:
            self._buf.pop(0); self._Dcum.pop(0)

    def _estimate_T(self):
        n = len(self._Dcum)
        if n < PT_TMIN + 5:
            return None
        D = self._Dcum; bestT, bc = None, 1e9
        for T in range(PT_TMIN, min(PT_TMAX, n - 3) + 1):
            d = [np.hypot(*(D[i] - D[i - T])) for i in range(T, n)]
            if d and np.mean(d) < bc:
                bc, bestT = np.mean(d), T
        return bestT

    def update(self, gray_u8, white_center=None):
        """매 프레임. gray_u8=현재 그레이(uint8). white_center 주어지면 백색 잠금 우선.
        반환: 추적 중심 (x,y) | None(미잠금)."""
        self._push(gray_u8)
        if white_center is not None:                 # 백색 단계 — 밝기 잠금
            self._center = [float(white_center[0]), float(white_center[1])]
            return self.center
        if self._center is None:
            return None
        # 주기 T는 버퍼가 한 주기 이상(≥50f) 찼을 때 한 번만 추정해 고정.
        # (매 프레임 재추정하면 T가 흔들려 frame[t−T] 기준이 바뀌며 추적 불안정 — 측정 확인)
        if self._T is None:
            if len(self._buf) >= 50:
                self._T = self._estimate_T() or PT_T_DEFAULT
            else:
                return self.center               # 주기 미확정 → 직전 위치 유지
        T = self._T
        if len(self._buf) > T:
            cur = self._buf[-1]; j = len(self._buf) - 1 - T
            past = self._buf[j]; sh = self._Dcum[-1] - self._Dcum[j]
            H, W = cur.shape
            warp = cv2.warpAffine(past, np.float32([[1, 0, sh[0]], [0, 1, sh[1]]]), (W, H))
            try:                                     # 정렬 미세보정
                (dx, dy), _ = cv2.phaseCorrelate(warp.astype(np.float32), cur.astype(np.float32))
                if abs(dx) < 20 and abs(dy) < 20:
                    warp = cv2.warpAffine(past, np.float32([[1, 0, sh[0]+dx], [0, 1, sh[1]+dy]]), (W, H))
            except cv2.error:
                pass
            res = cv2.absdiff(cur, warp).astype(np.float32)
            # 유령 억제: 한 주기 전 흰색 타겟(밝은 픽셀) 잔차 제거
            res[cv2.dilate((warp > 200).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0] = 0
            res = cv2.GaussianBlur(res, (0, 0), 4)
            tx, ty = int(self._center[0]), int(self._center[1])
            x0, x1 = max(0, tx-self._r), min(W, tx+self._r)
            y0, y1 = max(0, ty-self._r), min(H, ty+self._r)
            win = res[y0:y1, x0:x1]
            if win.size:
                w = win.copy(); w[w < 0.6 * w.max()] = 0
                if w.sum() > 0:
                    ys, xs = np.mgrid[0:win.shape[0], 0:win.shape[1]]
                    nx = x0 + (xs * w).sum() / w.sum()
                    ny = y0 + (ys * w).sum() / w.sum()
                    d = math.hypot(nx - self._center[0], ny - self._center[1])
                    if d > PT_JUMP:
                        nx = self._center[0] + (nx - self._center[0]) * PT_JUMP / d
                        ny = self._center[1] + (ny - self._center[1]) * PT_JUMP / d
                    self._center = [nx, ny]
        return self.center
