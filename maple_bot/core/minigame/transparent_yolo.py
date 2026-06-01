# 투명도형 거탐 신경망 — Planet v2 detector.py(ncnn HyungYolo) 자체 재현. secure_loader 우회
# dis 확정 명세: YOLOv8 anchor-free DFL 헤드, REG_MAX=16, IMGSZ=320, 입력 "in0" / 출력 "out2"
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

try:
    import ncnn
    _NCNN_OK = True
except Exception:
    _NCNN_OK = False

REG_MAX = 16
IMGSZ = 320
_PAD = 114          # letterbox 패딩값 (YOLO 표준 회색)
_CENTER_OFF = 0.5   # 그리드 중심 오프셋


def _softmax(x, axis=-1):
    e = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e / np.sum(e, axis=axis, keepdims=True)


class HyungYolo:
    """ncnn 기반 투명도형 감지기 (단일 모델). detector.HyungYolo 재현."""

    def __init__(self, param_path: str, bin_path: str, num_cls: int = 1,
                 use_gpu: bool = False, num_threads: int = 4, fp32_only: bool = True):
        if not _NCNN_OK:
            raise RuntimeError("ncnn 미설치 — pip install ncnn")
        self.num_cls = int(num_cls)
        self.out_ch = 4 * REG_MAX + self.num_cls   # DFL(4*16) + 클래스
        self.net = ncnn.Net()
        opt = self.net.opt
        opt.use_vulkan_compute = bool(use_gpu)
        opt.num_threads = num_threads
        if fp32_only:
            opt.use_fp16_packed = False
            opt.use_fp16_storage = False
            opt.use_fp16_arithmetic = False
            opt.use_bf16_storage = False
        if self.net.load_param(str(param_path)) != 0:
            raise RuntimeError(f"ncnn param load fail: {param_path}")
        if self.net.load_model(str(bin_path)) != 0:
            raise RuntimeError(f"ncnn bin load fail: {bin_path}")

    def _letterbox(self, img, size=IMGSZ):
        h, w = img.shape[:2]
        r = min(size / h, size / w)
        nh, nw = int(round(h * r)), int(round(w * r))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        out = np.full((size, size, 3), _PAD, dtype=np.uint8)
        out[:nh, :nw] = resized
        return out, r

    def detect(self, image_bgr, imgsz=IMGSZ, score_thr=0.25, iou_thr=0.45):
        """투명도형 박스 목록 반환 — np.array([[x1,y1,x2,y2,score,cls], ...])."""
        lb, r = self._letterbox(image_bgr, imgsz)
        lb = np.ascontiguousarray(lb)
        mat = ncnn.Mat.from_pixels(lb, ncnn.Mat.PixelType.PIXEL_BGR2RGB, imgsz, imgsz)
        mat.substract_mean_normalize([], [1 / 255.0, 1 / 255.0, 1 / 255.0])

        ex = self.net.create_extractor()
        ex.input("in0", mat)
        ret, out = ex.extract("out2")
        arr = np.array(out)   # ncnn → (H, W, out_ch) = (side, side, 68)
        boxes = self._decode(arr, score_thr)
        if len(boxes) == 0:
            return np.zeros((0, 6), np.float32)
        boxes = self._nms(boxes, iou_thr)
        # letterbox 역변환 + 원본 경계로 클램프
        boxes[:, :4] /= r
        h, w = image_bgr.shape[:2]
        boxes[:, [0, 2]] = np.clip(boxes[:, [0, 2]], 0, w)
        boxes[:, [1, 3]] = np.clip(boxes[:, [1, 3]], 0, h)
        return boxes

    def detect_center(self, image_bgr, score_thr=0.25):
        """최고 점수 도형의 중심좌표 (cx, cy) 반환. 없으면 None."""
        boxes = self.detect(image_bgr, score_thr=score_thr)
        if len(boxes) == 0:
            return None
        b = boxes[boxes[:, 4].argmax()]
        return (int((b[0] + b[2]) / 2), int((b[1] + b[3]) / 2))

    def _decode(self, arr, score_thr):
        """DFL anchor-free 디코드. arr: (side, side, out_ch) 단일 헤드(stride=IMGSZ/side)."""
        side = arr.shape[0]
        arr = arr.reshape(-1, self.out_ch)
        n = arr.shape[0]
        if side * side != n:
            return np.zeros((0, 6), np.float32)
        # 분류 점수는 sigmoid 적용(모델 출력은 raw logit)
        cls_logits = arr[:, 4 * REG_MAX:]
        cls_scores = 1.0 / (1.0 + np.exp(-cls_logits))
        scores = cls_scores.max(axis=1)
        cls = cls_scores.argmax(axis=1)
        keep = scores >= score_thr
        if not np.any(keep):
            return np.zeros((0, 6), np.float32)

        dfl = arr[:, :4 * REG_MAX].reshape(-1, 4, REG_MAX)
        prob = _softmax(dfl, axis=-1)
        ltrb = (prob * np.arange(REG_MAX)).sum(axis=-1)   # (N,4) 거리

        gy, gx = np.mgrid[0:side, 0:side]
        cx = (gx.reshape(-1) + _CENTER_OFF)
        cy = (gy.reshape(-1) + _CENTER_OFF)
        stride = IMGSZ / side
        x1 = (cx - ltrb[:, 0]) * stride
        y1 = (cy - ltrb[:, 1]) * stride
        x2 = (cx + ltrb[:, 2]) * stride
        y2 = (cy + ltrb[:, 3]) * stride
        out = np.stack([x1, y1, x2, y2, scores, cls.astype(np.float32)], axis=1)
        return out[keep]

    @staticmethod
    def _nms(boxes, iou_thr):
        if len(boxes) == 0:
            return boxes
        x1, y1, x2, y2, sc = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3], boxes[:, 4]
        areas = (x2 - x1) * (y2 - y1)
        order = sc.argsort()[::-1]
        keep = []
        while len(order) > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = np.clip(xx2 - xx1, 0, None)
            h = np.clip(yy2 - yy1, 0, None)
            inter = w * h
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-09)
            order = order[1:][iou < iou_thr]
        return boxes[keep]


class M1Ensemble:
    """m1 4-bin 앙상블 (hyung_m1.param + a~d.bin). detector.M1Ensemble 재현."""

    def __init__(self, param_path: str, bin_paths: list[str],
                 use_gpu: bool = False, num_threads: int = 4):
        self.nets = [HyungYolo(param_path, b, num_cls=1, use_gpu=use_gpu,
                               num_threads=num_threads) for b in bin_paths]

    def detect(self, image_bgr, score_thr=0.25, iou_thr=0.45):
        allb = [n.detect(image_bgr, score_thr=score_thr, iou_thr=iou_thr) for n in self.nets]
        allb = [b for b in allb if len(b) > 0]
        if not allb:
            return np.zeros((0, 6), np.float32)
        merged = np.concatenate(allb, axis=0)
        return HyungYolo._nms(merged, iou_thr)


def load_default(models_dir: str | Path, use_gpu: bool = False) -> HyungYolo:
    """models/transparent/ 의 m2(4클래스) 기본 로드."""
    d = Path(models_dir)
    return HyungYolo(str(d / "hyung_m2.param"), str(d / "hyung_m2.bin"),
                     num_cls=4, use_gpu=use_gpu)
