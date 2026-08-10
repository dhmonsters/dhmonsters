# 투명 도형을 ViT 추적 + 무동결 복구 루프로 추적하는 모듈
# update()는 이미 커서가 제거된 DET 프레임을 받는다. 커서 마스킹은 호출자 책임.
from __future__ import annotations

import cv2
import numpy as np

VIT_MAX_JUMP = 30       # ViT 결과 채택 게이트 — 직전 위치 대비 최대 점프(px)
VIT_SCORE_MIN = 0.0     # ViT 추적 점수 하한 (실측상 점수 게이트 효과 미미 → 기본 무효)
BLOB_ROI = 80           # 복구 블롭 탐색 ROI 한 변(px)
BLOB_MISS_LIMIT = 5     # 연속 블롭 실패 이 횟수 도달 → 전체 재획득 필요 플래그
HISTORY_LEN = 5         # 운동 예측용 중심 이력 길이
RES_BORDER = 12         # 잔차맵 테두리 제거 폭(px) — warp 경계 인공물 차단
RES_BLUR = 31           # 잔차 saliency 블러 커널(홀수)
RES_ROI_HALF = 70       # 잔차 탐색 ROI 반경(px) — 스윕 결과 70이 <80px 89%로 최적(100은 배경 오염)
RES_MIN_SIGNAL = 1.0    # 잔차 채택 최소 피크값
RES_CENTROID_THR = 0.6  # centroid 가중 임계(피크 대비 비율)


