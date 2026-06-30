# planet_solver_noauth의 M1 검출기를 퍼즐 라이브 솔버에서 재사용하는 어댑터다.
from __future__ import annotations

from typing import Any

import numpy as np


SHAPE_WEAK_SCORE = 0.10
DEFAULT_M1_WEAK_SCORES = (0.12, 0.08, 0.05)
DEFAULT_MAX_ROWS = 24


class PlanetNoAuthDetector:
    def __init__(
        self,
        *,
        use_gpu: bool = False,
        imgsz: int = 192,
        score: float = 0.2,
        shape_detector: Any | None = None,
        shape_score: float = SHAPE_WEAK_SCORE,
        weak_scores: tuple[float, ...] = DEFAULT_M1_WEAK_SCORES,
        max_rows: int = DEFAULT_MAX_ROWS,
        cursor_inpaint: bool = True,
    ) -> None:
        self.use_gpu = bool(use_gpu)
        self.imgsz = int(imgsz)
        self.score = float(score)
        self.shape_score = float(shape_score)
        self.weak_scores = tuple(float(value) for value in weak_scores)
        self.max_rows = int(max_rows)
        self.cursor_inpaint = bool(cursor_inpaint)
        self._m1: Any | None = None
        self._shape_detector: Any | None = shape_detector
        self._shape_detector_injected = shape_detector is not None
        self._shape_load_attempted = shape_detector is not None
        self._shape_runtime_retry_attempted = False
        self._load_attempted = False
        self._load_failed = False
        self.load_source = ""
        self.last_error = ""
        self.m1_score_used: float | None = None
        self.m1_attempts: list[float] = []

    @property
    def enabled(self) -> bool:
        return not self._load_failed

    def detect_all(self, board_bgr: Any) -> list[tuple[int, int, float, int, int]]:
        self.m1_score_used = None
        self.m1_attempts = []
        if board_bgr is None or not hasattr(board_bgr, "size") or board_bgr.size == 0:
            return []
        detect_frame = _inpaint_cursor_if_present(board_bgr) if self.cursor_inpaint else board_bgr
        shape_rows = self._detect_shape_rows(detect_frame)
        if shape_rows:
            self.load_source = "shape_yolo"
            self.last_error = ""
            return shape_rows
        m1 = self._load_m1()
        retry_shape_rows = self._retry_shape_rows_after_runtime_prepare(detect_frame)
        if retry_shape_rows:
            self.load_source = "shape_yolo"
            self.last_error = ""
            return retry_shape_rows
        if m1 is None:
            return []
        return self._detect_m1_rows(m1, detect_frame)

    def _detect_shape_rows(self, board_bgr: Any) -> list[tuple[int, int, float, int, int]]:
        detector = self._load_shape_detector()
        if detector is None or not bool(getattr(detector, "enabled", True)):
            return []
        try:
            rows = detector.detect_all(board_bgr, score_thr=self.shape_score)
        except Exception as exc:
            self.last_error = f"shape_yolo: {exc.__class__.__name__}: {exc}"
            return []
        return _shape_rows_to_rows(rows)

    def _retry_shape_rows_after_runtime_prepare(self, board_bgr: Any) -> list[tuple[int, int, float, int, int]]:
        if self._shape_detector_injected or self._shape_runtime_retry_attempted:
            return []
        self._shape_runtime_retry_attempted = True
        detector = self._load_shape_detector(force_reload=True)
        if detector is None or not bool(getattr(detector, "enabled", True)):
            return []
        try:
            rows = detector.detect_all(board_bgr, score_thr=self.shape_score)
        except Exception as exc:
            self.last_error = f"shape_yolo: {exc.__class__.__name__}: {exc}"
            return []
        return _shape_rows_to_rows(rows)

    def _load_shape_detector(self, *, force_reload: bool = False) -> Any | None:
        if self._shape_load_attempted and not force_reload:
            return self._shape_detector
        self._shape_load_attempted = True
        try:
            from core.shape_yolo import ShapeYolo

            self._shape_detector = ShapeYolo()
        except Exception as exc:
            self._shape_detector = None
            self.last_error = f"shape_yolo: {exc.__class__.__name__}: {exc}"
        return self._shape_detector

    def _load_m1(self) -> Any | None:
        if self._load_attempted:
            return self._m1
        self._load_attempted = True
        errors: list[str] = []
        for source, loader in (
            ("planet_live_solver", _load_from_planet_live_solver),
            ("planet_yolo_verify", _load_from_planet_yolo_verify),
        ):
            try:
                self._m1, _m2 = loader(use_gpu=self.use_gpu)
                self.load_source = source
                self.last_error = ""
                return self._m1
            except Exception as exc:
                errors.append(f"{source}: {exc.__class__.__name__}: {exc}")
        self._load_failed = True
        self._m1 = None
        self.last_error = " | ".join(errors)
        return self._m1

    def _detect_m1_rows(self, m1: Any, detect_frame: Any) -> list[tuple[int, int, float, int, int]]:
        for score in _unique_scores((self.score, *self.weak_scores)):
            self.m1_attempts.append(score)
            try:
                boxes = m1.detect(detect_frame, self.imgsz, score)
            except Exception as exc:
                self.last_error = f"{exc.__class__.__name__}: {exc}"
                return []
            rows = _limit_rows(_m1_boxes_to_rows(boxes), max_rows=self.max_rows)
            if rows:
                self.m1_score_used = score
                return rows
        self.m1_score_used = None
        return []


