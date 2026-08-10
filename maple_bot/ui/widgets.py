# 공용 커스텀 위젯 모음
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt


class HotkeyCapture(QPushButton):
    """클릭 후 키 입력을 받아 단축키를 설정하는 버튼.

    - 평소: 현재 단축키 표시
    - 클릭 후: '입력 대기...' 상태에서 다음 키 입력을 단축키로 저장
    - ESC 또는 포커스 아웃: 취소
    """

    _QT_KEY_TO_STR: dict = {
        Qt.Key.Key_F1:  "f1",  Qt.Key.Key_F2:  "f2",  Qt.Key.Key_F3:  "f3",
        Qt.Key.Key_F4:  "f4",  Qt.Key.Key_F5:  "f5",  Qt.Key.Key_F6:  "f6",
        Qt.Key.Key_F7:  "f7",  Qt.Key.Key_F8:  "f8",  Qt.Key.Key_F9:  "f9",
        Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
        Qt.Key.Key_Home:     "home",     Qt.Key.Key_End:      "end",
        Qt.Key.Key_PageUp:   "pageup",   Qt.Key.Key_PageDown:  "pagedown",
        Qt.Key.Key_Insert:   "insert",   Qt.Key.Key_Delete:    "delete",
        Qt.Key.Key_Left:     "left",     Qt.Key.Key_Right:     "right",
        Qt.Key.Key_Up:       "up",       Qt.Key.Key_Down:      "down",
        Qt.Key.Key_Space:    "space",    Qt.Key.Key_Tab:       "tab",
        Qt.Key.Key_Return:   "enter",    Qt.Key.Key_Enter:     "enter",
    }

    def __init__(self, initial_key: str, on_captured):
        super().__init__(initial_key.upper() if initial_key else "-")
        self._key = initial_key
        self._on_captured = on_captured  # Callable[[str], None]
        self._capturing = False
        self.setFixedWidth(80)
        self.setToolTip("클릭 후 원하는 키를 누르세요. ESC로 취소.")
        self.clicked.connect(self._start_capture)

    def current_key(self) -> str:
        return self._key

    def set_key(self, key: str) -> None:
        self._key = key
        self.setText(key.upper() if key else "-")

    # ── 캡처 흐름 ─────────────────────────────────────────────────────
    def _start_capture(self) -> None:
        self._capturing = True
        self.setText("입력 대기...")
        self.setFocus()

    def _cancel_capture(self) -> None:
        self._capturing = False
        self.setText(self._key.upper() if self._key else "-")

    def keyPressEvent(self, event) -> None:
        if not self._capturing:
            super().keyPressEvent(event)
            return

        qt_key = event.key()

        if qt_key == Qt.Key.Key_Escape:
            self._cancel_capture()
            return

        key_str = self._resolve_key(qt_key)
        if key_str is None:
            return  # 수식어 키 단독 입력 무시

        self._capturing = False
        self._key = key_str
        self.setText(key_str.upper())
        self._on_captured(key_str)

    def focusOutEvent(self, event) -> None:
        if self._capturing:
            self._cancel_capture()
        super().focusOutEvent(event)

    # ── Qt 키코드 → 문자열 변환 ───────────────────────────────────────
    def _resolve_key(self, qt_key: int) -> str | None:
        if qt_key in self._QT_KEY_TO_STR:
            return self._QT_KEY_TO_STR[qt_key]
        if Qt.Key.Key_A <= qt_key <= Qt.Key.Key_Z:
            return chr(qt_key).lower()
        if Qt.Key.Key_0 <= qt_key <= Qt.Key.Key_9:
            return chr(qt_key)
        return None
