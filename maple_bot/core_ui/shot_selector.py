# 스크린샷 기반 영역 선택기 — 게임창을 캡처해 정지 이미지 위에서 드래그(움직이는 게임보다 정확)
from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QWidget, QVBoxLayout, QScrollArea
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


def rect_to_offsets(left: int, top: int, w: int, h: int,
                    anchor: tuple[int, int]) -> tuple:
    """원본 박스 → 앵커(캐릭) 기준 상대 오프셋 (x_min, x_max, y_min, y_max)."""
    ax, ay = anchor
    return (left - ax, left + w - ax, top - ay, top + h - ay)


def offsets_to_rect(x_min: int, x_max: int, y_min: int, y_max: int,
                    anchor: tuple[int, int]) -> tuple:
    """앵커 기준 오프셋 → 원본 박스 (left, top, w, h). 기존 범위 미리보기용."""
    ax, ay = anchor
    return (ax + x_min, ay + y_min, x_max - x_min, y_max - y_min)


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
        # 작은 미니맵은 확대 표시(최대 6배). display_to_point가 역배율로 환산
        self._scale = min(6.0, max_display / max(w, h))
        dw, dh = int(w * self._scale), int(h * self._scale)
        rgb = np.ascontiguousarray(bgr_image[:, :, ::-1])
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            dw, dh, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation)   # 도트 미니맵 선명 확대
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


class _LineCanvas(QWidget):
    """이미지 위 드래그로 시작→끝 직선. 양끝 점 + 라벤더 직선 표시."""

    def __init__(self, pix: QPixmap, on_release):
        super().__init__()
        self._pix = pix
        self._on_release = on_release
        self.setFixedSize(pix.width(), pix.height())
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.start: QPoint | None = None
        self.cur: QPoint | None = None

    def _clamp(self, p: QPoint) -> QPoint:
        return QPoint(max(0, min(p.x(), self._pix.width())),
                      max(0, min(p.y(), self._pix.height())))

    def mousePressEvent(self, e):
        self.start = self._clamp(e.position().toPoint()); self.cur = self.start; self.update()

    def mouseMoveEvent(self, e):
        if self.start is not None:
            self.cur = self._clamp(e.position().toPoint()); self.update()

    def mouseReleaseEvent(self, e):
        if self.start and self.cur:
            self._on_release(self.start, self.cur)

    def paintEvent(self, e):
        qp = QPainter(self)
        qp.drawPixmap(0, 0, self._pix)
        if self.start and self.cur:
            qp.setPen(QPen(QColor("#5e6ad2"), 3))
            qp.drawLine(self.start, self.cur)
            for pt, col in [(self.start, "#27a644"), (self.cur, "#f04452")]:
                qp.setPen(QPen(QColor(col), 2))
                qp.drawEllipse(pt, 5, 5)


class LinePointPicker(QDialog):
    """이미지 위 시작→끝 드래그로 직선의 양 끝점 좌표를 얻는다.
    line_picked(sx, sy, ex, ey) — 원본 좌표."""
    line_picked = pyqtSignal(int, int, int, int)

    def __init__(self, bgr_image, max_display=900, parent=None):
        super().__init__(parent)
        self.setWindowTitle("시작→끝 드래그 (ESC 취소)")
        import numpy as np
        h, w = bgr_image.shape[:2]
        # 작은 미니맵은 확대 표시(최대 6배). display_to_point가 역배율로 환산
        self._scale = min(6.0, max_display / max(w, h))
        dw, dh = int(w * self._scale), int(h * self._scale)
        rgb = np.ascontiguousarray(bgr_image[:, :, ::-1])
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            dw, dh, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation)   # 도트 미니맵 선명 확대
        self._canvas = _LineCanvas(pix, self._on_release)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._canvas)

    def _on_release(self, s: QPoint, c: QPoint):
        sx, sy = display_to_point(s.x(), s.y(), self._scale)
        ex, ey = display_to_point(c.x(), c.y(), self._scale)
        self.line_picked.emit(sx, sy, ex, ey)
        self.accept()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reject()