def _load_from_planet_live_solver(*, use_gpu: bool) -> tuple[Any, Any]:
    from planet_live_solver import load_models

    return load_models(use_gpu=use_gpu)


def _load_from_planet_yolo_verify(*, use_gpu: bool) -> tuple[Any, Any]:
    from planet_yolo_verify import load_models

    return load_models(use_gpu=use_gpu)


def _shape_rows_to_rows(rows: Any) -> list[tuple[int, int, float, int, int]]:
    out: list[tuple[int, int, float, int, int]] = []
    for row in rows or []:
        if len(row) < 5:
            continue
        cx, cy, score, width, height = row[:5]
        out.append((int(cx), int(cy), float(score), int(width), int(height)))
    return out


def _m1_boxes_to_rows(boxes: Any) -> list[tuple[int, int, float, int, int]]:
    arr = np.asarray(boxes)
    if arr.size == 0:
        return []
    rows: list[tuple[int, int, float, int, int]] = []
    for box in arr:
        if len(box) < 5:
            continue
        x1, y1, x2, y2, score = [float(value) for value in box[:5]]
        rows.append((
            int((x1 + x2) / 2.0),
            int((y1 + y2) / 2.0),
            float(score),
            int(x2 - x1),
            int(y2 - y1),
        ))
    return rows


def _unique_scores(scores: tuple[float, ...]) -> list[float]:
    out: list[float] = []
    seen: set[float] = set()
    for score in scores:
        rounded = round(float(score), 4)
        if rounded in seen:
            continue
        seen.add(rounded)
        out.append(float(score))
    return out


def _limit_rows(
    rows: list[tuple[int, int, float, int, int]],
    *,
    max_rows: int,
) -> list[tuple[int, int, float, int, int]]:
    if max_rows <= 0 or len(rows) <= max_rows:
        return rows
    return sorted(rows, key=lambda row: row[2], reverse=True)[:max_rows]


def _inpaint_cursor_if_present(frame_bgr: Any) -> Any:
    cursor = _detect_pink_cursor(frame_bgr)
    if cursor is None:
        return frame_bgr
    try:
        import cv2

        arr = np.asarray(frame_bgr)
        height, width = arr.shape[:2]
        radius = max(14, int(min(width, height) * 0.03))
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.circle(mask, (int(cursor[0]), int(cursor[1])), radius, 255, -1)
        return cv2.inpaint(arr, mask, 5, cv2.INPAINT_TELEA)
    except Exception:
        return frame_bgr


def _detect_pink_cursor(frame_bgr: Any) -> tuple[float, float] | None:
    try:
        import cv2

        arr = np.asarray(frame_bgr)
        if arr.size == 0:
            return None
        hsv = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array([140, 80, 80]), np.array([175, 255, 255]))
        contours, _hierarchy = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        contour = max(contours, key=cv2.contourArea)
        if cv2.contourArea(contour) < 15:
            return None
        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            return None
        return (float(moments["m10"] / moments["m00"]), float(moments["m01"] / moments["m00"]))
    except Exception:
        return None
