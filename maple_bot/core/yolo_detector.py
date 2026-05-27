# YOLO11 추론 전담 모듈 — Vision Layer
from __future__ import annotations
import logging
import numpy as np

logger = logging.getLogger(__name__)


class YoloDetector:
    """
    YOLO11 (ultralytics) 추론만 수행.
    반환값은 raw detections — 방향 판단은 AttackDecision에서 처리.
    """

    CHARACTER_CLASS_NAME = "character"  # YOLO 모델의 캐릭터 클래스 이름

    def __init__(
        self,
        model_path: str,
        confidence: float = 0.5,
        iou: float = 0.45,
        max_det: int = 20,
    ) -> None:
        self._conf = confidence
        self._iou  = iou
        self._max_det = max_det
        self._model = None
        self._char_class_id: int | None = None
        self._load(model_path)

    def _load(self, model_path: str) -> None:
        """모델 로드. 실패 시 self._model = None (폴백 신호)."""
        try:
            from ultralytics import YOLO
            self._model = YOLO(model_path)
            # 클래스 이름에서 character 클래스 ID 탐색
            names = self._model.names  # {0: "monster", 1: "character", ...}
            for cid, name in names.items():
                if name.lower() == self.CHARACTER_CLASS_NAME:
                    self._char_class_id = cid
                    break
            logger.info("YoloDetector 로드 완료: %s (character class_id=%s)",
                        model_path, self._char_class_id)
        except Exception as e:
            self._model = None
            logger.warning("YoloDetector 로드 실패 — 템플릿 매칭 폴백: %s", e)

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

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
                "detections": [...]  # 전체 raw (Phase 2 확장용)
            }
        오류 시 빈 결과 반환 (크래시 없음).
        """
        _empty = {"monsters": [], "character": None, "detections": []}
        if self._model is None:
            return _empty

        try:
            crop = frame
            ox, oy = 0, 0
            if roi is not None:
                rx, ry, rw, rh = roi
                crop = frame[ry:ry + rh, rx:rx + rw]
                ox, oy = rx, ry

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
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
                    # roi 오프셋 보정
                    x1 += ox; y1 += oy; x2 += ox; y2 += oy
                    conf   = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    raw.append({"box": [x1, y1, x2, y2], "conf": conf, "cls": cls_id})

                    if cls_id == self._char_class_id:
                        # 가장 높은 신뢰도의 캐릭터 1개만 사용
                        if character is None or conf > character["conf"]:
                            character = {
                                "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                                "conf": conf,
                            }
                    else:
                        monsters.append({"box": [x1, y1, x2, y2], "conf": conf})

            return {"monsters": monsters, "character": character, "detections": raw}

        except Exception as e:
            logger.warning("YoloDetector.detect 오류: %s", e)
            return _empty
