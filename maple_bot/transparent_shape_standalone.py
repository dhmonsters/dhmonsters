# 투명 도형 찾기 미니게임 독립 실행 추적 프로그램 (PyQt6 GUI)
# 실행: python transparent_shape_standalone.py

import sys
import os
import time
import json
import threading
from datetime import datetime

import numpy as np
import cv2
import mss
import win32api
import win32con

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLabel, QTextEdit,
)
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QCursor, QScreen

# ── 파라미터 ─────────────────────────────────────────────────────────
FRAME_INTERVAL = 0.033
EMA_ALPHA      = 0.35
MAX_SPEED      = 30
SPEED_PROP     = 0.4

WHITE_THRESH   = 200
WHITE_MIN_AREA = 800
WHITE_MAX_AREA = 40000
WHITE_KERNEL   = (7, 7)

DIFF_THRESH    = 20
DIFF_MIN_AREA  = 400

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "board_roi.json")

# 기본 단축키
DEFAULT_START_KEY = "f9"
DEFAULT_STOP_KEY  = "f10"

# ── 다크 스타일 (maple bot 동일 계열) ────────────────────────────────
DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #2b2b2b;
    color: #cccccc;
}
QGroupBox {
    border: 1px solid #555;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 4px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
}
QPushButton {
    background-color: #3c3f41;
    color: #cccccc;
    border: 1px solid #555;
    border-radius: 3px;
    padding: 4px 12px;
    min-height: 28px;
}
QPushButton:hover  { background-color: #4c5052; }
QPushButton:disabled { color: #666; }
QTextEdit {
    background-color: #1e1e1e;
    color: #aaaaaa;
    border: 1px solid #444;
    font-family: Consolas, monospace;
    font-size: 11px;
}
QLabel { color: #cccccc; }
"""

BTN_START   = "background-color:#4CAF50; color:white; font-weight:bold;"
BTN_STOP    = "background-color:#f44336; color:white; font-weight:bold;"
BTN_ROI     = "background-color:#2196F3; color:white; font-weight:bold;"
BTN_CAPTURE = "background-color:#FF9800; color:white; font-weight:bold;"


# ── ROI + 단축키 저장/로드 ───────────────────────────────────────────
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(data: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 가상 키코드 변환 ─────────────────────────────────────────────────
_VK_MAP: dict[str, int] = {
    "left":  win32con.VK_LEFT,  "right": win32con.VK_RIGHT,
    "up":    win32con.VK_UP,    "down":  win32con.VK_DOWN,
    "space": win32con.VK_SPACE, "enter": win32con.VK_RETURN,
    "esc":   win32con.VK_ESCAPE,"ctrl":  win32con.VK_CONTROL,
    "shift": win32con.VK_SHIFT, "alt":   win32con.VK_MENU,
    "home":  win32con.VK_HOME,  "end":   win32con.VK_END,
    "ins":   win32con.VK_INSERT,"del":   win32con.VK_DELETE,
    "tab":   win32con.VK_TAB,
}

def _to_vk(key: str) -> int | None:
    key = key.strip().lower()
    if key in _VK_MAP:
        return _VK_MAP[key]
    if key.startswith("f") and key[1:].isdigit():
        n = int(key[1:])
        if 1 <= n <= 24:
            return win32con.VK_F1 + (n - 1)
    if len(key) == 1:
        vk = win32api.VkKeyScan(key) & 0xFF
        return vk if vk != 0xFF else None
    return None

def _vk_to_name(vk: int) -> str:
    """가상 키코드 → 키 이름 역변환 (표시용)."""
    for name, code in _VK_MAP.items():
        if code == vk:
            return name
    if win32con.VK_F1 <= vk <= win32con.VK_F24:
        return f"f{vk - win32con.VK_F1 + 1}"
    try:
        ch = chr(win32api.MapVirtualKey(vk, 2))
        if ch.isprintable():
            return ch.lower()
    except Exception:
        pass
    return f"vk{vk}"


# ── 전역 단축키 폴러 ─────────────────────────────────────────────────
class HotkeyPoller(QObject):
    """GetAsyncKeyState 폴링으로 전역 단축키를 감지한다."""
    triggered = pyqtSignal(str)   # "start" | "stop"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hotkeys: dict[str, int] = {}   # name → vk
        self._prev_state: dict[str, bool] = {}
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._timer  = QTimer(self)
        self._queue: list[str] = []
        self._queue_lock = threading.Lock()
        self._timer.setInterval(30)
        self._timer.timeout.connect(self._dispatch)
        self._timer.start()
        self._thread.start()

    def set_key(self, name: str, key: str) -> bool:
        vk = _to_vk(key)
        if vk is None:
            return False
        self._hotkeys[name] = vk
        self._prev_state[name] = False
        return True

    def stop(self):
        self._stop_event.set()
        self._timer.stop()

    def _poll(self):
        while not self._stop_event.is_set():
            for name, vk in list(self._hotkeys.items()):
                pressed = bool(win32api.GetAsyncKeyState(vk) & 0x8000)
                prev    = self._prev_state.get(name, False)
                if pressed and not prev:
                    with self._queue_lock:
                        self._queue.append(name)
                self._prev_state[name] = pressed
            time.sleep(0.01)

    def _dispatch(self):
        with self._queue_lock:
            items, self._queue = self._queue[:], []
        for name in items:
            self.triggered.emit(name)


# ── 키 캡처 버튼 ─────────────────────────────────────────────────────
class KeyCaptureButton(QPushButton):
    """클릭하면 다음 키 입력을 캡처해 표시하는 버튼."""
    key_captured = pyqtSignal(str)   # 캡처된 키 이름

    # 무시할 modifier 키
    _IGNORE_VK = {
        win32con.VK_SHIFT, win32con.VK_LSHIFT, win32con.VK_RSHIFT,
        win32con.VK_CONTROL, win32con.VK_LCONTROL, win32con.VK_RCONTROL,
        win32con.VK_MENU, win32con.VK_LMENU, win32con.VK_RMENU,
    }

    def __init__(self, key: str = "", parent=None):
        super().__init__(parent)
        self._current_key = key
        self._listening   = False
        self._poll_timer  = QTimer(self)
        self._poll_timer.setInterval(20)
        self._poll_timer.timeout.connect(self._check_key)
        self._update_text()

    def set_key(self, key: str):
        self._current_key = key
        self._update_text()

    def current_key(self) -> str:
        return self._current_key

    def _update_text(self):
        if self._listening:
            self.setText("… 키를 누르세요")
            self.setStyleSheet(BTN_CAPTURE)
        else:
            self.setText(self._current_key.upper() if self._current_key else "(없음)")
            self.setStyleSheet("")

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        if not self._listening:
            self._listening = True
            self._update_text()
            self._poll_timer.start()

    def _check_key(self):
        for vk in range(1, 255):
            if vk in self._IGNORE_VK:
                continue
            if win32api.GetAsyncKeyState(vk) & 0x8000:
                if vk == win32con.VK_ESCAPE:
                    self._cancel()
                    return
                name = _vk_to_name(vk)
                self._current_key = name
                self._listening   = False
                self._poll_timer.stop()
                self._update_text()
                self.key_captured.emit(name)
                return

    def _cancel(self):
        self._listening = False
        self._poll_timer.stop()
        self._update_text()


# ── PyQt6 ROI 선택 오버레이 ──────────────────────────────────────────
class RoiOverlay(QWidget):
    """전체 화면 반투명 오버레이 — 드래그로 ROI 선택."""
    roi_selected = pyqtSignal(int, int, int, int)   # x, y, w, h

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

        screen: QScreen = QApplication.primaryScreen()
        geom = screen.geometry()
        self.setGeometry(geom)
        self.showFullScreen()

        self._start = None
        self._end   = None

    def mousePressEvent(self, e):
        self._start = e.pos()
        self._end   = e.pos()

    def mouseMoveEvent(self, e):
        self._end = e.pos()
        self.update()

    def mouseReleaseEvent(self, e):
        self._end = e.pos()
        self.update()
        if self._start and self._end:
            x1 = min(self._start.x(), self._end.x())
            y1 = min(self._start.y(), self._end.y())
            x2 = max(self._start.x(), self._end.x())
            y2 = max(self._start.y(), self._end.y())
            w, h = x2 - x1, y2 - y1
            if w > 10 and h > 10:
                self.roi_selected.emit(x1, y1, w, h)
        self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.close()

    def paintEvent(self, e):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        if self._start and self._end:
            x1 = min(self._start.x(), self._end.x())
            y1 = min(self._start.y(), self._end.y())
            x2 = max(self._start.x(), self._end.x())
            y2 = max(self._start.y(), self._end.y())
            painter.fillRect(x1, y1, x2 - x1, y2 - y1, QColor(0, 0, 0, 0))
            pen = QPen(QColor(255, 80, 80), 2)
            painter.setPen(pen)
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
            "  게임판 영역을 드래그하세요  (ESC 취소)"
        )


# ── 감지 함수 ─────────────────────────────────────────────────────────
def _contour_center(mask, min_a, max_a):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid = [c for c in contours if min_a <= cv2.contourArea(c) <= max_a]
    if not valid:
        return None
    c = max(valid, key=cv2.contourArea)
    m = cv2.moments(c)
    if m["m00"] == 0:
        return None
    return (int(m["m10"] / m["m00"]), int(m["m01"] / m["m00"]))


def find_white(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, WHITE_THRESH, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, WHITE_KERNEL)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return _contour_center(mask, WHITE_MIN_AREA, WHITE_MAX_AREA)


def find_diff(img, prev):
    if prev is None or prev.shape != img.shape:
        return None
    diff = cv2.absdiff(img, prev)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, DIFF_THRESH, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel)
    return _contour_center(mask, DIFF_MIN_AREA, WHITE_MAX_AREA)


# ── 시그널 브릿지 ─────────────────────────────────────────────────────
class _Emitter(QObject):
    log = pyqtSignal(str)
    stopped = pyqtSignal()


# ── 추적 스레드 ───────────────────────────────────────────────────────
class ShapeTracker:
    def __init__(self, roi, emitter: _Emitter):
        self.roi = roi
        self._emitter = emitter
        self._ema_x = None
        self._ema_y = None
        self._prev  = None
        self._stop  = threading.Event()

    def stop(self):
        self._stop.set()

    def _ema(self, ax, ay):
        if self._ema_x is None:
            self._ema_x, self._ema_y = float(ax), float(ay)
        else:
            self._ema_x = EMA_ALPHA * ax + (1 - EMA_ALPHA) * self._ema_x
            self._ema_y = EMA_ALPHA * ay + (1 - EMA_ALPHA) * self._ema_y
        return self._ema_x, self._ema_y

    def _move(self, tx, ty):
        try:
            cx, cy = win32api.GetCursorPos()
        except Exception:
            return
        dx, dy = tx - cx, ty - cy
        dist = (dx * dx + dy * dy) ** 0.5
        if dist < 1.0:
            return
        step = min(dist * SPEED_PROP, MAX_SPEED)
        r = step / dist
        try:
            win32api.SetCursorPos((int(round(cx + dx * r)), int(round(cy + dy * r))))
        except Exception:
            pass

    def run(self):
        x, y, w, h = self.roi["x"], self.roi["y"], self.roi["w"], self.roi["h"]
        region = {"left": x, "top": y, "width": w, "height": h}
        self._ema_x = x + w / 2.0
        self._ema_y = y + h / 2.0
        self._prev  = None

        self._emitter.log.emit(f"[추적 시작] {w}×{h} @ ({x},{y})")

        with mss.MSS() as sct:
            while not self._stop.is_set():
                t0 = time.time()

                raw   = sct.grab(region)
                board = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)

                rel   = find_white(board)
                if rel is None:
                    rel = find_diff(board, self._prev)

                self._prev = board

                if rel is not None:
                    sx, sy = self._ema(x + rel[0], y + rel[1])
                    self._move(sx, sy)

                rem = FRAME_INTERVAL - (time.time() - t0)
                if rem > 0:
                    time.sleep(rem)

        self._emitter.log.emit("[추적 정지]")
        self._emitter.stopped.emit()


# ── 메인 윈도우 ───────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("투명 도형 찾기 추적기")
        self.setMinimumWidth(420)
        self.setMinimumHeight(380)

        self._cfg     = load_config()
        self._roi     = self._cfg.get("roi")
        self._tracker = None
        self._thread  = None
        self._emitter = _Emitter()
        self._emitter.log.connect(self._append_log)
        self._emitter.stopped.connect(self._on_tracker_stopped)
        self._overlay = None

        self._build_ui()
        self._refresh_roi_label()

        # 전역 단축키 폴러 초기화
        self._poller = HotkeyPoller(self)
        self._poller.triggered.connect(self._on_hotkey)
        self._load_hotkeys()

    # ── UI 빌드 ──────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        layout.addWidget(self._build_roi_group())
        layout.addWidget(self._build_hotkey_group())
        layout.addWidget(self._build_control_group())
        layout.addWidget(self._build_log_group())

    def _build_roi_group(self):
        group = QGroupBox("게임판 영역")
        row = QHBoxLayout(group)

        self.lbl_roi = QLabel("미설정")
        self.lbl_roi.setStyleSheet("color: #ff6b6b;")
        btn_select = QPushButton("영역 선택")
        btn_select.setStyleSheet(BTN_ROI)
        btn_select.setFixedWidth(90)
        btn_select.clicked.connect(self._on_select_roi)

        row.addWidget(self.lbl_roi, stretch=1)
        row.addWidget(btn_select)
        return group

    def _build_hotkey_group(self):
        group = QGroupBox("단축키 설정  (클릭 후 원하는 키 입력 · ESC 취소)")
        layout = QVBoxLayout(group)

        # 시작 단축키 행
        start_row = QHBoxLayout()
        start_row.addWidget(QLabel("시작"))
        self.btn_hk_start = KeyCaptureButton(
            self._cfg.get("hotkey_start", DEFAULT_START_KEY)
        )
        self.btn_hk_start.setFixedWidth(80)
        self.btn_hk_start.key_captured.connect(self._on_hk_start_captured)
        start_row.addWidget(self.btn_hk_start)
        start_row.addSpacing(24)

        # 정지 단축키 행
        start_row.addWidget(QLabel("정지"))
        self.btn_hk_stop = KeyCaptureButton(
            self._cfg.get("hotkey_stop", DEFAULT_STOP_KEY)
        )
        self.btn_hk_stop.setFixedWidth(80)
        self.btn_hk_stop.key_captured.connect(self._on_hk_stop_captured)
        start_row.addWidget(self.btn_hk_stop)
        start_row.addStretch()

        self.lbl_hk_status = QLabel("")
        self.lbl_hk_status.setStyleSheet("color: gray; font-size: 11px;")
        layout.addLayout(start_row)
        layout.addWidget(self.lbl_hk_status)
        return group

    def _build_control_group(self):
        group = QGroupBox("추적 제어")
        row = QHBoxLayout(group)

        self.btn_start = QPushButton("▶ 추적 시작")
        self.btn_stop  = QPushButton("■ 정지")
        self.lbl_status = QLabel("대기 중")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_start.setStyleSheet(BTN_START)
        self.btn_stop.setStyleSheet(BTN_STOP)
        self.btn_start.setFixedHeight(36)
        self.btn_stop.setFixedHeight(36)
        self.btn_stop.setEnabled(False)

        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)

        row.addWidget(self.btn_start)
        row.addWidget(self.btn_stop)
        row.addWidget(self.lbl_status, stretch=1)
        return group

    def _build_log_group(self):
        group = QGroupBox("로그")
        v = QVBoxLayout(group)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(120)
        v.addWidget(self.log_box)
        return group

    # ── 단축키 로드 / 이벤트 ─────────────────────────────────────────
    def _load_hotkeys(self):
        sk = self._cfg.get("hotkey_start", DEFAULT_START_KEY)
        ek = self._cfg.get("hotkey_stop",  DEFAULT_STOP_KEY)
        self._poller.set_key("start", sk)
        self._poller.set_key("stop",  ek)
        self._update_hk_status(sk, ek)

    def _on_hk_start_captured(self, key: str):
        self._cfg["hotkey_start"] = key
        self._poller.set_key("start", key)
        save_config(self._cfg)
        self._update_hk_status(key, self.btn_hk_stop.current_key())
        self._append_log(f"시작 단축키 변경 → [{key.upper()}]")

    def _on_hk_stop_captured(self, key: str):
        self._cfg["hotkey_stop"] = key
        self._poller.set_key("stop", key)
        save_config(self._cfg)
        self._update_hk_status(self.btn_hk_start.current_key(), key)
        self._append_log(f"정지 단축키 변경 → [{key.upper()}]")

    def _update_hk_status(self, sk: str, ek: str):
        self.lbl_hk_status.setText(
            f"전역 단축키 활성  [{sk.upper()}] 시작  /  [{ek.upper()}] 정지"
        )

    def _on_hotkey(self, name: str):
        if name == "start":
            self._on_start()
        elif name == "stop":
            self._on_stop()

    # ── ROI 선택 ─────────────────────────────────────────────────────
    def _on_select_roi(self):
        self._append_log("화면을 클릭·드래그로 게임판 영역을 선택하세요 (ESC 취소)")
        self.showMinimized()
        QTimer.singleShot(300, self._show_overlay)

    def _show_overlay(self):
        self._overlay = RoiOverlay()
        self._overlay.roi_selected.connect(self._on_roi_selected)
        self._overlay.show()

    def _on_roi_selected(self, x, y, w, h):
        self._roi = {"x": x, "y": y, "w": w, "h": h}
        self._cfg["roi"] = self._roi
        save_config(self._cfg)
        self._refresh_roi_label()
        self._append_log(f"게임판 저장: X={x} Y={y} W={w} H={h}")
        self.showNormal()

    def _refresh_roi_label(self):
        if self._roi:
            r = self._roi
            self.lbl_roi.setText(f"X={r['x']}  Y={r['y']}  {r['w']}×{r['h']}")
            self.lbl_roi.setStyleSheet("color: #6bcb77;")
        else:
            self.lbl_roi.setText("미설정 — 영역 선택 버튼을 누르세요")
            self.lbl_roi.setStyleSheet("color: #ff6b6b;")

    # ── 추적 제어 ────────────────────────────────────────────────────
    def _on_start(self):
        if self._tracker and self._thread and self._thread.is_alive():
            return   # 이미 실행 중
        if not self._roi:
            self._append_log("⚠ 게임판 영역을 먼저 선택하세요.")
            return
        self._tracker = ShapeTracker(self._roi, self._emitter)
        self._thread  = threading.Thread(target=self._tracker.run, daemon=True)
        self._thread.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status.setText("추적 중 ●")
        self.lbl_status.setStyleSheet("color: #6bcb77; font-weight: bold;")

    def _on_stop(self):
        if self._tracker:
            self._tracker.stop()
        self.btn_stop.setEnabled(False)

    def _on_tracker_stopped(self):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("대기 중")
        self.lbl_status.setStyleSheet("color: #cccccc;")

    # ── 로그 ─────────────────────────────────────────────────────────
    def _append_log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.append(f"[{ts}] {msg}")
        self.log_box.moveCursor(self.log_box.textCursor().MoveOperation.End)

    def closeEvent(self, event):
        self._poller.stop()
        if self._tracker:
            self._tracker.stop()
        event.accept()


# ── 진입점 ───────────────────────────────────────────────────────────
def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    app = QApplication(sys.argv)
    app.setStyleSheet(DARK_STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
