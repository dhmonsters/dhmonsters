# MainShell — 6카테고리 셸. 상단 가로 내비 + 중앙 스택 + 하단 컨트롤바 (Discord Night)
from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QStackedWidget, QLabel, QTextEdit, QButtonGroup, QSplitter,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap

from core_ui.theme import build_qss, SPACING
from core_ui.branding import claude_icon

# 6 카테고리 (아이콘 + 이름)
CATEGORIES = [
    ("연결·인식", "게임연결·미니맵·사냥영역·닉네임·몬스터감지"),
    ("동선·이동", "구역·사다리·다운점프·텔포·포탈·블록빌더·녹화·프리셋"),
    ("전투", "공격·버프·물약·펫·줍기"),
    ("안전·안티밴", "거탐·방지몹·유저감지·자동응답·채널변경·인간화강도"),
    ("자동화·운영", "자동판매·마을귀환·예약종료·레벨정지·텔레그램·찰리중사"),
    ("시스템", "라이선스·업데이트·저사양/원격·입력백엔드·YOLO캡처"),
]
_ICONS = ["🔌", "🧭", "⚔️", "🛡️", "⚙️", "🖥️"]

# 로그 카테고리 — 칩으로 켜고 끔(표시 필터). 봇 동작을 종류별로 구분
LOG_CATEGORIES = ["이동", "공격", "버프", "물약", "펫·줍기", "감지", "시스템"]


def _read_version() -> str:
    if getattr(sys, "frozen", False):
        bases = [Path(sys.executable).parent]
        if getattr(sys, "_MEIPASS", None):
            bases.append(Path(sys._MEIPASS))
    else:
        bases = [Path(__file__).resolve().parent.parent]
    for base in bases:
        try:
            return (base / "version.txt").read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return "?"


