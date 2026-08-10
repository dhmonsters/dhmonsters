# 흰색 도형 모양 분류 — YOLO-cls ncnn 4클래스(원/세모/네모/별). 흰색단계에 모양 판별→전문 검출기 선택용
from __future__ import annotations

import cv2
import numpy as np

try:
    import ncnn
    _NCNN_OK = True
except Exception:
    _NCNN_OK = False

# dataset_cls 알파벳 순(학습 클래스 순서) = ncnn 출력 순서
NAMES = ["circle", "square", "star", "triangle"]


class ShapeClassifier:
    """흰색 도형 crop → 4모양 분류. 커서 inpaint 내장(핑크 커서가 도형을 가려서)."""

    def __init__(self, param_path: str, bin_path: str):
        self._ok = False
        if not _NCNN_OK:
            return
        try:
            self.net = ncnn.Net()
            if (self.net.load_param(param_path) == 0
                    and self.net.load_model(bin_path) == 0):
                self._ok = True
        except Exception:
            self._ok = False

    @property
    def enabled(self) -> bool:
        return self._ok

    @staticmethod
    def _inpaint_cursor(img: np.ndarray) -> np.ndarray:
        """핑크 커서(HSV 140~175)를 inpaint — 흰색 도형이 커서에 가려 모양이 안 보임."""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        m = cv2.inRange(hsv, np.array([140, 60, 60]), np.array([175, 255, 255]))
        m = cv2.dilate(m, np.ones((3, 3), np.uint8), iterations=2)
        return cv2.inpaint(img, m, 3, cv2.INPAINT_TELEA)

    def classify(self, bgr: np.ndarray):
        """흰색 도형 crop(BGR) → (모양명, score). 비활성/빈입력이면 (None, 0)."""
        if not self._ok or bgr is None or bgr.size == 0:
            return None, 0.0
        img = self._inpaint_cursor(bgr)
        mat = ncnn.Mat.from_pixels_resize(
            np.ascontiguousarray(img), ncnn.Mat.PixelType.PIXEL_BGR2RGB,
            img.shape[1], img.shape[0], 64, 64)
        mat.substract_mean_normalize([0., 0., 0.], [1 / 255.] * 3)
        ex = self.net.create_extractor()
        ex.input("in0", mat)
        _, out = ex.extract("out0")
        a = np.array(out)
        if a.size < len(NAMES):
            return None, 0.0
        return NAMES[int(a.argmax())], float(a.max())
