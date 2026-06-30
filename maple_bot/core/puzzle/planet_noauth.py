# planet_solver_noauth의 M1 검출기를 퍼즐 라이브 솔버에서 재사용하는 어댑터다.
from __future__ import annotations

from typing import Any

import numpy as np


class PlanetNoAuthDetector:
    def __init__(self, *, use_gpu: bool = False, imgsz: int = 192, score: float = 0.2) -> None:
        self.use_gpu = bool(use_gpu)
        self.imgsz = int(imgsz)
        self.score = float(score)
        self._m1: Any | None = None
        self._load_attempted = False
        self._load_failed = False
        self.load_source = ""
        self.last_error = ""

    @property
    def enabled(self) -> bool:
        return not self._load_failed

    def detect_all(self, board_bgr: Any) -> list[tuple[int, int, float, int, int]]:
        if board_bgr is None or not hasattr(board_bgr, "size") or board_bgr.size == 0:
            return []
        m1 = self._load_m1()
        if m1 is None:
            return []
        try:
            boxes = m1.detect(board_bgr, self.imgsz, self.score)
        except Exception as exc:
            self.last_error = f"{exc.__class__.__name__}: {exc}"
            return []
        return _m1_boxes_to_rows(boxes)

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


def _load_from_planet_live_solver(*, use_gpu: bool) -> tuple[Any, Any]:
    from planet_live_solver import load_models

    return load_models(use_gpu=use_gpu)


def _load_from_planet_yolo_verify(*, use_gpu: bool) -> tuple[Any, Any]:
    from planet_yolo_verify import load_models

    return load_models(use_gpu=use_gpu)


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
