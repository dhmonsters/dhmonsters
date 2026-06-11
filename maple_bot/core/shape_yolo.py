# 투명 도형 추적용 ncnn YOLOv8n 1클래스 추론기 — 모델 없으면 자동 비활성(휴리스틱 폴백)
"""
설계 근거: planet_yolo_verify.py에서 검증한 HyungYolo 디코드를 1클래스 전용으로 단순화.
  - models/shape_yolo.param/.bin 이 있으면 활성, 없으면 _enabled=False (절대 예외 안 던짐).
  - detect(board_bgr) -> (cx, cy, score) | None  (board 상대좌표).
  - 출력은 board ROI 픽셀 좌표. EMA/마우스 제어는 호출측(transparent_shape_game) 담당.
"""
from __future__ import annotations

import os
import logging
from typing import Optional

import numpy as np
import cv2

logger = logging.getLogger(__name__)

_MODEL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
PARAM_PATH = os.path.join(_MODEL_DIR, "shape_yolo.param")
BIN_PATH   = os.path.join(_MODEL_DIR, "shape_yolo.bin")

IMGSZ      = 192
SCORE_THR  = 0.2
IOU_THR    = 0.45
NUM_CLS    = 2
# 클래스 인덱스(data.yaml names 순서): 0=mouse, 1=transparent-game.
# 봇은 도형 위치만 필요하므로 도형(1)만 사용하고 커서(0)는 버린다.
SHAPE_CLASS_IDX = 1
# ultralytics ncnn export는 Detect 후처리를 그래프에 구워 단일 "out0"(4+nc, anchors) 출력.
# 2클래스 → out0 형태 = (6, A): 행0~3=cx,cy,w,h(레터박스 px), 행4=mouse score, 행5=shape score.
OUT_ROWS   = 4 + NUM_CLS  # 6


class ShapeYolo:
    """단일 ncnn YOLOv8n 1클래스 추론기. 도형 박스 중심을 반환."""

    def __init__(self, param_path: str = PARAM_PATH, bin_path: str = BIN_PATH,
                 num_threads: int = 4):
        self._enabled = False
        self.net = None
        if not (os.path.exists(param_path) and os.path.exists(bin_path)):
            logger.info("ShapeYolo: 모델 미존재 — 비활성(휴리스틱 폴백). %s", param_path)
            return
        try:
            import ncnn
            net = ncnn.Net()
            net.opt.use_vulkan_compute = False
            net.opt.num_threads = num_threads
            net.opt.use_fp16_packed = False
            net.opt.use_fp16_storage = False
            net.opt.use_fp16_arithmetic = False
            net.opt.use_bf16_storage = False
            if net.load_param(str(param_path)) != 0:
                raise RuntimeError("param load fail")
            if net.load_model(str(bin_path)) != 0:
                raise RuntimeError("bin load fail")
            self.net = net
            self._enabled = True
            logger.info("ShapeYolo: 모델 로드 완료 — YOLO 감지 활성")
        except Exception as exc:
            logger.warning("ShapeYolo: 로드 실패 — 비활성. %s", exc)
            self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    # ── 전처리 ────────────────────────────────────────────────────────
    @staticmethod
    def _letterbox(img, size):
        h, w = img.shape[:2]
        r = min(size / h, size / w)
        nh, nw = int(round(h * r)), int(round(w * r))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((size, size, 3), 114, np.uint8)
        canvas[:nh, :nw] = resized
        return canvas, r

    # ── 디코드 (이미 디코딩된 단일 out0 파싱) ─────────────────────────
    @staticmethod
    def _decode(out0, score_thr):
        """out0 (6, A) → [x1,y1,x2,y2,score] Nx5 (레터박스 px). 도형(class 1) score만 사용.
        커서(class 0)는 무시 — 봇은 도형 위치만 필요. DFL은 그래프에 구워져 불필요."""
        a = np.asarray(out0, dtype=np.float32)
        if a.ndim != 2 or a.shape[0] != OUT_ROWS:
            return np.zeros((0, 5), np.float32)
        cx, cy, w, h = a[0], a[1], a[2], a[3]
        score = a[4 + SHAPE_CLASS_IDX]   # 도형 클래스 score (행5)
        keep = score > score_thr
        if not keep.any():
            return np.zeros((0, 5), np.float32)
        cx, cy, w, h, score = cx[keep], cy[keep], w[keep], h[keep], score[keep]
        x1 = cx - w / 2
        y1 = cy - h / 2
        x2 = cx + w / 2
        y2 = cy + h / 2
        return np.stack([x1, y1, x2, y2, score], axis=1)

    @staticmethod
    def _nms(boxes, iou_thr):
        if len(boxes) == 0:
            return boxes
        x1, y1, x2, y2, sc = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3], boxes[:, 4]
        areas = (x2 - x1).clip(0) * (y2 - y1).clip(0)
        order = sc.argsort()[::-1]
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = (xx2 - xx1).clip(0)
            h = (yy2 - yy1).clip(0)
            inter = w * h
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
            order = order[1:][iou <= iou_thr]
        return boxes[keep]

    # ── 추론 ──────────────────────────────────────────────────────────
    def _infer(self, board_bgr: np.ndarray, score_thr: float):
        """공통 추론 — NMS 후 boxes (Nx5: x1,y1,x2,y2,score, board px). 실패 시 빈 배열."""
        import ncnn
        lb, r = self._letterbox(board_bgr, IMGSZ)
        lb = np.ascontiguousarray(lb)
        mat_in = ncnn.Mat.from_pixels(lb, ncnn.Mat.PixelType.PIXEL_BGR2RGB, IMGSZ, IMGSZ)
        mat_in.substract_mean_normalize([0., 0., 0.], [1 / 255., 1 / 255., 1 / 255.])
        ex = self.net.create_extractor()
        ex.input("in0", mat_in)
        ret, out = ex.extract("out0")
        boxes = self._decode(np.array(out), score_thr)
        boxes = self._nms(boxes, IOU_THR)
        if len(boxes):
            boxes[:, :4] /= r
        return boxes

    def detect(self, board_bgr: np.ndarray,
               score_thr: float = SCORE_THR) -> Optional[tuple]:
        """board 상대 도형 중심 (cx, cy, score). 미검출/비활성 시 None."""
        if not self._enabled or board_bgr is None or board_bgr.size == 0:
            return None
        try:
            boxes = self._infer(board_bgr, score_thr)
            if len(boxes) == 0:
                return None
            best = boxes[boxes[:, 4].argmax()]
            cx = int((best[0] + best[2]) / 2)
            cy = int((best[1] + best[3]) / 2)
            return (cx, cy, float(best[4]))
        except Exception as exc:
            logger.debug("ShapeYolo.detect 실패: %s", exc)
            return None

    def detect_all(self, board_bgr: np.ndarray,
                   score_thr: float = SCORE_THR) -> list:
        """모든 후보 [(cx, cy, score, w, h), ...] — 호출측이 움직임 게이트로 선택.
        w/h는 미리보기 박스 표시용(앞 3개 인덱스만 쓰는 기존 호출과 호환). 비활성 시 []."""
        if not self._enabled or board_bgr is None or board_bgr.size == 0:
            return []
        try:
            boxes = self._infer(board_bgr, score_thr)
            return [(int((b[0] + b[2]) / 2), int((b[1] + b[3]) / 2), float(b[4]),
                     int(b[2] - b[0]), int(b[3] - b[1]))
                    for b in boxes]
        except Exception as exc:
            logger.debug("ShapeYolo.detect_all 실패: %s", exc)
            return []
