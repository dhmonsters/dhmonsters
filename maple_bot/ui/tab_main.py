# 메인 탭 - 봇 시작/정지 제어 및 실시간 상태 로그
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QGroupBox, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject
from PyQt6.QtGui import QTextCursor

from ui.widgets import HotkeyCapture


class _StatusEmitter(QObject):
    """스레드에서 UI 스레드로 상태 메시지를 안전하게 전달하는 시그널 브릿지."""
    message = pyqtSignal(str)
    bot_stopped = pyqtSignal()   # 내부 정지 알림 (이탈 감지 등)


class TabMain(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._bot = None
        self._hk  = None
        self._pre_start_cb = None   # 봇 시작 직전 호출 (전 탭 자동 저장용)
        self._emitter = _StatusEmitter()
        self._emitter.message.connect(self._append_log)
        self._emitter.bot_stopped.connect(self._on_stop)

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_control_group())
        layout.addWidget(self._build_module_group())
        layout.addWidget(self._build_hotkey_group())
        layout.addWidget(self._build_log_group())

    # ── UI 빌드 ───────────────────────────────────────────────────────
    def _build_control_group(self):
        group = QGroupBox("봇 제어")
        row = QHBoxLayout(group)

        self.btn_start = QPushButton("▶ 시작")
        self.btn_stop  = QPushButton("■ 정지")
        self.lbl_status = QLabel("대기 중")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.btn_start.setFixedHeight(40)
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.setEnabled(False)

        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_stop.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")

        self.btn_start.clicked.connect(self._on_start)
        self.btn_stop.clicked.connect(self._on_stop)

        row.addWidget(self.btn_start)
        row.addWidget(self.btn_stop)
        row.addWidget(self.lbl_status)
        return group

    def _build_module_group(self):
        group = QGroupBox("모듈 활성화")
        row = QHBoxLayout(group)

        self.chk_attack      = QCheckBox("키(공격)")
        self.chk_move        = QCheckBox("좌표(움직임)")
        self.chk_potion      = QCheckBox("물약")
        self.chk_lie_notify  = QCheckBox("거탐 알림")
        self.chk_lie_solve   = QCheckBox("거탐 해제")

        self.chk_lie_notify.setToolTip("거짓말탐지기 발견 시 경보음 · 텔레그램 알림")
        self.chk_lie_solve.setToolTip("거짓말탐지기 발견 시 퍼즐 자동 해제")

        for chk in [self.chk_attack, self.chk_move, self.chk_potion,
                    self.chk_lie_notify, self.chk_lie_solve]:
            chk.setChecked(True)
            row.addWidget(chk)
        row.addStretch()
        return group

    def _build_hotkey_group(self):
        group = QGroupBox("단축키 설정")
        row = QHBoxLayout(group)

        row.addWidget(QLabel("시작"))
        self.btn_hk_start = HotkeyCapture("f1", self._apply_start_hotkey)
        row.addWidget(self.btn_hk_start)

        row.addSpacing(24)

        row.addWidget(QLabel("정지"))
        self.btn_hk_stop = HotkeyCapture("f2", self._apply_stop_hotkey)
        row.addWidget(self.btn_hk_stop)

        row.addSpacing(8)
        self.lbl_hk_status = QLabel("")
        row.addWidget(self.lbl_hk_status)

        row.addStretch()
        return group

    def _build_log_group(self):
        group = QGroupBox("상태 로그")
        layout = QVBoxLayout(group)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(300)
        layout.addWidget(self.log_view)

        btn_clear = QPushButton("로그 지우기")
        btn_clear.clicked.connect(self.log_view.clear)
        layout.addWidget(btn_clear)
        return group

    # ── 봇/단축키 주입 ───────────────────────────────────────────────
    def set_bot(self, bot) -> None:
        self._bot = bot

    def set_hotkey_manager(self, hk) -> None:
        self._hk = hk
        start_key = self.btn_hk_start.current_key()
        stop_key  = self.btn_hk_stop.current_key()
        if start_key:
            self._apply_start_hotkey(start_key)
        if stop_key:
            self._apply_stop_hotkey(stop_key)

    # ── 단축키 적용 ───────────────────────────────────────────────────
    def _apply_start_hotkey(self, key: str) -> None:
        if not self._hk:
            return
        err = self._hk.register("bot_start", key, self._on_start)
        self.lbl_hk_status.setText("등록됨" if not err else f"오류: {err}")
        self.config.set("hotkeys", "start", key)

    def _apply_stop_hotkey(self, key: str) -> None:
        if not self._hk:
            return
        err = self._hk.register("bot_stop", key, self._on_stop)
        self.lbl_hk_status.setText("등록됨" if not err else f"오류: {err}")
        self.config.set("hotkeys", "stop", key)

    def set_pre_start_callback(self, cb) -> None:
        """봇 시작 직전에 호출할 콜백 등록 (main_window에서 전 탭 저장 함수를 주입)."""
        self._pre_start_cb = cb

    # ── 버튼 핸들러 ───────────────────────────────────────────────────
    def _on_start(self) -> None:
        if self._bot is None or self._bot.is_running:
            return
        # 봇 시작 전 모든 탭 설정을 config에 반영
        if self._pre_start_cb:
            self._pre_start_cb()
        self._bot.set_modules(
            attack=self.chk_attack.isChecked(),
            move=self.chk_move.isChecked(),
            potion=self.chk_potion.isChecked(),
            lie_notify=self.chk_lie_notify.isChecked(),
            lie_solve=self.chk_lie_solve.isChecked(),
        )
        self._bot.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.lbl_status.setText("실행 중 🟢")
        # 단축키가 게임창에 전달되어 축소되는 경우 방지 — 300ms 후 게임창 포커스 복귀
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(300, self._refocus_game)

    def _refocus_game(self) -> None:
        """봇 시작 후 게임 창 포커스를 복귀한다."""
        try:
            import win32gui, win32con
            title = (self._bot._config.get("settings2", "game_window_title")
                     or "MapleStory") if self._bot else "MapleStory"
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                if win32gui.IsIconic(hwnd):   # 최소화된 경우에만 복원
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def _on_stop(self) -> None:
        if self._bot is None:
            return
        if self._bot.is_running:
            self._bot.stop()
        # 봇 스레드가 예외로 죽었어도 항상 UI 상태는 정지로 초기화
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lbl_status.setText("정지됨 🔴")

    # ── 상태 메시지 수신 (스레드 세이프) ─────────────────────────────
    def emit_status(self, msg: str) -> None:
        self._emitter.message.emit(msg)

    def on_bot_stopped(self) -> None:
        """봇이 내부적으로 정지될 때 호출 (별도 스레드 → 시그널로 UI 업데이트)."""
        self._emitter.bot_stopped.emit()

    def _append_log(self, msg: str) -> None:
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"[{timestamp}] {msg}")
        self.log_view.moveCursor(QTextCursor.MoveOperation.End)

    # ── 설정 저장/로드 ────────────────────────────────────────────────
    def save_to_config(self):
        self.config.set("hotkeys", "start", self.btn_hk_start.current_key())
        self.config.set("hotkeys", "stop",  self.btn_hk_stop.current_key())
        self.config.set("modules", "attack",      self.chk_attack.isChecked())
        self.config.set("modules", "move",        self.chk_move.isChecked())
        self.config.set("modules", "potion",      self.chk_potion.isChecked())
        self.config.set("modules", "lie_notify",  self.chk_lie_notify.isChecked())
        self.config.set("modules", "lie_solve",   self.chk_lie_solve.isChecked())

    def load_from_config(self):
        hk = self.config.get("hotkeys") or {}
        self.btn_hk_start.set_key(hk.get("start", "f1"))
        self.btn_hk_stop.set_key(hk.get("stop",  "f2"))
        mod = self.config.get("modules") or {}
        self.chk_attack.setChecked(mod.get("attack",     True))
        self.chk_move.setChecked(mod.get("move",         True))
        self.chk_potion.setChecked(mod.get("potion",     True))
        self.chk_lie_notify.setChecked(mod.get("lie_notify", True))
        self.chk_lie_solve.setChecked(mod.get("lie_solve",   True))
