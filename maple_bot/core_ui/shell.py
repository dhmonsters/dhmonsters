# MainShell — 6카테고리 셸. 좌측 내비 + 중앙 스택 + 우측 로그도크 (도면 4단계, DESIGN.md Linear 토큰)
from __future__ import annotations

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QStackedWidget, QLabel, QTextEdit, QButtonGroup, QFrame,
)
from PyQt6.QtCore import Qt

from core_ui.theme import build_qss, TOKENS, SPACING

# 6 카테고리 (도면 4단계)
CATEGORIES = [
    ("연결·인식", "게임연결·미니맵·사냥영역·닉네임·몬스터감지"),
    ("동선·이동", "구역·사다리·다운점프·텔포·포탈·블록빌더·녹화·프리셋"),
    ("전투", "공격·버프·물약·펫·줍기"),
    ("안전·안티밴", "거탐·방지몹·유저감지·자동응답·채널변경·인간화강도"),
    ("자동화·운영", "자동판매·마을귀환·예약종료·레벨정지·텔레그램·찰리중사"),
    ("시스템", "라이선스·업데이트·저사양/원격·입력백엔드·YOLO캡처"),
]


class MainShell(QMainWindow):
    """통합 봇의 메인 셸. 페이지 내용은 플레이스홀더(실연결은 통합단계).
    레이아웃·간격은 DESIGN.md(Linear) spacing 토큰을 따른다."""

    def __init__(self, config=None):
        super().__init__()
        self._config = config
        self.setWindowTitle("DHMONSTERS")
        self.resize(1180, 720)
        self.setMinimumSize(1024, 640)   # 이보다 작아지면 중앙 내용이 잘리므로 하한
        self.setStyleSheet(build_qss())

        self.nav_buttons: list[QPushButton] = []
        self.stack = QStackedWidget()

        root = QWidget()
        root_l = QHBoxLayout(root)
        root_l.setContentsMargins(0, 0, 0, 0)
        root_l.setSpacing(0)

        root_l.addWidget(self._build_sidebar(), 0)
        root_l.addWidget(self.stack, 1)
        root_l.addWidget(self._build_log_dock(), 0)
        self.setCentralWidget(root)

        # config 있으면 실제 설정 페이지, 없으면 플레이스홀더(테스트 호환)
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

    def _bind_hotkeys(self) -> None:
        """전역 단축키: 시작/정지 (config hotkeys, 기본 F1/F2)."""
        from PyQt6.QtGui import QShortcut, QKeySequence
        start_key = "F1"
        stop_key = "F2"
        if self._config is not None:
            start_key = str(self._config.get("hotkeys", "start", default="f1")).upper()
            stop_key = str(self._config.get("hotkeys", "stop", default="f2")).upper()
        QShortcut(QKeySequence(start_key), self, activated=self.btn_start.click)
        QShortcut(QKeySequence(stop_key), self, activated=self.btn_stop.click)
        self.btn_start.setText(f"▶  시작  ({start_key})")
        self.btn_stop.setText(f"■  정지  ({stop_key})")

    # ── 좌측 사이드바: 6 내비 + 시작/정지 ────────────────────────────
    def _build_sidebar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("card")          # surface_1 차콜 패널 + hairline
        bar.setMinimumWidth(208)           # 고정 대신 약간 유연 (창 리사이즈 반응)
        bar.setMaximumWidth(248)
        v = QVBoxLayout(bar)
        v.setContentsMargins(SPACING["sm"], SPACING["lg"], SPACING["sm"], SPACING["lg"])
        v.setSpacing(SPACING["xxs"])

        title = QLabel("DHMONSTERS")
        title.setObjectName("h1")
        v.addWidget(title)
        v.addSpacing(SPACING["md"])

        group = QButtonGroup(self)
        group.setExclusive(True)
        for i, (name, _desc) in enumerate(CATEGORIES):
            b = QPushButton(name)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, idx=i: self._switch(idx))
            group.addButton(b)
            self.nav_buttons.append(b)
            v.addWidget(b)

        v.addStretch(1)
        self.btn_start = QPushButton("▶  시작  (F1)")
        self.btn_start.setObjectName("primary")
        self.btn_stop = QPushButton("■  정지")
        v.addWidget(self.btn_start)
        v.addSpacing(SPACING["xxs"])
        v.addWidget(self.btn_stop)
        return bar

    # ── 우측 로그 도크 ────────────────────────────────────────────────
    def _build_log_dock(self) -> QWidget:
        dock = QWidget()
        dock.setMinimumWidth(220)          # 고정 대신 유연 — 창 줄이면 로그도크도 함께 양보
        dock.setMaximumWidth(380)
        v = QVBoxLayout(dock)
        v.setContentsMargins(SPACING["xs"], SPACING["lg"], SPACING["md"], SPACING["lg"])
        v.setSpacing(SPACING["sm"])
        lbl = QLabel("실시간 로그")
        lbl.setObjectName("subtle")
        v.addWidget(lbl)
        self.log_view = QTextEdit()
        self.log_view.setObjectName("log")
        self.log_view.setReadOnly(True)
        v.addWidget(self.log_view)
        return dock

    def _build_page(self, name: str, desc: str) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(SPACING["xl"], SPACING["xl"], SPACING["xl"], SPACING["xl"])
        v.setSpacing(SPACING["sm"])
        h = QLabel(name)
        h.setObjectName("h1")
        sub = QLabel(desc)
        sub.setObjectName("subtle")
        sub.setWordWrap(True)
        v.addWidget(h)
        v.addWidget(sub)
        v.addStretch(1)
        return page

    # ── 동작 ──────────────────────────────────────────────────────────
    def _switch(self, idx: int) -> None:
        self.stack.setCurrentIndex(idx)

    def append_log(self, msg: str) -> None:
        self.log_view.append(msg)