class _Canvas(QWidget):
    """배경 이미지 + 드래그 사각형을 한 표면에 그리는 캔버스.
    QLabel을 쓰면 이미지가 사각형을 가리므로 직접 paint 한다.
    좌표는 source(원본 이미지) 기준으로 보관하고, eff(표시배율)을 곱해 그린다 → Ctrl+휠 줌 가능."""

    def __init__(self, src_img: QImage, eff: float, on_release,
                 initial_src=None, anchor_src=None, overlays_src=None):
        super().__init__()
        self._src = src_img
        self.eff = eff                       # 표시배율(원본→표시). 줌 시 갱신
        self._on_release = on_release
        self._initial_src = initial_src      # (l,t,w,h) 원본좌표 기존범위
        self._anchor_src = anchor_src        # (x,y) 원본좌표 기준점
        self._overlays_src = overlays_src or []  # [(l,t,w,h,color,label), ...] 원본좌표
        self._pix = QPixmap()
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.start: QPoint | None = None
        self.cur: QPoint | None = None
        self.set_eff(eff)

    def set_eff(self, eff: float) -> None:
        """표시배율 변경 → 픽스맵 재생성·크기 갱신(드래그 좌표는 표시공간 그대로)."""
        self.eff = eff
        w, h = self._src.width(), self._src.height()
        self._pix = QPixmap.fromImage(self._src).scaled(
            max(1, int(w * eff)), max(1, int(h * eff)),
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.setFixedSize(self._pix.width(), self._pix.height())
        self.update()

    def _clamp(self, p: QPoint) -> QPoint:
        return QPoint(max(0, min(p.x(), self._pix.width())),
                      max(0, min(p.y(), self._pix.height())))

    def _r(self, l, t, w, h) -> QRect:   # 원본좌표 → 현재 표시좌표
        return QRect(int(l * self.eff), int(t * self.eff),
                     int(w * self.eff), int(h * self.eff))

    def mousePressEvent(self, e):
        self.start = self._clamp(e.position().toPoint())
        self.cur = self.start
        self.update()

    def mouseMoveEvent(self, e):
        if self.start is not None:
            self.cur = self._clamp(e.position().toPoint())
            self.update()

    def mouseReleaseEvent(self, e):
        if self.start is not None:
            self.cur = self._clamp(e.position().toPoint())
            self.update()
            self._on_release(QRect(self.start, self.cur).normalized())

    def paintEvent(self, e):
        qp = QPainter(self)
        qp.drawPixmap(0, 0, self._pix)
        # 감지 오버레이 (닉네임=노랑, 몬스터=빨강 등) — 항상 표시
        for l, t, w, h, color, label in self._overlays_src:
            qp.setBrush(Qt.BrushStyle.NoBrush)
            qp.setPen(QPen(QColor(color), 2))
            rect = self._r(l, t, w, h)
            qp.drawRect(rect)
            if label:
                qp.setFont(QFont("Inter", 9))
                qp.drawText(rect.left(), rect.top() - 3, label)
        # 앵커(캐릭 기준점) 십자
        if self._anchor_src is not None:
            qp.setPen(QPen(QColor("#27a644"), 1, Qt.PenStyle.DashLine))
            ax = int(self._anchor_src[0] * self.eff); ay = int(self._anchor_src[1] * self.eff)
            qp.drawLine(ax - 10, ay, ax + 10, ay)
            qp.drawLine(ax, ay - 10, ax, ay + 10)
        # 드래그 전이면 기존 범위(점선) 미리보기
        if not (self.start and self.cur):
            if self._initial_src is not None:
                qp.setPen(QPen(QColor("#828fff"), 2, Qt.PenStyle.DashLine))
                qp.setBrush(Qt.BrushStyle.NoBrush)
                qp.drawRect(self._r(*self._initial_src))
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

    def __init__(self, bgr_image, src_origin=(0, 0), max_display=1100, parent=None,
                 initial_rect=None, anchor=None, overlays=None):
        """initial_rect: 기존 범위 (left,top,w,h) 원본. anchor: 기준점(x,y) 원본.
        overlays: [(left,top,w,h,color,label), ...] 원본좌표 — 닉네임/몬스터 표시."""
        super().__init__(parent)
        self.setWindowTitle("영역 선택 — 드래그하세요 (ESC 취소)")
        self._origin = src_origin
        self._initial_rect = initial_rect
        self._anchor = anchor
        self._overlays_src = overlays or []

        import numpy as np
        h, w = bgr_image.shape[:2]
        self._base = min(1.0, max_display / max(w, h))   # 처음 화면맞춤 배율
        self._zoom = 1.0                                  # Ctrl+휠 줌(1.0=기본)

        rgb = np.ascontiguousarray(bgr_image[:, :, ::-1])
        self._src_img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()

        # 캔버스는 원본좌표 + eff(=base*zoom)로 그린다(줌해도 좌표 정합 유지)
        self._canvas = _Canvas(self._src_img, self._base, self._on_release,
                               initial_src=self._initial_rect, anchor_src=self._anchor,
                               overlays_src=self._overlays_src)

        # 스크롤 영역으로 감싸 줌 인 시 이동 가능, 다이얼로그는 화면맞춤 크기로
        self._scroll = QScrollArea()
        self._scroll.setWidget(self._canvas)
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._scroll)
        self.resize(min(int(w * self._base) + 4, 1280),
                    min(int(h * self._base) + 4, 860))
        self.setWindowState(Qt.WindowState.WindowMaximized)

    @property
    def _scale(self) -> float:    # 현재 유효 배율(테스트/호환)
        return self._base * self._zoom

    def wheelEvent(self, e):
        """Ctrl+휠 → 확대/축소(0.2~8배). 일반 휠은 스크롤(스크롤영역 기본동작)."""
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            step = 1.15 if e.angleDelta().y() > 0 else 1 / 1.15
            self._zoom = max(0.2, min(8.0, self._zoom * step))
            self._canvas.set_eff(self._base * self._zoom)
            e.accept()
        else:
            super().wheelEvent(e)

    def _on_release(self, rect: QRect):
        rx, ry, rw, rh = display_to_source_rect(
            rect.x(), rect.y(), rect.width(), rect.height(),
            self._canvas.eff, self._origin,
        )
        if rw > 2 and rh > 2:
            self.region_selected.emit(rx, ry, rw, rh)
            self.accept()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.reject()
