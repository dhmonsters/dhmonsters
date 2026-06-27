# 퍼즐 라이브 감시 게이트가 도형 감지 전 녹화 시작을 막는다.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from core.puzzle.defaults import fixed_board_roi, fixed_detect_roi, fixed_popup_header_roi
from core.puzzle.models import RoiSpec
from core.puzzle.roi import crop_by_roi


@dataclass(frozen=True)
class PuzzleActivation:
    active: bool
    reason: str
    center: tuple[float, float] | None = None
    score: float = 0.0
    detect_roi: RoiSpec | None = None
    board_roi: RoiSpec | None = None
    debug: dict[str, object] | None = None


@dataclass(frozen=True)
class WatchStartResult:
    status: str
    session_dir: Path | None = None
    preview_path: Path | None = None
    preview_frame: Any | None = None
    message: str = ""


class LivePuzzleActivationDetector:
    def __init__(
        self,
        *,
        use_yolo: bool = True,
        template_dir: str | Path | None = None,
        popup_score_threshold: float = 0.50,
        allow_white_fallback: bool = False,
        white_threshold: int = 210,
        min_white_pixels: int = 300,
    ) -> None:
        _ = (use_yolo, template_dir)
        self.popup_score_threshold = float(popup_score_threshold)
        self.allow_white_fallback = allow_white_fallback
        self.white_threshold = white_threshold
        self.min_white_pixels = min_white_pixels

    def detect(self, frame: Any) -> PuzzleActivation:
        if frame is None or not hasattr(frame, "shape") or frame.size == 0:
            return PuzzleActivation(False, "empty_frame")

        frame_h, frame_w = frame.shape[:2]
        popup = self._detect_popup(frame, frame_w=frame_w, frame_h=frame_h)
        if not popup.active:
            if self.allow_white_fallback:
                board_roi = fixed_board_roi(frame_w=frame_w, frame_h=frame_h)
                board = crop_by_roi(frame, board_roi)
                return self._detect_white_shape(board, board_roi=board_roi)
            return popup

        board_roi = popup.board_roi or fixed_board_roi(frame_w=frame_w, frame_h=frame_h)
        board = crop_by_roi(frame, board_roi)
        if board.size == 0:
            return PuzzleActivation(False, "empty_board")
        return popup

    def _detect_popup(self, frame: Any, *, frame_w: int, frame_h: int) -> PuzzleActivation:
        header_roi = fixed_popup_header_roi(frame_w=frame_w, frame_h=frame_h)
        detect_roi = fixed_detect_roi(frame_w=frame_w, frame_h=frame_h)
        board_roi = fixed_board_roi(frame_w=frame_w, frame_h=frame_h)
        header = crop_by_roi(frame, header_roi)
        score = _planet_dark_ratio(header)
        debug = {
            "popup_dark_ratio": score,
            "popup_score_threshold": self.popup_score_threshold,
        }
        if score < self.popup_score_threshold:
            return PuzzleActivation(
                False,
                "popup_not_detected",
                score=score,
                detect_roi=detect_roi,
                board_roi=board_roi,
                debug=debug,
            )
        return PuzzleActivation(
            True,
            "popup_board",
            score=score,
            detect_roi=detect_roi,
            board_roi=board_roi,
            debug=debug,
        )

    def _detect_white_shape(
        self,
        board: Any,
        *,
        detect_roi: RoiSpec | None = None,
        board_roi: RoiSpec | None = None,
    ) -> PuzzleActivation:
        arr = np.asarray(board)
        if arr.ndim < 3:
            gray = arr
        else:
            gray = arr[:, :, :3].mean(axis=2)
        mask = gray >= self.white_threshold
        white_pixels = int(mask.sum())
        if white_pixels < self.min_white_pixels:
            return PuzzleActivation(False, "no_shape", detect_roi=detect_roi, board_roi=board_roi)

        ys, xs = np.nonzero(mask)
        center = (float(xs.mean()), float(ys.mean()))
        score = min(1.0, white_pixels / float(max(self.min_white_pixels, 1)))
        return PuzzleActivation(
            True,
            "white_shape",
            center,
            score,
            detect_roi=detect_roi,
            board_roi=board_roi,
            debug={"white_pixels": white_pixels},
        )

def _planet_dark_ratio(header: Any) -> float:
    arr = np.asarray(header)
    if arr.size == 0:
        return 0.0
    if arr.ndim < 3:
        dark = arr.astype(np.int16) < 80
    else:
        dark = np.all(arr[:, :, :3].astype(np.int16) < 80, axis=2)
    return float(dark.mean())
