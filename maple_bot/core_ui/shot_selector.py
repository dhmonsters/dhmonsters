# 스크린샷 기반 영역 선택기 — 게임창을 캡처해 정지 이미지 위에서 드래그(움직이는 게임보다 정확)
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QPen


def display_to_source_rect(x: int, y: int, w: int, h: int,
                           scale: float, src_origin: tuple[int, int]) -> tuple:
    """표시 이미지 위의 드래그 사각형 → 원본 화면 절대좌표.

    scale: 표시배율(원본 대비. 0.5면 50% 축소표시).
    src_origin: 캡처한 원본 영역의 화면 좌상단(게임창 위치).
    음수 w/h(역방향 드래그)는 정규화한다.
    """
    # 정규화 (좌상단 기준 + 양수 크기)
    if w < 0:
        x, w = x + w, -w
    if h < 0:
        y, h = y + h, -h
    # 표시 → 원본 상대 (역배율)
    sx = x / scale
    sy = y / scale
    sw = w / scale
    sh = h / scale
    # 원본 절대 (게임창 오프셋)
    ox, oy = src_origin
    return (int(ox + sx), int(oy + sy), int(sw), int(sh))


class ScreenshotRegionSelector(QDialog):
    """게임창 스크린샷을 띄우고 그 위에서 드래그로 영역 선택.

    region_selected(x, y, w, h) — 원본 화면 절대좌표로 발행.
    """
    region_selected = pyqtSignal(int, int, int, int)

    def __init__(self, bgr_image, src_origin=(0, 0), max_display=1100, parent=None):
        """bgr_image: 캡처된 BGR ndarray. src_origin: 캡처 영역의 화면 좌상단."""
        super().__init__(parent)
        self.setWindowTitle("영역 선택 — 드래그하세요 (ESC 취소)")
        self._origin = src_origin

        import numpy as np
        h, w = bgr_image.shape[:2]
        # 큰 화면은 축소 표시 (max_display 넘으면)
        self._scale = min(1.0, max_display / max(w, h))
        disp_w, disp_h = int(w * self._scale), int(h * self._scale)

        # BGR → QImage(RGB)
        rgb = np.ascontiguousarray(bgr_image[:, :, ::-1])
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        self._pix = QPixmap.fromImage(qimg).scaled(
            disp_w, disp_h, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self._label = QLabel()
        self._label.setPixmap(self._pix)
        self._label.setFixedSize(disp_w, disp_h)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._label)

        self._start: QPoint | None = None
        self._cur: QPoint | None = None

    # ── 드래그 ────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        self._start = self._to_label(e.position().toPoint())
        self._cur = self._start
        self.update()

    def mouseMoveEvent(self, e):
        if self._start is not None:
            self._cur = self._to_label(e.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, e):
        if self._start is None or self._cur is None:
            return
        x, y = self._start.x(), self._start.y()
        w, h = self._cur.x() - x, self._cur.y() - y
        rx, ry, rw, rh = display_to_source_rect(x, y, w, h, self._scale, self._origin)
        if rw > 2 and rh > 2:
            self.region_selected.emit(rx, ry, rw, rh)
            self.accept()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reject()

    def _to_label(self, p: QPoint) -> QPoint:
        # 다이얼로그 좌표 → 라벨(이미지) 좌표
        lp = self._label.mapFrom(self, p)
        return QPoint(max(0, min(lp.x(), self._pix.width())),
                      max(0, min(lp.y(), self._pix.height())))

    def paintEvent(self, e):
        super().paintEvent(e)
        if self._start and self._cur:
            qp = QPainter(self)
            qp.setPen(QPen(QColor("#5e6ad2"), 2))
            qp.drawRect(QRect(self._start, self._cur).normalized())
