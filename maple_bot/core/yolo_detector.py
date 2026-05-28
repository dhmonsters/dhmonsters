# YOLO11 추론 전담 모듈 — Vision Layer (ultralytics 우선, ONNX 폴백)
from __future__ import annotations
import os
import logging
import numpy as np

logger = logging.getLogger(__name__)


class YoloDetector:
    """
    YOLO11 추론만 수행.
    - 우선: ultralytics (torch 필요)
    - 폴백: onnxruntime (.onnx 파일 자동 탐색)

    반환값은 raw detections — 방향 판단은 AttackDecision에서 처리.
    """

    CHARACTER_CLASS_NAME = "character"

    def __init__(
        self,
        model_path: str,
        confidence: float = 0.5,
        iou: float = 0.45,
        max_det: int = 20,
    ) -> None:
        self._conf     = confidence
        self._iou      = iou
        self._max_det  = max_det
        self._model    = None          # ultralytics YOLO
        self._onnx_session  = None     # onnxruntime.InferenceSession
        self._onnx_nc       = 1        # 클래스 수 (ONNX 출력에서 자동 추론)
        self._onnx_names: dict[int, str] = {}
        self._char_class_id: int | None  = None
        self._load(model_path)

    # ── 로드 ─────────────────────────────────────────────────────────
    def _load(self, model_path: str) -> None:
        # 1순위: ultralytics (torch 있을 때)
        try:
            from ultralytics import YOLO
            self._model = YOLO(model_path)
            names = self._model.names
            for cid, name in names.items():
                if name.lower() == self.CHARACTER_CLASS_NAME:
                    self._char_class_id = cid
                    break
            logger.info("YoloDetector 로드 완료 (ultralytics): %s", model_path)
            return
        except Exception as e:
            logger.info("ultralytics 로드 실패 (%s) — ONNX 폴백 시도", e)

        # 2순위: onnxruntime (.onnx 파일 자동 탐색)
        onnx_path = self._find_onnx(model_path)
        if onnx_path:
            try:
                import onnxruntime as ort
                self._onnx_session = ort.InferenceSession(
                    onnx_path,
                    providers=["CPUExecutionProvider"],
                )
                # 출력 shape에서 nc 추론: (1, 4+nc, 8400)
                out_shape = self._onnx_session.get_outputs()[0].shape
                if len(out_shape) >= 2:
                    self._onnx_nc = out_shape[1] - 4  # 4=bbox
                # metadata에서 클래스 이름 추출 (ultralytics export 시 포함됨)
                meta = self._onnx_session.get_modelmeta().custom_metadata_map
                import json
                names_raw = meta.get("names", "")
                if names_raw:
                    try:
                        parsed = json.loads(names_raw)
                        if isinstance(parsed, dict):
                            self._onnx_names = {int(k): v for k, v in parsed.items()}
                        elif isinstance(parsed, list):
                            self._onnx_names = {i: v for i, v in enumerate(parsed)}
                    except Exception:
                        pass
                for cid, name in self._onnx_names.items():
                    if name.lower() == self.CHARACTER_CLASS_NAME:
                        self._char_class_id = cid
                        break
                logger.info("YoloDetector 로드 완료 (ONNX): %s  nc=%d", onnx_path, self._onnx_nc)
                return
            except Exception as e2:
                self._onnx_session = None
                logger.warning("ONNX 로드 실패: %s", e2)

        logger.warning("YoloDetector 로드 실패 — 템플릿 매칭 폴백")

    @staticmethod
    def _find_onnx(model_path: str) -> str | None:
        """같은 폴더에서 .onnx 파일을 찾는다."""
        # 직접 .onnx 경로인 경우
        if model_path.endswith(".onnx") and os.path.exists(model_path):
            return model_path
        # .pt → .onnx 변환 경로
        onnx_path = os.path.splitext(model_path)[0] + ".onnx"
        if os.path.exists(onnx_path):
            return onnx_path
        return None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None or self._onnx_session is not None

    # ── 추론 ─────────────────────────────────────────────────────────
    def detect(
        self,
        frame: np.ndarray,
        roi: tuple[int, int, int, int] | None = None,
    ) -> dict:
        """
        frame: BGR numpy 배열 (전체 스크린샷)
        roi: (x, y, w, h) — 지정 시 해당 영역만 크롭 후 추론
        반환:
            {
                "monsters":   [{"box": [x1,y1,x2,y2], "conf": float}, ...],
                "character":  {"center": (cx, cy), "conf": float} | None,
                "detections": [{"box":..., "conf":..., "cls":...}, ...]
            }
        """
        _empty = {"monsters": [], "character": None, "detections": []}
        if not self.is_loaded:
            return _empty

        try:
            crop = frame
            ox, oy = 0, 0
            if roi is not None:
                rx, ry, rw, rh = roi
                crop = frame[ry:ry + rh, rx:rx + rw]
                ox, oy = rx, ry

            if self._model is not None:
                return self._detect_ultralytics(crop, ox, oy)
            else:
                return self._detect_onnx(crop, ox, oy)

        except Exception as e:
            logger.warning("YoloDetector.detect 오류: %s", e)
            return _empty

    # ── ultralytics 경로 ──────────────────────────────────────────────
    def _detect_ultralytics(self, crop, ox, oy) -> dict:
        results = self._model.predict(
            crop,
            conf=self._conf,
            iou=self._iou,
            max_det=self._max_det,
            verbose=False,
        )
        monsters: list[dict] = []
        character: dict | None = None
        raw: list[dict] = []

        for r in results:
            for box in r.boxes:
                x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                x1 += ox; y1 += oy; x2 += ox; y2 += oy
                conf   = float(box.conf[0])
                cls_id = int(box.cls[0])
                raw.append({"box": [x1, y1, x2, y2], "conf": conf, "cls": cls_id})

                if cls_id == self._char_class_id:
                    if character is None or conf > character["conf"]:
                        character = {
                            "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                            "conf": conf,
                        }
                else:
                    monsters.append({"box": [x1, y1, x2, y2], "conf": conf})

        return {"monsters": monsters, "character": character, "detections": raw}

    # ── ONNX 경로 ────────────────────────────────────────────────────
    _INPUT_SIZE = 640

    def _detect_onnx(self, crop, ox, oy) -> dict:
        ih, iw = crop.shape[:2]
        blob, scale, (pad_x, pad_y) = self._preprocess_onnx(crop)

        input_name = self._onnx_session.get_inputs()[0].name
        raw_out = self._onnx_session.run(None, {input_name: blob})[0]
        # raw_out shape: (1, 4+nc, 8400)
        preds = raw_out[0].T  # → (8400, 4+nc)

        monsters: list[dict] = []
        character: dict | None = None
        raw: list[dict] = []

        nc = self._onnx_nc
        # 클래스별 최대 점수 + argmax
        if nc == 1:
            scores = preds[:, 4]
            class_ids = np.zeros(len(preds), dtype=int)
        else:
            class_scores = preds[:, 4:]
            class_ids = class_scores.argmax(axis=1)
            scores = class_scores.max(axis=1)

        mask = scores >= self._conf
        if not mask.any():
            return {"monsters": [], "character": None, "detections": []}

        preds_f   = preds[mask]
        scores_f  = scores[mask]
        cls_ids_f = class_ids[mask]

        # cx,cy,w,h → x1,y1,x2,y2 (letterbox 좌표계)
        cx, cy = preds_f[:, 0], preds_f[:, 1]
        bw, bh = preds_f[:, 2], preds_f[:, 3]
        x1s = ((cx - bw / 2 - pad_x) / scale).astype(int)
        y1s = ((cy - bh / 2 - pad_y) / scale).astype(int)
        x2s = ((cx + bw / 2 - pad_x) / scale).astype(int)
        y2s = ((cy + bh / 2 - pad_y) / scale).astype(int)

        # NMS (간단 버전: 클래스별 IoU 필터)
        boxes  = np.stack([x1s, y1s, x2s, y2s], axis=1)
        keep   = self._nms(boxes, scores_f, self._iou)

        for idx in keep[:self._max_det]:
            x1, y1, x2, y2 = (
                int(np.clip(boxes[idx, 0], 0, iw)) + ox,
                int(np.clip(boxes[idx, 1], 0, ih)) + oy,
                int(np.clip(boxes[idx, 2], 0, iw)) + ox,
                int(np.clip(boxes[idx, 3], 0, ih)) + oy,
            )
            conf   = float(scores_f[idx])
            cls_id = int(cls_ids_f[idx])
            raw.append({"box": [x1, y1, x2, y2], "conf": conf, "cls": cls_id})

            if cls_id == self._char_class_id:
                if character is None or conf > character["conf"]:
                    character = {
                        "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                        "conf": conf,
                    }
            else:
                monsters.append({"box": [x1, y1, x2, y2], "conf": conf})

        return {"monsters": monsters, "character": character, "detections": raw}

    def _preprocess_onnx(self, img_bgr: np.ndarray):
        """BGR → letterbox float32 (1,3,640,640), scale, (pad_x, pad_y)."""
        import cv2
        s = self._INPUT_SIZE
        h, w = img_bgr.shape[:2]
        scale = min(s / h, s / w)
        nh, nw = int(round(h * scale)), int(round(w * scale))
        img = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
        pad_x = (s - nw) // 2
        pad_y = (s - nh) // 2
        canvas = np.full((s, s, 3), 114, dtype=np.uint8)
        canvas[pad_y:pad_y + nh, pad_x:pad_x + nw] = img
        canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = canvas.transpose(2, 0, 1)[np.newaxis]  # (1,3,s,s)
        return blob, scale, (pad_x, pad_y)

    @staticmethod
    def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float) -> list[int]:
        """간단 NMS. boxes=(N,4) x1y1x2y2, scores=(N,). 내림차순 인덱스 반환."""
        if len(boxes) == 0:
            return []
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
        order = scores.argsort()[::-1]
        keep  = []
        while order.size > 0:
            i = order[0]
            keep.append(int(i))
            if order.size == 1:
                break
            rest  = order[1:]
            xx1   = np.maximum(x1[i], x1[rest])
            yy1   = np.maximum(y1[i], y1[rest])
            xx2   = np.minimum(x2[i], x2[rest])
            yy2   = np.minimum(y2[i], y2[rest])
            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            iou   = inter / (areas[i] + areas[rest] - inter + 1e-9)
            order = rest[iou <= iou_thresh]
        return keep