def acquire_white(det_bgr, bright_thr=200, min_area=200, size_cap=60):
    """흰색 도형 락온 — 밝기 임계 이진화 후 최대 윤곽의 bbox 반환. 없으면 None."""
    gray = cv2.cvtColor(det_bgr, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, bright_thr, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    b = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(b) < min_area:
        return None
    x, y, w, h = cv2.boundingRect(b)
    cx, cy = x + w / 2, y + h / 2
    w = min(w, size_cap)
    h = min(h, size_cap)
    return (int(cx - w / 2), int(cy - h / 2), int(w), int(h))


def _frosted_score_map(det_bgr):
    """프로스트(서리) 점수맵 — 텍스처 부드러움(굴절로 흐려짐) + 밝기 결합."""
    g = cv2.cvtColor(det_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    lap = cv2.Laplacian(g, cv2.CV_32F, ksize=3)
    localvar = cv2.boxFilter(lap * lap, -1, (15, 15))   # 국소 고주파 에너지
    smooth = 1.0 / (1.0 + localvar * 0.01)              # 흐릴수록 높음
    bright = cv2.boxFilter(g, -1, (15, 15)) / 255.0
    return smooth * 0.6 + bright * 0.4


def find_frosted_blob(det_bgr, pred_cx, pred_cy, ref_area, roi=BLOB_ROI):
    """예측 위치 주변 ROI에서 프로스트 도형 후보 bbox 반환. 2단계 YOLO seam 위치."""
    H, W = det_bgr.shape[:2]
    half = roi // 2
    x0 = max(0, int(pred_cx - half))
    y0 = max(0, int(pred_cy - half))
    x1 = min(W, int(pred_cx + half))
    y1 = min(H, int(pred_cy + half))
    if x1 - x0 < 10 or y1 - y0 < 10:
        return None
    sub = det_bgr[y0:y1, x0:x1]
    score = _frosted_score_map(sub)
    _, mx, _, ml = cv2.minMaxLoc(score)
    if mx <= 0:
        return None
    mask = (score >= mx * 0.85).astype(np.uint8) * 255
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None
    # 면적이 ref_area의 0.3~2.0배인 후보 중 점수 피크에 가장 가까운 것 선택
    best = None
    best_d = 1e9
    for c in cnts:
        a = cv2.contourArea(c)
        if a < ref_area * 0.3 or a > ref_area * 2.0:
            continue
        bx, by, bw, bh = cv2.boundingRect(c)
        d = np.hypot((bx + bw / 2) - ml[0], (by + bh / 2) - ml[1])
        if d < best_d:
            best_d = d
            best = (x0 + bx, y0 + by, bw, bh)
    return best


class ResidualMotionDetector:
    """배경 모션 보상 잔차 검출 — 배경(일정 흐름)을 phaseCorrelate로 정렬해 제거하면
    배경과 다르게 움직이는 타겟만 잔차로 남는다. 외형이 아닌 '움직임'으로 검출."""

    def __init__(self):
        self._prev = None        # 직전 프레임 gray float32
        self._prev_cmask = None  # 직전 프레임 커서 마스크 — 커서 '꼬리' 잔차 제거용
        self._saliency = None    # 최신 잔차 saliency 맵

    def reset(self):
        self._prev = None
        self._prev_cmask = None
        self._saliency = None

    def update(self, gray_f32, cursor_mask=None):
        """매 프레임 호출 — 잔차 saliency 갱신. 첫 프레임은 상태 저장만."""
        if self._prev is not None:
            (sx, sy), _ = cv2.phaseCorrelate(self._prev, gray_f32)
            M = np.float32([[1, 0, sx], [0, 1, sy]])
            h, w = gray_f32.shape
            warped = cv2.warpAffine(self._prev, M, (w, h))
            diff = cv2.absdiff(gray_f32, warped)
            b = RES_BORDER
            diff[:b, :] = 0; diff[-b:, :] = 0; diff[:, :b] = 0; diff[:, -b:] = 0
            # 직전+현재 커서 마스크 합집합 제거 — diff는 두 프레임 차이라
            # 직전 커서 위치(inpaint 인공물)에도 가짜 잔차가 생긴다. 현재 것만 지우면
            # 커서 '꼬리'를 타겟으로 오인 → 추적기가 커서를 역추적하는 폭주 발생(라이브 실증)
            if cursor_mask is not None:
                diff[cursor_mask > 0] = 0
            if self._prev_cmask is not None:
                diff[self._prev_cmask > 0] = 0
            self._saliency = cv2.GaussianBlur(diff, (RES_BLUR, RES_BLUR), 0)
        self._prev = gray_f32
        self._prev_cmask = cursor_mask

    def find(self, pred_cx, pred_cy, roi_half=RES_ROI_HALF, min_signal=RES_MIN_SIGNAL):
        """예측 위치 ROI 내 잔차 가중 centroid 반환 (cx, cy, strength) | None.
        peak가 아닌 centroid — 커서 마스크로 중심이 비어도 림(rim) 잔차의 무게중심=도형 중심."""
        if self._saliency is None:
            return None
        H, W = self._saliency.shape
        x0 = max(0, int(pred_cx) - roi_half)
        y0 = max(0, int(pred_cy) - roi_half)
        x1 = min(W, int(pred_cx) + roi_half)
        y1 = min(H, int(pred_cy) + roi_half)
        if x1 - x0 < 10 or y1 - y0 < 10:
            return None
        sub = self._saliency[y0:y1, x0:x1]
        _, mx, _, _ = cv2.minMaxLoc(sub)
        if mx < min_signal:
            return None
        th = np.where(sub >= mx * RES_CENTROID_THR, sub, 0.0)
        s = th.sum()
        if s <= 0:
            return None
        ys, xs = np.mgrid[0:sub.shape[0], 0:sub.shape[1]]
        cx = x0 + float((th * xs).sum() / s)
        cy = y0 + float((th * ys).sum() / s)
        return (cx, cy, float(mx))


class VitShapeTracker:
    """ViT 외형 추적 + 운동 예측·프로스트 복구로 무동결 추적."""

    def __init__(self, model_path, max_jump=VIT_MAX_JUMP, score_min=VIT_SCORE_MIN,
                 recovery_mode="residual"):
        # recovery_mode: "residual"(기본 — 물리 예측 위치 주변 모션잔차 centroid로 보정) |
        #                "physics"(실측 속도 외삽 + 벽 반사) |
        #                "freeze"(직전 위치 유지, ViT는 내부에서 계속 동작) |
        #                "inertia"(운동 예측 위치로 이동) |
        #                "frosted"(예측 위치 주변 프로스트 블롭으로 ViT 재init)
        self._params = cv2.TrackerVit_Params()
        self._params.net = str(model_path)
        self._max_jump = max_jump
        self._score_min = score_min
        self._mode = recovery_mode
        self._tracker = None
        self._residual = ResidualMotionDetector()
        self._history = []
        self._last_good = None
        self._blob_miss = 0
        self._reject_run = 0
        self._ref_area = 3600.0

    def init(self, frame_bgr, bbox):
        """흰색 락온 bbox로 ViT 초기화 + 상태 리셋."""
        x, y, w, h = (int(v) for v in bbox)
        self._tracker = cv2.TrackerVit_create(self._params)
        self._tracker.init(frame_bgr, (x, y, w, h))
        cx, cy = x + w / 2, y + h / 2
        self._ref_area = float(w * h)
        self._history = [(cx, cy)]
        self._last_good = (cx, cy, (x, y, w, h))
        self._vx = 0.0   # 속도 EMA — ViT 채택 프레임에서만 갱신(예측점 오염 방지)
        self._vy = 0.0
        self._blob_miss = 0
        self._reject_run = 0
        self._residual.reset()   # 팝업 경계에서 잔차 상태 초기화

    @staticmethod
    def _reflect(p, v, hi):
        """벽 반사 — 위치 p+v가 [0,hi] 밖이면 튕겨서 위치·속도 반전."""
        np_ = p + v
        if np_ < 0:
            np_ = -np_
            v = -v
        elif np_ > hi:
            np_ = 2 * hi - np_
            v = -v
        return max(0.0, min(hi, np_)), v

    def needs_reacquire(self):
        """연속 거부가 한계 도달 → 호출자가 acquire_white 재시도해야 함."""
        return self._reject_run >= BLOB_MISS_LIMIT

    def _add_to_history(self, cx, cy):
        self._history.append((cx, cy))
        if len(self._history) > HISTORY_LEN:
            self._history.pop(0)

    def _predict_from_motion(self):
        h = self._history
        if len(h) >= 2:
            dx = np.mean([h[i][0] - h[i - 1][0] for i in range(1, len(h))])
            dy = np.mean([h[i][1] - h[i - 1][1] for i in range(1, len(h))])
            return h[-1][0] + dx, h[-1][1] + dy
        return self._last_good[0], self._last_good[1]

    def _jump_ok(self, cx, cy):
        lx, ly = self._history[-1]
        return np.hypot(cx - lx, cy - ly) <= self._max_jump

    def update(self, frame_bgr, cursor_mask=None, residual_bgr=None):
        """프레임당 1회 — (cx, cy, score, accepted) 반환. 절대 멈추지 않음.
        cursor_mask: 커서 영역 255 마스크(잔차에서 자기 마우스 제외용, 커서 실크기 권장).
        residual_bgr: 잔차 계산용 원본 프레임 — inpaint 프레임은 합성 내용이 매 프레임
        달라져 깜빡임 잔차(커서 꼬리 오인 폭주)를 만들므로 원본 사용 권장. 없으면 frame_bgr."""
        H, W = frame_bgr.shape[:2]
        if self._mode == "residual":
            # 잔차 상태는 연속성이 필요 — ViT 채택 여부와 무관하게 매 프레임 갱신
            src = residual_bgr if residual_bgr is not None else frame_bgr
            gray = cv2.cvtColor(src, cv2.COLOR_BGR2GRAY).astype(np.float32)
            self._residual.update(gray, cursor_mask)
        ok, box = self._tracker.update(frame_bgr)
        try:
            score = float(self._tracker.getTrackingScore())
        except Exception:
            score = 1.0
        cx = box[0] + box[2] / 2
        cy = box[1] + box[3] / 2

        # 1) ViT 게이트 통과 → 정상 사용 + 속도 EMA 갱신(실관측만)
        if ok and self._jump_ok(cx, cy) and score >= self._score_min:
            lgx, lgy = self._last_good[0], self._last_good[1]
            self._vx = self._vx * 0.6 + (cx - lgx) * 0.4
            self._vy = self._vy * 0.6 + (cy - lgy) * 0.4
            self._last_good = (cx, cy, tuple(box))
            self._add_to_history(cx, cy)
            self._reject_run = 0
            return (cx, cy, score, True)

        # 2) 거부 — ViT는 내부에서 계속 동작(재init 안 하면 복귀 여지)
        self._reject_run += 1

        if self._mode == "freeze":
            # 직전 위치 유지
            gx, gy = self._last_good[0], self._last_good[1]
            self._add_to_history(gx, gy)
            return (gx, gy, 0.0, False)

        if self._mode in ("physics", "residual"):
            # 바운싱 볼 물리 — 실측 속도로 전진 + 벽 반사. 절대 멈추지 않음
            gx, gy = self._last_good[0], self._last_good[1]
            nx, self._vx = self._reflect(gx, self._vx, W - 1)
            ny, self._vy = self._reflect(gy, self._vy, H - 1)
            if self._mode == "residual":
                # 물리 예측 위치 주변에서 모션잔차 실측 → 발견 시 맹목 외삽 대신 보정
                found = self._residual.find(nx, ny)
                if found is not None:
                    rcx, rcy, _ = found
                    d = float(np.hypot(rcx - gx, rcy - gy))
                    if d > self._max_jump:   # 점프 게이트 — 배경 이펙트 오염 피해 한정
                        rcx = gx + (rcx - gx) * self._max_jump / d
                        rcy = gy + (rcy - gy) * self._max_jump / d
                    self._vx = self._vx * 0.6 + (rcx - gx) * 0.4
                    self._vy = self._vy * 0.6 + (rcy - gy) * 0.4
                    nx, ny = rcx, rcy
            self._last_good = (nx, ny, self._last_good[2])
            self._add_to_history(nx, ny)
            return (nx, ny, 0.0, False)

        pcx, pcy = self._predict_from_motion()
        pcx = max(0, min(W - 1, pcx))
        pcy = max(0, min(H - 1, pcy))

        if self._mode == "frosted":
            blob = find_frosted_blob(frame_bgr, pcx, pcy, self._ref_area)
            if blob is not None:
                bx, by, bw, bh = blob
                self._tracker = cv2.TrackerVit_create(self._params)
                self._tracker.init(frame_bgr, (int(bx), int(by), int(bw), int(bh)))
                ncx, ncy = bx + bw / 2, by + bh / 2
                self._last_good = (ncx, ncy, blob)
                self._add_to_history(ncx, ncy)
                self._reject_run = 0
                return (ncx, ncy, 0.0, True)

        # inertia 또는 frosted 미발견 → 예측 위치로 이동
        self._add_to_history(pcx, pcy)
        return (pcx, pcy, 0.0, False)
