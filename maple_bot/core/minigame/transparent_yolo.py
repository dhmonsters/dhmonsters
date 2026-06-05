# 투명도형 거탐 신경망 — planet_yolo_verify.py(Planet v2 완전 재현)와 동일한 구동 방식
# ① out0/out1/out2 3개 헤드 전부 사용  ② M1 앙상블(4-bin) 탐지  ③ imgsz=192  ④ sigmoid 미적용
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
BOX_CH  = 4 * REG_MAX   # 64  (ltrb DFL)
IMGSZ   = 192            # planet v2 기본값 (구현 기준)


def _softmax(x, axis):
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


class HyungYolo:
    """단일 ncnn YOLO 추론. planet_yolo_verify.HyungYolo 완전 재현.
    num_cls=1(M1 탐지) 또는 4(M2 분류)."""

    def __init__(self, param_path: str, bin_path: str, num_cls: int = 1,
                 use_gpu: bool = False, num_threads: int = 4, fp32_only: bool = True):
        if not _NCNN_OK:
            raise RuntimeError("ncnn 미설치 — pip install ncnn")
        self.num_cls = int(num_cls)
        self.out_ch  = BOX_CH + self.num_cls
        self.net = ncnn.Net()
        opt = self.net.opt
        opt.use_vulkan_compute = bool(use_gpu)
        opt.num_threads = num_threads
        if fp32_only:
            opt.use_fp16_packed      = False
            opt.use_fp16_storage     = False
            opt.use_fp16_arithmetic  = False
            opt.use_bf16_storage     = False
        if self.net.load_param(str(param_path)) != 0:
            raise RuntimeError(f"ncnn param load fail: {param_path}")
        if self.net.load_model(str(bin_path)) != 0:
            raise RuntimeError(f"ncnn bin load fail: {bin_path}")

    # ── 추론 ─────────────────────────────────────────────────────────
    def _letterbox(self, img, size: int):
        h, w = img.shape[:2]
        r = min(size / h, size / w)
        nh, nw = int(round(h * r)), int(round(w * r))
        canvas = np.full((size, size, 3), 114, np.uint8)
        canvas[:nh, :nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
        return canvas, r

    def _decode(self, arr: np.ndarray, stride: float, score_thr: float) -> np.ndarray:
        """DFL anchor-free 디코드. arr: (H, W, out_ch). planet_yolo_verify._decode 완전 재현."""
        H, W, _ = arr.shape
        a = arr.reshape(H * W, self.out_ch)
        cls    = a[:, BOX_CH:BOX_CH + self.num_cls]
        scores = cls.max(axis=1)           # sigmoid 미적용 — planet v2와 동일
        cls_id = cls.argmax(axis=1)
        keep   = scores > score_thr
        if not keep.any():
            return np.zeros((0, 6), np.float32)
        idx  = np.where(keep)[0]
        box  = a[keep, :BOX_CH].reshape(-1, 4, REG_MAX)
        d    = (_softmax(box, axis=2) * np.arange(REG_MAX, dtype=np.float32)).sum(axis=2)
        gy, gx = divmod(idx, W)
        cx_ = gx + 0.5;  cy_ = gy + 0.5
        x1 = (cx_ - d[:, 0]) * stride;  y1 = (cy_ - d[:, 1]) * stride
        x2 = (cx_ + d[:, 2]) * stride;  y2 = (cy_ + d[:, 3]) * stride
        return np.stack([x1, y1, x2, y2, scores[keep],
                         cls_id[keep].astype(np.float32)], axis=1)

    @staticmethod
    def _nms(boxes: np.ndarray, iou_thr: float) -> np.ndarray:
        if len(boxes) == 0:
            return boxes
        x1, y1, x2, y2, sc = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3], boxes[:, 4]
        areas = (x2 - x1).clip(0) * (y2 - y1).clip(0)
        order = sc.argsort()[::-1]
        keep  = []
        while order.size > 0:
            i = order[0]; keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            iou = ((xx2 - xx1).clip(0) * (yy2 - yy1).clip(0)) / (
                   areas[i] + areas[order[1:]] -
                   (xx2 - xx1).clip(0) * (yy2 - yy1).clip(0) + 1e-9)
            order = order[1:][iou <= iou_thr]
        return boxes[keep]

    def detect(self, image_bgr: np.ndarray, imgsz: int = IMGSZ,
               score_thr: float = 0.2, iou_thr: float = 0.45) -> np.ndarray:
        """out0/out1/out2 3개 헤드 → NMS. planet_yolo_verify.detect 완전 재현."""
        lb, r = self._letterbox(image_bgr, imgsz)
        mat = ncnn.Mat.from_pixels(np.ascontiguousarray(lb),
                                   ncnn.Mat.PixelType.PIXEL_BGR2RGB, imgsz, imgsz)
        mat.substract_mean_normalize([0., 0., 0.], [1/255., 1/255., 1/255.])
        ex = self.net.create_extractor()
        ex.input("in0", mat)
        all_boxes = []
        for name in ("out0", "out1", "out2"):
            _, out = ex.extract(name)
            arr = np.array(out)
            # ncnn 버전별 레이아웃 차이 대응: (C,H,W) → (H,W,C)
            if arr.ndim == 3 and arr.shape[-1] != self.out_ch and arr.shape[0] == self.out_ch:
                arr = arr.transpose(1, 2, 0)
            stride = imgsz / arr.shape[0]
            all_boxes.append(self._decode(arr, stride, score_thr))
        boxes = (np.concatenate(all_boxes, 0) if all_boxes
                 else np.zeros((0, 6), np.float32))
        boxes = self._nms(boxes, iou_thr)
        if len(boxes):
            boxes[:, :4] /= r
        return boxes

    def detect_center(self, image_bgr: np.ndarray, score_thr: float = 0.2):
        """최고 점수 도형의 중심좌표 (cx, cy). 없으면 None."""
        boxes = self.detect(image_bgr, score_thr=score_thr)
        if len(boxes) == 0:
            return None
        b = boxes[boxes[:, 4].argmax()]
        return (int((b[0] + b[2]) / 2), int((b[1] + b[3]) / 2))

    def classify_crop(self, image_bgr: np.ndarray, imgsz: int = IMGSZ,
                      score_thr: float = 0.0):
        """M2용: 전체 이미지에서 최고 점수 클래스 ID 반환. 없으면 None."""
        boxes = self.detect(image_bgr, imgsz, score_thr)
        if len(boxes) == 0:
            return None
        return int(boxes[boxes[:, 4].argmax(), 5])


