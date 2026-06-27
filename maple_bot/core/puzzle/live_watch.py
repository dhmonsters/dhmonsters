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
    _TEMPLATE_MIN_W = 100
    _TEMPLATE_MIN_H = 50

    def __init__(
        self,
        *,
        use_yolo: bool = True,
        template_dir: str | Path | None = None,
        popup_score_threshold: float = 0.65,
        allow_white_fallback: bool = False,
        white_threshold: int = 210,
        min_white_pixels: int = 300,
    ) -> None:
        self.use_yolo = use_yolo
        self.template_dir = Path(template_dir) if template_dir is not None else _default_template_dir()
        self.popup_score_threshold = float(popup_score_threshold)
        self.allow_white_fallback = allow_white_fallback
        self.white_threshold = white_threshold
        self.min_white_pixels = min_white_pixels
        self._popup_templates: list[tuple[Any, int, int]] | None = None
        self._shape_yolo: Any | None = None
        self._shape_yolo_loaded = False

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

        yolo_activation = self._detect_with_yolo(board, detect_roi=popup.detect_roi, board_roi=board_roi)
        if yolo_activation.active:
            return yolo_activation

        if self.allow_white_fallback:
            fallback = self._detect_white_shape(board, detect_roi=popup.detect_roi, board_roi=board_roi)
            if fallback.active:
                return fallback

        return popup

    def _detect_popup(self, frame: Any, *, frame_w: int, frame_h: int) -> PuzzleActivation:
        header_roi = fixed_popup_header_roi(frame_w=frame_w, frame_h=frame_h)
        detect_roi = fixed_detect_roi(frame_w=frame_w, frame_h=frame_h)
        board_roi = fixed_board_roi(frame_w=frame_w, frame_h=frame_h)
        header = crop_by_roi(frame, header_roi)
        templates = self._load_popup_templates()
        if not templates:
            return PuzzleActivation(
                False,
                "popup_template_unavailable",
                detect_roi=detect_roi,
                board_roi=board_roi,
                debug={"template_dir": str(self.template_dir)},
            )

        score = self._best_popup_score(header, templates)
        debug = {
            "popup_score": score,
            "popup_score_threshold": self.popup_score_threshold,
            "template_count": len(templates),
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

    def _detect_with_yolo(
        self,
        board: Any,
        *,
        detect_roi: RoiSpec | None = None,
        board_roi: RoiSpec | None = None,
    ) -> PuzzleActivation:
        if not self.use_yolo:
            return PuzzleActivation(False, "yolo_disabled", detect_roi=detect_roi, board_roi=board_roi)
        yolo = self._load_shape_yolo()
        if yolo is None or not getattr(yolo, "enabled", False):
            return PuzzleActivation(False, "yolo_unavailable", detect_roi=detect_roi, board_roi=board_roi)
        candidates = yolo.detect_all(board)
        if not candidates:
            return PuzzleActivation(False, "yolo_no_shape", detect_roi=detect_roi, board_roi=board_roi)
        cx, cy, score, *_rest = max(candidates, key=lambda item: float(item[2]))
        return PuzzleActivation(
            True,
            "shape_yolo",
            (float(cx), float(cy)),
            float(score),
            detect_roi=detect_roi,
            board_roi=board_roi,
        )

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

    def _load_popup_templates(self) -> list[tuple[Any, int, int]]:
        if self._popup_templates is not None:
            return self._popup_templates
        templates: list[tuple[Any, int, int]] = []
        cv2 = _cv2_or_none()
        if cv2 is None or not self.template_dir.is_dir():
            self._popup_templates = templates
            return templates
        for path in sorted(self.template_dir.iterdir()):
            if path.suffix.lower() not in {".bmp", ".png", ".jpg", ".jpeg"}:
                continue
            image = cv2.imread(str(path))
            if image is None:
                continue
            height, width = image.shape[:2]
            if width < self._TEMPLATE_MIN_W or height < self._TEMPLATE_MIN_H:
                continue
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            templates.append((gray, height, width))
        self._popup_templates = templates
        return templates

    def _best_popup_score(self, header: Any, templates: list[tuple[Any, int, int]]) -> float:
        cv2 = _cv2_or_none()
        if cv2 is None:
            return 0.0
        header_gray = cv2.cvtColor(np.asarray(header), cv2.COLOR_BGR2GRAY)
        search_h, search_w = header_gray.shape[:2]
        best_score = 0.0
        for template, template_h, template_w in templates:
            if template_h > search_h or template_w > search_w:
                continue
            result = cv2.matchTemplate(header_gray, template, cv2.TM_CCOEFF_NORMED)
            _min_value, max_value, _min_loc, _max_loc = cv2.minMaxLoc(result)
            if float(max_value) > best_score:
                best_score = float(max_value)
        return best_score


def _default_template_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "templates"


def _cv2_or_none() -> Any | None:
    try:
        import cv2
    except Exception:
        return None
    return cv2
