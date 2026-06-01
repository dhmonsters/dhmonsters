# 스크린샷 기반 영역 선택기 — 게임창을 캡처해 정지 이미지 위에서 드래그(움직이는 게임보다 정확)
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QPainter, QColor, QPen, QFont


def display_to_source_rect(x: int, y: int, w: int, h: int,
                           scale: float, src_origin: tuple[int, int]) -> tuple:
    """표시 이미지 위의 드래그 사각형 → 원본 화면 절대좌표.

    scale: 표시배율(원본 대비. 0.5면 50% 축소표시).
    src_origin: 캡처한 원본 영역의 화면 좌상단(게임창 위치).
    음수 w/h(역방향 드래그)는 정규화한다.
    """
    if w < 0:
        x, w = x + w, -w
    if h < 0:
        y, h = y + h, -h
    sx = x / scale
    sy = y / scale
    sw = w / scale
    sh = h / scale
    ox, oy = src_origin
    return (int(ox + sx), int(oy + sy), int(sw), int(sh))


def display_to_point(x: int, y: int, scale: float) -> tuple:
    """표시 클릭좌표 → 원본 좌표(역배율). 미니맵 클릭 픽커용."""
    return (int(round(x / scale)), int(round(y / scale)))


class _ClickCanvas(QWidget):
    """이미지 표시 + 클릭 위치에 십자 마커. 클릭하면 콜백."""

    def __init__(self, pix: QPixmap, on_click):
        super().__init__()
        self._pix = pix
        self._on_click = on_click
        self.setFixedSize(pix.width(), pix.height())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._pt: QPoint | None = None

    def mousePressEvent(self, e):
        p = e.position().toPoint()
        self._pt = QPoint(max(0, min(p.x(), self._pix.width())),
                          max(0, min(p.y(), self._pix.height())))
        self.update()
        self._on_click(self._pt)

    def paintEvent(self, e):
        qp = QPainter(self)
        qp.drawPixmap(0, 0, self._pix)
        if self._pt:
            qp.setPen(QPen(QColor("#5e6ad2"), 2))
            x, y = self._pt.x(), self._pt.y()
            qp.drawLine(x - 8, y, x + 8, y)
            qp.drawLine(x, y - 8, x, y + 8)


class ClickPointPicker(QDialog):
    """이미지에서 한 점을 클릭해 좌표를 얻는다. point_picked(x, y) — 원본 좌표."""
    point_picked = pyqtSignal(int, int)

    def __init__(self, bgr_image, max_display=900, parent=None):
        super().__init__(parent)
        self.setWindowTitle("좌표 클릭 (ESC 취소)")
        import numpy as np
        h, w = bgr_image.shape[:2]
        self._scale = min(1.0, max_display / max(w, h))
        dw, dh = int(w * self._scale), int(h * self._scale)
        rgb = np.ascontiguousarray(bgr_image[:, :, ::-1])
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            dw, dh, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self._canvas = _ClickCanvas(pix, self._on_click)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)

    def _on_click(self, pt: QPoint):
        x, y = display_to_point(pt.x(), pt.y(), self._scale)
        self.point_picked.emit(x, y)
        self.accept()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reject()


class _Canvas(QWidget):
    """배경 이미지 + 드래그 사각형을 한 표면에 그리는 캔버스.
    QLabel을 쓰면 이미지가 사각형을 가리므로 직접 paint 한다."""

    def __init__(self, pix: QPixmap, on_release):
        super().__init__()
        self._pix = pix
        self._on_release = on_release
        self.setFixedSize(pix.width(), pix.height())
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.start: QPoint | None = None
        self.cur: QPoint | None = None

    def _clamp(self, p: QPoint) -> QPoint:
        return QPoint(max(0, min(p.x(), self._pix.width())),
                      max(0, min(p.y(), self._pix.height())))

    def mousePressEvent(self, e):
        self.start = self._clamp(e.position().toPoint())
        self.cur = self.start
        self.update()

    def mouseMoveEvent(self, e):
        if self.start is not None:
            self.cur = self._clamp(e.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, e):
        if self.start and self.cur:
            self._on_release(QRect(self.start, self.cur).normalized())

    def paintEvent(self, e):
        qp = QPainter(self)
        qp.drawPixmap(0, 0, self._pix)
        if not (self.start and self.cur):
            return
        rect = QRect(self.start, self.cur).normalized()
        # 선택 영역 밖을 어둡게 (선택 부분 도드라지게)
        mask = QColor(1, 1, 2, 150)   # near-black 반투명
        qp.setPen(Qt.PenStyle.NoPen)
        qp.setBrush(mask)
        full = self.rect()
        qp.drawRect(QRect(0, 0, full.width(), rect.top()))                       # 위
        qp.drawRect(QRect(0, rect.bottom(), full.width(), full.height()))        # 아래
        qp.drawRect(QRect(0, rect.top(), rect.left(), rect.height()))            # 왼
        qp.drawRect(QRect(rect.right(), rect.top(), full.width(), rect.height()))# 오
        # 라벤더 테두리
        qp.setBrush(Qt.BrushStyle.NoBrush)
        qp.setPen(QPen(QColor("#5e6ad2"), 2))
        qp.drawRect(rect)
        # 크기 텍스트
        qp.setPen(QColor("#f7f8f8"))
        qp.setFont(QFont("Inter", 10))
        qp.drawText(rect.left() + 4, rect.top() - 6, f"{rect.width()} × {rect.height()}")


class ScreenshotRegionSelector(QDialog):
    """게임창 스크린샷을 띄우고 그 위에서 드래그로 영역 선택.
    region_selected(x, y, w, h) — 원본 화면 절대좌표로 발행.
    """
    region_selected = pyqtSignal(int, int, int, int)

    def __init__(self, bgr_image, src_origin=(0, 0), max_display=1100, parent=None):
        super().__init__(parent)
        self.setWindowTitle("영역 선택 — 드래그하세요 (ESC 취소)")
        self._origin = src_origin

        import numpy as np
        h, w = bgr_image.shape[:2]
        self._scale = min(1.0, max_display / max(w, h))
        disp_w, disp_h = int(w * self._scale), int(h * self._scale)

        rgb = np.ascontiguousarray(bgr_image[:, :, ::-1])
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            disp_w, disp_h, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self._canvas = _Canvas(pix, self._on_release)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)

    def _on_release(self, rect: QRect):
        rx, ry, rw, rh = display_to_source_rect(
            rect.x(), rect.y(), rect.width(), rect.height(),
            self._scale, self._origin,
        )
        if rw > 2 and rh > 2:
            self.region_selected.emit(rx, ry, rw, rh)
            self.accept()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reject()
