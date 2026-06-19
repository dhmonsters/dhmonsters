# 투명 도형 vortex 추적 — 타겟 자전이 만드는 광류 소용돌이로 추적(검출/분류 불요).
# 백색 단계는 밝기로 잠금(lock), 투명 전환 시 광류 소용돌이로 추적. 배경 광류 빼서 타겟만 부각.
from __future__ import annotations

import cv2
import numpy as np
import math

VTX_MOTION_THR = 0.4    # 광류 활성 임계(px/f) — 미만은 정지로 간주
VTX_VORTEX_THR = 5.0    # 소용돌이 score 임계(8방향 중 겹침 수)
VTX_SEARCH_R   = 70     # 직전 중심 주변 탐색 반경(px)
VTX_ALPHA      = 0.5    # EMA 평활(클수록 직전 유지)
VTX_MAX_SPEED  = 40     # 단일 프레임 최대 이동(px)


class VortexTracker:
    """광류 소용돌이 기반 투명 도형 추적. 타겟만 자전→소용돌이, 배경은 평행이동→없음."""

    def __init__(self, motion_thr=VTX_MOTION_THR, vortex_thr=VTX_VORTEX_THR,
                 search_r=VTX_SEARCH_R, alpha=VTX_ALPHA, max_speed=VTX_MAX_SPEED):
        self._mt = motion_thr; self._vt = vortex_thr; self._r = search_r
        self._alpha = alpha; self._ms = max_speed
        self._prev = None
        self._center = None

    def reset(self):
        self._prev = None; self._center = None

    def lock(self, x, y):
        """백색 단계 — 밝기 중심으로 잠금(투명 전환 시 여기서 출발)."""
        self._center = [float(x), float(y)]

    @property
    def locked(self):
        return self._center is not None

    @property
    def center(self):
        return (self._center[0], self._center[1]) if self._center else None

    @staticmethod
    def _compute_vortex(flow, center, search_r, mt, vt):
        rh, rw = flow.shape[:2]
        # ROI median 광류 = 배경 스크롤 → 빼면 타겟 자전 잔차가 부각(핵심)
        y0 = max(0, int(center[1]-search_r)); y1 = min(rh, int(center[1]+search_r))
        x0 = max(0, int(center[0]-search_r)); x1 = min(rw, int(center[0]+search_r))
        roi = flow[y0:y1, x0:x1]
        if roi.size:
            flow = flow.copy()
            flow[..., 0] -= float(np.median(roi[..., 0]))
            flow[..., 1] -= float(np.median(roi[..., 1]))
        mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1], angleInDegrees=True)
        active = (mag > mt).astype(np.uint8)
        bins = (ang / 45.0).astype(np.uint8) % 8       # 8방향 양자화
        score = np.zeros((rh, rw), np.float32)
        kernel = np.ones((15, 15), np.uint8)
        for b in range(8):
            score += cv2.dilate(((bins == b) & active).astype(np.uint8), kernel)
        rmask = np.zeros((rh, rw), np.uint8)
        cv2.circle(rmask, (int(center[0]), int(center[1])), search_r, 1, -1)
        masked = score * rmask
        _, top = cv2.threshold(masked, vt, 255, cv2.THRESH_BINARY)
        cnts, _ = cv2.findContours(top.astype(np.uint8), cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            Mo = cv2.moments(max(cnts, key=cv2.contourArea))
            if Mo['m00'] > 0:
                return (Mo['m10']/Mo['m00'], Mo['m01']/Mo['m00'])
        return None

    def update(self, gray_u8, white_center=None):
        """매 프레임. gray_u8=현재 그레이(uint8). white_center 주어지면 백색 잠금 우선.
        반환: 추적 중심 (x,y) | None(미잠금)."""
        prev = self._prev
        self._prev = gray_u8
        if white_center is not None:        # 백색 단계 — 밝기 잠금
            self._center = [float(white_center[0]), float(white_center[1])]
            return self.center
        if self._center is None or prev is None:
            return self.center              # 아직 미잠금
        # 투명 단계 — 광류 소용돌이
        flow = cv2.calcOpticalFlowFarneback(prev, gray_u8, None, 0.5, 3, 15, 3, 5, 1.2, 0)
        res = self._compute_vortex(flow, self._center, self._r, self._mt, self._vt)
        if res is not None:
            nx = self._alpha*self._center[0] + (1-self._alpha)*res[0]
            ny = self._alpha*self._center[1] + (1-self._alpha)*res[1]
            d = math.hypot(nx-self._center[0], ny-self._center[1])
            if d > self._ms:
                nx = self._center[0] + (nx-self._center[0])*self._ms/d
                ny = self._center[1] + (ny-self._center[1])*self._ms/d
            self._center = [nx, ny]
        return self.center
