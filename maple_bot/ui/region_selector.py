# ?쒕옒洹몃줈 ?붾㈃ ?곸뿭???좏깮?섎뒗 ?꾩껜?붾㈃ 諛섑닾紐??ㅻ쾭?덉씠
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QClipboard


def _copy_text_to_clipboard(text: str) -> None:
    """드래그한 영역 좌표를 Qt와 Windows 클립보드에 함께 복사한다."""
    try:
        clipboard = QApplication.clipboard()
        clipboard.setText(text, QClipboard.Mode.Clipboard)
        QApplication.processEvents()
    except Exception:
        pass
    try:
        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.OpenClipboard(None)
        user32.EmptyClipboard()
        data = text.encode("utf-16le") + b"\x00\x00"
        handle = kernel32.GlobalAlloc(0x0002, len(data))
        locked = kernel32.GlobalLock(handle)
        ctypes.memmove(locked, data, len(data))
        kernel32.GlobalUnlock(handle)
        user32.SetClipboardData(13, handle)
        user32.CloseClipboard()
    except Exception:
        try:
            user32.CloseClipboard()
        except Exception:
            pass


def logical_to_physical(x: int, y: int, w: int, h: int) -> tuple[int, int, int, int]:
    """RegionSelector ?꾩젽-?곷? ?쇰━ ?쎌? ??mss ?덈? 臾쇰━ ?쎌? 蹂??

    RegionSelector??媛???곗뒪?ы넲 湲곗? ?ㅽ봽???꾩튂???볦씤 ?꾩젽?대?濡?
    event.pos()???꾩젽-?곷? 醫뚰몴?? ?꾩뿭 ?쇰━ 醫뚰몴濡?蹂????臾쇰━ 諛곗쑉??怨깊븳??

    硫?곕え?덊꽣?먯꽌 蹂댁“ 紐⑤땲?곌? 二쇰え?덊꽣 ???쇱そ???덉쑝硫?virtual desktop
    origin??(0,0)???꾨땶 ?뚯닔 媛믪쓣 媛吏꾨떎 (?? top=-221). ???ㅽ봽?뗭쓣 諛섎뱶???뷀빐???쒕떎.
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
    # ?꾩젽-?곷? ???꾩뿭 ?쇰━ 醫뚰몴濡?蹂??(媛???곗뒪?ы넲 origin 蹂댁젙)
    abs_x = x + total.x()
    abs_y = y + total.y()
    return int(abs_x * sx), int(abs_y * sy), int(w * sx), int(h * sy)


class RegionSelector(QWidget):
    """留덉슦???쒕옒洹몃줈 ?붾㈃ ?곸뿭???좏깮?쒕떎. ESC濡?痍⑥냼."""

    # x, y, width, height (?덈? ?붾㈃ 醫뚰몴)
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

        # ?꾩껜 媛???곗뒪?ы넲(硫?곕え?덊꽣 ?ы븿) ?ш린濡??ㅼ젙
        # showFullScreen() ? 遊?紐⑤땲?곕쭔 ??쑝誘濡?setGeometry + show() 諛⑹떇?쇰줈 蹂寃?
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

    # ?? 留덉슦???대깽???????????????????????????????????????????????????
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
            if rect.width() > 2 and rect.height() > 2:
                try:
                    try:
                        px, py, pw, ph = logical_to_physical(
                            rect.x(), rect.y(), rect.width(), rect.height()
                        )
                    except Exception:
                        px, py, pw, ph = rect.x(), rect.y(), rect.width(), rect.height()
                    _copy_text_to_clipboard(
                        "logical={"
                        f"'left': {rect.x()}, 'top': {rect.y()}, "
                        f"'width': {rect.width()}, 'height': {rect.height()}"
                        "}\n"
                        "physical={"
                        f"'left': {px}, 'top': {py}, "
                        f"'width': {pw}, 'height': {ph}"
                        "}"
                    )
                    self.region_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())
                except Exception:
                    import traceback, datetime
                    try:
                        with open("error.log", "a", encoding="utf-8") as f:
                            f.write(f"\n{'='*60}\n")
                            f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] RegionSelector release error\n")
                            f.write(traceback.format_exc())
                    except Exception:
                        pass
            self.close()
    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    # ?? 洹몃━湲?????????????????????????????????????????????????????????
    def paintEvent(self, event) -> None:
        try:
            self._paint(event)
        except Exception:
            import traceback, datetime
            try:
                with open("error.log", "a", encoding="utf-8") as f:
                    f.write(f"\n{'='*60}\n")
                    f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] RegionSelector paintEvent ?ㅻ쪟\n")
                    f.write(traceback.format_exc())
            except Exception:
                pass

    def _paint(self, event) -> None:
        painter = QPainter(self)

        # ?꾩껜 ?붾㈃ 諛섑닾紐??대몢???ㅻ쾭?덉씠
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))

        if self._start is None or self._current is None:
            # ?덈궡 ?띿뒪??
            painter.setPen(QColor(255, 255, 255))
            font = QFont(); font.setPointSize(14)
            painter.setFont(font)
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                "?쒕옒洹몃줈 ?곸뿭???좏깮?섏꽭??nESC: 痍⑥냼",
            )
            return

        rect = QRect(self._start, self._current).normalized()

        # ?좏깮 ?곸뿭 ??CompositionMode_Clear ???諛섑닾紐?諛앹? ?됱쑝濡??쒖떆
        # (CompositionMode_Clear ???쇰? GPU/?쒕씪?대쾭?먯꽌 ?щ옒???좊컻)
        painter.fillRect(rect, QColor(255, 255, 255, 40))

        # ?뚮? ?뚮몢由?
        pen = QPen(QColor(30, 144, 255), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        # 醫뚰몴 / ?ш린 ?띿뒪??
        painter.setPen(QColor(255, 255, 255))
        font = QFont(); font.setPointSize(10)
        painter.setFont(font)
        info = f"X={rect.x()}  Y={rect.y()}  ?덈퉬={rect.width()}  ?믪씠={rect.height()}"
        text_pos = rect.bottomLeft() + QPoint(4, 18)
        # ?붾㈃ 諛뽰쑝濡??섍?吏 ?딅룄濡?蹂댁젙
        if text_pos.y() > self.height() - 20:
            text_pos = rect.topLeft() + QPoint(4, -6)
        painter.drawText(text_pos, info)


def capture_template(save_path: str, parent=None) -> bool:
    """RegionSelector濡??쒕옒洹??곸뿭???좏깮???쒗뵆由??대?吏濡???ν븳??

    Returns:
        True  ??????깃났
        False ??痍⑥냼 ?먮뒗 ?ㅻ쪟
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
    # ESC ?먮뒗 李쎌씠 ?ロ엳硫?猷⑦봽 醫낅즺
    selector.destroyed.connect(loop.quit)

    loop.exec()

    if not result:
        return False

    x, y, w, h = result[0]
    if w <= 0 or h <= 0:
        return False

    px, py, pw, ph = logical_to_physical(x, y, w, h)

    # ?좏깮 ?곸뿭 罹≪쿂
    with mss.mss() as sct:
        mon = {"left": px, "top": py, "width": pw, "height": ph}
        raw = sct.grab(mon)
        img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)

    import os
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    cv2.imwrite(save_path, img)
    return True