class M1Ensemble:
    """M1 4-bin 앙상블 (hyung_m1.param + a~d.bin). planet_yolo_verify.M1Ensemble 완전 재현.
    탐지 전용(1클래스) — 저가시성 도형 탐지 보강."""

    def __init__(self, param_path: str, bin_paths: list[str],
                 use_gpu: bool = False, num_threads: int = 4):
        self.nets = [HyungYolo(param_path, bp, num_cls=1,
                               use_gpu=use_gpu, num_threads=num_threads)
                     for bp in bin_paths]

    def detect(self, image_bgr: np.ndarray, imgsz: int = IMGSZ,
               score_thr: float = 0.2, iou_thr: float = 0.45) -> np.ndarray:
        """4개 모델 탐지 결과를 병합 후 NMS."""
        all_boxes = [n.detect(image_bgr, imgsz, score_thr, iou_thr) for n in self.nets]
        all_boxes = [b for b in all_boxes if len(b) > 0]
        if not all_boxes:
            return np.zeros((0, 6), np.float32)
        return HyungYolo._nms(np.concatenate(all_boxes, 0), iou_thr)

    def detect_center(self, image_bgr: np.ndarray, score_thr: float = 0.2):
        """최고 점수 도형의 중심좌표 (cx, cy). 없으면 None. SelfTransparentEngine 인터페이스."""
        boxes = self.detect(image_bgr, score_thr=score_thr)
        if len(boxes) == 0:
            return None
        b = boxes[boxes[:, 4].argmax()]
        return (int((b[0] + b[2]) / 2), int((b[1] + b[3]) / 2))


def load_default(models_dir: str | Path, use_gpu: bool = False) -> M1Ensemble:
    """models/transparent/ 의 M1 앙상블(4-bin) 로드. planet v2와 동일하게 M1으로 탐지."""
    d = Path(models_dir)
    return M1Ensemble(
        param_path=str(d / "hyung_m1.param"),
        bin_paths=[str(d / f"hyung_m1_{s}.bin") for s in "abcd"],
        use_gpu=use_gpu,
    )


def load_m2(models_dir: str | Path, use_gpu: bool = False) -> HyungYolo:
    """M2(4클래스 분류) 로드. 도형 종류 확인이 필요할 때만 사용."""
    d = Path(models_dir)
    return HyungYolo(str(d / "hyung_m2.param"), str(d / "hyung_m2.bin"),
                     num_cls=4, use_gpu=use_gpu)
