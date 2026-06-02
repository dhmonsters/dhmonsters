# MainShell — 6카테고리 셸. 상단 가로 내비 + 중앙 스택 + 하단 컨트롤바 (Discord Night)
from __future__ import annotations

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QStackedWidget, QLabel, QTextEdit, QButtonGroup,
)
from PyQt6.QtCore import Qt

from core_ui.theme import build_qss, SPACING

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


class MainShell(QMainWindow):
    """통합 봇 메인 셸. 상단 내비 탭 + 중앙 페이지 스택 + 하단 컨트롤바(시작/정지·상태·로그)."""

    def __init__(self, config=None):
        super().__init__()
        self._config = config
        self.setWindowTitle("DHMONSTERS")
        self.resize(1180, 760)
        self.setMinimumSize(1024, 640)
        self.setStyleSheet(build_qss())

        self.nav_buttons: list[QPushButton] = []
        self.stack = QStackedWidget()

        root = QWidget()
        root_v = QVBoxLayout(root)
        root_v.setContentsMargins(0, 0, 0, 0)
        root_v.setSpacing(0)
        root_v.addWidget(self._build_topnav(), 0)
        root_v.addWidget(self.stack, 1)
        root_v.addWidget(self._build_log_drawer(), 0)
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

        logo = QLabel("● DHMONSTERS"); logo.setObjectName("logo")
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

    # ── 로그 드로어 (기본 숨김, 컨트롤바 버튼으로 토글) ──────────────
    def _build_log_drawer(self) -> QWidget:
        self._log_drawer = QWidget()
        v = QVBoxLayout(self._log_drawer)
        v.setContentsMargins(SPACING["md"], SPACING["xs"], SPACING["md"], 0)
        self.log_view = QTextEdit(); self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True); self.log_view.setFixedHeight(120)
        v.addWidget(self.log_view)
        self._log_drawer.setVisible(False)
        return self._log_drawer

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

        log_btn = QPushButton("🗎  로그"); log_btn.setObjectName("navtab")
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
        return bar

    # ── 단축키 ────────────────────────────────────────────────────────
    def _bind_hotkeys(self) -> None:
        from PyQt6.QtGui import QShortcut, QKeySequence
        start_key, stop_key = "F1", "F2"
        if self._config is not None:
            start_key = str(self._config.get("hotkeys", "start", default="f1")).upper()
            stop_key = str(self._config.get("hotkeys", "stop", default="f2")).upper()
        QShortcut(QKeySequence(start_key), self, activated=self.btn_start.click)
        QShortcut(QKeySequence(stop_key), self, activated=self.btn_stop.click)
        self.btn_start.setText(f"▶  시작  ({start_key})")
        self.btn_stop.setText(f"■  정지  ({stop_key})")

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

    def append_log(self, msg: str) -> None:
        self.log_view.append(msg)
