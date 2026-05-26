# 드래그로 화면 영역을 선택하는 전체화면 반투명 오버레이
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont


def logical_to_physical(x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
    """RegionSelector 위젯-상대 논리 픽셀 → mss 절대 물리 픽셀 변환.

    RegionSelector는 가상 데스크톱 기준 오프셋 위치에 놓인 위젯이므로
    event.pos()는 위젯-상대 좌표다. 전역 논리 좌표로 변환 후 물리 배율을 곱한다.

    멀티모니터에서 보조 모니터가 주모니터 위/왼쪽에 있으면 virtual desktop
    origin이 (0,0)이 아닌 음수 값을 가진다 (예: top=-221). 이 오프셋을 반드시 더해야 한다.
    """
    import mss as _mss
    from PyQt6.QtCore import QRect
    total = QRect()
    for s in QApplication.screens():
        total = total.united(s.geometry())
    with _mss.mss() as sct:
        mon = sct.monitors[0]
        phys_w, phys_h = mon["width"], mon["height"]
    sx = phys_w / max(1, total.width())
    sy = phys_h / max(1, total.height())
    # 위젯-상대 → 전역 논리 좌표로 변환 (가상 데스크톱 origin 보정)
    abs_x = x + total.x()
    abs_y = y + total.y()
    return int(abs_x * sx), int(abs_y * sy), int(w * sx), int(h * sy)


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
        # showFullScreen() 은 봇 모니터만 덮으므로 setGeometry + show() 방식으로 변경
        from PyQt6.QtCore import QRect
        total_rect = QRect()
        for screen in QApplication.screens():
            total_rect = total_rect.united(screen.geometry())
        self.setGeometry(total_rect)
        self.show()
        self.activateWindow()
        self.raise_()
        self.setFocus()

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
                try:
                    self.region_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())
                except Exception:
                    import traceback, datetime
                    try:
                        with open("error.log", "a", encoding="utf-8") as f:
                            f.write(f"\n{'='*60}\n")
                            f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] RegionSelector 슬롯 오류\n")
                            f.write(traceback.format_exc())
                    except Exception:
                        pass

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    # ── 그리기 ────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:
        try:
            self._paint(event)
        except Exception:
            import traceback, datetime
            try:
                with open("error.log", "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] RegionSelector paintEvent 오류\n")
                    f.write(traceback.format_exc())
            except Exception:
                pass

    def _paint(self, event) -> None:
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

        # 선택 영역 — CompositionMode_Clear 대신 반투명 밝은 색으로 표시
        # (CompositionMode_Clear 는 일부 GPU/드라이버에서 크래시 유발)
        painter.fillRect(rect, QColor(255, 255, 255, 40))

        # 파란 테두리
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


def capture_template(save_path: str, parent=None) -> bool:
    """RegionSelector로 드래그 영역을 선택해 템플릿 이미지로 저장한다.

    Returns:
        True  — 저장 성공
        False — 취소 또는 오류
    """
    import cv2
    import mss
    import numpy as np
    from PyQt6.QtCore import QEventLoop

    result: list[tuple[int, int, int, int]] = []

    selector = RegionSelector()

    loop = QEventLoop()

    def on_selected(x: int, y: int, w: int, h: int) -> None:
        result.append((x, y, w, h))
        loop.quit()

    selector.region_selected.connect(on_selected)
    # ESC 또는 창이 닫히면 루프 종료
    selector.destroyed.connect(loop.quit)

    loop.exec()

    if not result:
        return False

    x, y, w, h = result[0]
    if w <= 0 or h <= 0:
        return False

    px, py, pw, ph = logical_to_physical(x, y, w, h)

    # 선택 영역 캡처
    with mss.mss() as sct:
        mon = {"left": px, "top": py, "width": pw, "height": ph}
        raw = sct.grab(mon)
        img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)

    import os
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    cv2.imwrite(save_path, img)
    return True
