# 드래그로 화면 영역을 선택하는 전체화면 반투명 오버레이
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont


class RegionSelector(QWidget):
    """마우스 드래그로 화면 영역을 선택한다. ESC로 취소."""

    # x, y, width, height (절대 화면 좌표)
    region_selected = pyqtSignal(int, int, int, int)

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)

        # 전체 가상 데스크톱(멀티모니터 포함) 크기로 설정
        geo = QApplication.primaryScreen().virtualGeometry()
        self.setGeometry(geo)
        self.showFullScreen()

        self._start: QPoint | None = None
        self._current: QPoint | None = None

    # ── 마우스 이벤트 ─────────────────────────────────────────────────
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start = event.pos()
            self._current = event.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._start is not None:
            self._current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._start is not None:
            self._current = event.pos()
            rect = QRect(self._start, self._current).normalized()
            self.close()  # 오버레이를 먼저 닫은 뒤 시그널 발생
            if rect.width() > 2 and rect.height() > 2:
                self.region_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    # ── 그리기 ────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        painter = QPainter(self)

        # 전체 화면 반투명 어두운 오버레이
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self._start is None or self._current is None:
            # 안내 텍스트
            painter.setPen(QColor(255, 255, 255))
            font = QFont(); font.setPointSize(14)
            painter.setFont(font)
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "드래그로 영역을 선택하세요\nESC: 취소",
            )
            return

        rect = QRect(self._start, self._current).normalized()

        # 선택 영역만 투명하게 (아래 화면이 보임)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(rect, QColor(0, 0, 0, 0))

        # 파란 테두리
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        pen = QPen(QColor(30, 144, 255), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        # 좌표 / 크기 텍스트
        painter.setPen(QColor(255, 255, 255))
        font = QFont(); font.setPointSize(10)
        painter.setFont(font)
        info = f"X={rect.x()}  Y={rect.y()}  너비={rect.width()}  높이={rect.height()}"
        text_pos = rect.bottomLeft() + QPoint(4, 18)
        # 화면 밖으로 나가지 않도록 보정
        if text_pos.y() > self.height() - 20:
            text_pos = rect.topLeft() + QPoint(4, -6)
        painter.drawText(text_pos, info)