class MainShell(QMainWindow):
    log_requested = pyqtSignal(str, str)
    settings_apply_requested = pyqtSignal()

    """통합 봇 메인 셸. 상단 내비 탭 + 중앙 페이지 스택 + 하단 컨트롤바(시작/정지·상태·로그)."""

    def __init__(self, config=None):
        super().__init__()
        self._config = config
        self.setWindowTitle(f"Claude v{_read_version()}")
        self.setWindowIcon(claude_icon())
        self.resize(1180, 760)
        self.setMinimumSize(760, 560)
        self.setStyleSheet(build_qss())

        self.nav_buttons: list[QPushButton] = []
        self.stack = QStackedWidget()

        root = QWidget()
        root_v = QVBoxLayout(root)
        root_v.setContentsMargins(0, 0, 0, 0)
        root_v.setSpacing(0)
        root_v.addWidget(self._build_topnav(), 0)
        # 중앙 스택 + 로그 드로어를 세로 스플리터로 → 경계 드래그로 로그창 높이 조절
        self._vsplit = QSplitter(Qt.Orientation.Vertical)
        self._vsplit.setObjectName("vsplit")
        self._vsplit.addWidget(self.stack)
        self._vsplit.addWidget(self._build_log_drawer())
        self._vsplit.setStretchFactor(0, 1)
        self._vsplit.setStretchFactor(1, 0)
        self._vsplit.setCollapsible(0, False)
        self._vsplit.setHandleWidth(8)   # 로그창 크기조절 핸들 — 잡기 쉽게
        root_v.addWidget(self._vsplit, 1)
        root_v.addWidget(self._build_controlbar(), 0)
        self.setCentralWidget(root)

        if config is not None:
            from core_ui.pages import build_pages
            for page in build_pages(config):
                self.stack.addWidget(page)
        else:
            for name, desc in CATEGORIES:
                self.stack.addWidget(self._build_page(name, desc))
        self.nav_buttons[0].setChecked(True)
        self.stack.setCurrentIndex(0)
        self._bind_hotkeys()

    # ── 상단 가로 내비 ────────────────────────────────────────────────
    def _build_topnav(self) -> QWidget:
        bar = QWidget(); bar.setObjectName("topnav"); bar.setFixedHeight(54)
        h = QHBoxLayout(bar)
        h.setContentsMargins(SPACING["md"], SPACING["xs"], SPACING["md"], SPACING["xs"])
        h.setSpacing(SPACING["xxs"])

        logo_mark = QLabel()
        logo_mark.setPixmap(claude_icon().pixmap(22, 22))
        logo_mark.setObjectName("logoMark")
        h.addWidget(logo_mark)
        logo = QLabel(f"Claude v{_read_version()}"); logo.setObjectName("logo")
        h.addWidget(logo)
        h.addSpacing(SPACING["sm"])

        group = QButtonGroup(self); group.setExclusive(True)
        for i, (name, _desc) in enumerate(CATEGORIES):
            b = QPushButton(f"{_ICONS[i]} {name}")
            b.setObjectName("navtab"); b.setCheckable(True)
            b.clicked.connect(lambda _=False, idx=i: self._switch(idx))
            group.addButton(b); self.nav_buttons.append(b)
            h.addWidget(b)

        h.addStretch(1)
        self.status_chip = QLabel("● 정지"); self.status_chip.setObjectName("statusChip")
        self.status_chip.setStyleSheet("color:#80848e; background:transparent;")   # 기본 정지(회색)
        h.addWidget(self.status_chip)
        return bar

    def _save_all_settings(self) -> None:
        if self._config is not None:
            self._config.save()
        self.settings_apply_requested.emit()
        self.set_status("전체 설정 저장 및 적용 완료")

    # ── 로그 드로어 (기본 숨김, 컨트롤바 버튼으로 토글) ──────────────
    def _build_log_drawer(self) -> QWidget:
        self._log_drawer = QWidget()
        v = QVBoxLayout(self._log_drawer)
        v.setContentsMargins(SPACING["md"], SPACING["xs"], SPACING["md"], 0)
        # 카테고리 필터 칩 (켜진 것만 로그에 표시) — 클릭으로 추가/제외
        self._log_buffer: list[tuple] = []          # (cat, msg) 전체 보관(필터 토글 시 재렌더)
        self._log_pending: list[tuple[str, str]] = []
        self._log_cats_on = set(LOG_CATEGORIES)      # 켜진 카테고리(기본 전부)
        self.log_requested.connect(self._queue_log)
        self._log_flush_timer = QTimer(self)
        self._log_flush_timer.timeout.connect(self._flush_logs)
        self._log_flush_timer.start(100)
        self._cat_btns: dict[str, QPushButton] = {}
        chips = QWidget(); ch = QHBoxLayout(chips)
        ch.setContentsMargins(0, 0, 0, SPACING["xxs"]); ch.setSpacing(SPACING["xxs"])
        ch.addWidget(QLabel("로그:"))
        for cat in LOG_CATEGORIES:
            b = QPushButton(cat); b.setObjectName("navtab"); b.setCheckable(True)
            b.setChecked(True)
            b.clicked.connect(lambda _=False, c=cat: self._toggle_log_cat(c))
            self._cat_btns[cat] = b; ch.addWidget(b)
        ch.addStretch(1)
        v.addWidget(chips)
        self.log_view = QTextEdit(); self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(80)   # 스플리터 드래그로 자유 조절(고정 높이 제거)
        # 새 로그가 쌓이면 항상 맨 아래로 따라가게 — append 직후엔 maximum이 아직 안 커져
        # 한 줄 모자라게 멈추므로, 스크롤 범위가 바뀌는 순간(rangeChanged)에 맨 아래로 내린다.
        self.log_view.verticalScrollBar().rangeChanged.connect(
            lambda _min, _max: self.log_view.verticalScrollBar().setValue(_max)
        )
        v.addWidget(self.log_view)
        self._log_drawer.setVisible(False)
        return self._log_drawer

    def _toggle_log_cat(self, cat: str) -> None:
        """카테고리 표시 토글 → 버퍼에서 켜진 카테고리만 재렌더."""
        if cat in self._log_cats_on:
            self._log_cats_on.discard(cat)
        else:
            self._log_cats_on.add(cat)
        self.log_view.clear()
        for c, m in self._log_buffer:
            if c in self._log_cats_on:
                self.log_view.append(f"[{c}] {m}")

    def _toggle_log(self) -> None:
        self._log_drawer.setVisible(not self._log_drawer.isVisible())

    # ── 하단 컨트롤바 ─────────────────────────────────────────────────
    def _build_controlbar(self) -> QWidget:
        bar = QWidget(); bar.setObjectName("controlbar"); bar.setFixedHeight(66)
        h = QHBoxLayout(bar)
        h.setContentsMargins(SPACING["md"], SPACING["xs"], SPACING["md"], SPACING["xs"])
        h.setSpacing(SPACING["xs"])

        self.btn_start = QPushButton("▶  시작  (F1)"); self.btn_start.setObjectName("startBtn")
        self.btn_stop = QPushButton("■  정지  (F2)"); self.btn_stop.setObjectName("stopBtn")
        h.addWidget(self.btn_start)
        h.addWidget(self.btn_stop)
        h.addStretch(1)

        log_btn = QPushButton("로그"); log_btn.setObjectName("navtab"); log_btn.setMinimumWidth(56)
        log_btn.clicked.connect(self._toggle_log)
        h.addWidget(log_btn)

        # HP/MP 실시간 미리보기 (config 있을 때만, 실패 시 생략)
        if self._config is not None:
            try:
                from core.detector import Detector
                from core.screen_reader import ScreenReader
                from core_ui.gauge_preview import GaugePreview
                h.addWidget(GaugePreview(Detector(ScreenReader(), self._config), compact=True),
                            0, Qt.AlignmentFlag.AlignVCenter)
            except Exception:
                pass
        self.global_save_button = QPushButton("전체 설정 저장 및 적용")
        self.global_save_button.setObjectName("primaryButton")
        self.global_save_button.setToolTip("현재 설정을 저장하고 실행 중인 봇에 다시 적용합니다.")
        self.global_save_button.clicked.connect(self._save_all_settings)
        h.addWidget(self.global_save_button)
        return bar

    # ── 단축키 (전역: 게임 포커스 중에도 동작) ────────────────────────
    def _bind_hotkeys(self) -> None:
        start_key, stop_key = "f1", "f2"
        if self._config is not None:
            start_key = str(self._config.get("hotkeys", "start", default="f1")).lower()
            stop_key = str(self._config.get("hotkeys", "stop", default="f2")).lower()
        # QShortcut은 앱 포커스 때만 동작 → GetAsyncKeyState 폴링(HotkeyManager)으로 전역화
        try:
            from core.hotkey_manager import HotkeyManager
            self._hotkey_mgr = HotkeyManager(self)
            self._hotkey_mgr.register("start", start_key, self.btn_start.click)
            self._hotkey_mgr.register("stop", stop_key, self.btn_stop.click)
        except Exception:
            # win32 미가용 등 폴백 — 앱 포커스 단축키라도 건다
            from PyQt6.QtGui import QShortcut, QKeySequence
            QShortcut(QKeySequence(start_key.upper()), self, activated=self.btn_start.click)
            QShortcut(QKeySequence(stop_key.upper()), self, activated=self.btn_stop.click)
        self.btn_start.setText(f"▶  시작  ({start_key.upper()})")
        self.btn_stop.setText(f"■  정지  ({stop_key.upper()})")

    # ── 플레이스홀더 페이지 (config 없을 때) ──────────────────────────
    def _build_page(self, name: str, desc: str) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(SPACING["xl"], SPACING["xl"], SPACING["xl"], SPACING["xl"])
        v.setSpacing(SPACING["sm"])
        h = QLabel(name); h.setObjectName("h1")
        sub = QLabel(desc); sub.setObjectName("subtle"); sub.setWordWrap(True)
        v.addWidget(h); v.addWidget(sub); v.addStretch(1)
        return page

    # ── 동작 ──────────────────────────────────────────────────────────
    def _switch(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)

    def set_status(self, text: str, running: bool = False) -> None:
        """상단 상태 칩 갱신 (사냥중=네온그린 / 정지=회색)."""
        self.status_chip.setText(f"● {text}")
        self.status_chip.setStyleSheet(
            ("color:#3ada85;" if running else "color:#80848e;") + " background:transparent;")

    def append_log(self, msg: str, cat: str = "시스템") -> None:
        """카테고리 태그와 함께 로그 적재. 켜진 카테고리만 화면에 표시(전체는 버퍼 보관)."""
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.log_requested.emit(f"[{timestamp}] {msg}", str(cat))

    def _queue_log(self, msg: str, cat: str) -> None:
        if cat not in LOG_CATEGORIES:
            cat = "시스템"
        self._log_pending.append((cat, msg))

    def _flush_logs(self) -> None:
        if not self._log_pending:
            return
        pending, self._log_pending = self._log_pending, []
        self._log_buffer.extend(pending)
        if len(self._log_buffer) > 1000:        # 버퍼 상한(메모리)
            self._log_buffer = self._log_buffer[-1000:]
        visible = [f"[{cat}] {msg}" for cat, msg in pending if cat in self._log_cats_on]
        if visible:
            self.log_view.append("\n".join(visible))
