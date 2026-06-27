# 퍼즐 라이브 감시 게이트가 도형 감지 전 녹화 시작을 막는다.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from core.puzzle.defaults import fixed_board_roi
from core.puzzle.roi import crop_by_roi


@dataclass(frozen=True)
class PuzzleActivation:
    active: bool
    reason: str
    center: tuple[float, float] | None = None
    score: float = 0.0


@dataclass(frozen=True)
class WatchStartResult:
    status: str
    session_dir: Path | None = None
    preview_path: Path | None = None
    message: str = ""


class LivePuzzleActivationDetector:
    def __init__(
        self,
        *,
        use_yolo: bool = True,
        white_threshold: int = 210,
        min_white_pixels: int = 300,
    ) -> None:
        self.use_yolo = use_yolo
        self.white_threshold = white_threshold
        self.min_white_pixels = min_white_pixels
        self._shape_yolo: Any | None = None
        self._shape_yolo_loaded = False

    def detect(self, frame: Any) -> PuzzleActivation:
        if frame is None or not hasattr(frame, "shape") or frame.size == 0:
            return PuzzleActivation(False, "empty_frame")

        frame_h, frame_w = frame.shape[:2]
        board_roi = fixed_board_roi(frame_w=frame_w, frame_h=frame_h)
        board = crop_by_roi(frame, board_roi)
        if board.size == 0:
            return PuzzleActivation(False, "empty_board")

        yolo_activation = self._detect_with_yolo(board)
        if yolo_activation.active:
            return yolo_activation

        return self._detect_white_shape(board)

    def _detect_with_yolo(self, board: Any) -> PuzzleActivation:
        if not self.use_yolo:
            return PuzzleActivation(False, "yolo_disabled")
        yolo = self._load_shape_yolo()
        if yolo is None or not getattr(yolo, "enabled", False):
            return PuzzleActivation(False, "yolo_unavailable")
        candidates = yolo.detect_all(board)
        if not candidates:
            return PuzzleActivation(False, "yolo_no_shape")
        cx, cy, score, *_rest = max(candidates, key=lambda item: float(item[2]))
        return PuzzleActivation(True, "shape_yolo", (float(cx), float(cy)), float(score))

    def _load_shape_yolo(self):
        if self._shape_yolo_loaded:
            return self._shape_yolo
        self._shape_yolo_loaded = True
        try:
            from core.shape_yolo import ShapeYolo

            self._shape_yolo = ShapeYolo()
        except Exception:
            self._shape_yolo = None
        return self._shape_yolo

    def _detect_white_shape(self, board: Any) -> PuzzleActivation:
        arr = np.asarray(board)
        if arr.ndim < 3:
            gray = arr
        else:
            gray = arr[:, :, :3].mean(axis=2)
        mask = gray >= self.white_threshold
        white_pixels = int(mask.sum())
        if white_pixels < self.min_white_pixels:
            return PuzzleActivation(False, "no_shape")

        ys, xs = np.nonzero(mask)
        center = (float(xs.mean()), float(ys.mean()))
        score = min(1.0, white_pixels / float(max(self.min_white_pixels, 1)))
        return PuzzleActivation(True, "white_shape", center, score)
