# MainShell — 6카테고리 셸. 좌측 내비 + 중앙 스택 + 좌하단 시작/정지 + 우측 로그도크 (도면 4단계)
from __future__ import annotations

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QStackedWidget, QLabel, QTextEdit, QButtonGroup,
)
from PyQt6.QtCore import Qt

from core_ui.theme import build_qss

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
    """통합 봇의 메인 셸. 페이지 내용은 플레이스홀더(실연결은 통합단계)."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DHMONSTERS")
        self.resize(1100, 680)
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

        # 카테고리 페이지(플레이스홀더)
        for name, desc in CATEGORIES:
            self.stack.addWidget(self._build_page(name, desc))
        self.nav_buttons[0].setChecked(True)
        self.stack.setCurrentIndex(0)

    # ── 좌측 사이드바: 6 내비 + 시작/정지 ────────────────────────────
    def _build_sidebar(self) -> QWidget:
        from core_ui.theme import TOKENS
        bar = QWidget()
        bar.setFixedWidth(220)
        # House Green 딥그린 배경 — 흰 nav 글씨 대비 (Starbucks 색블록 리듬)
        bar.setStyleSheet(f"background-color: {TOKENS['house_green']};")
        v = QVBoxLayout(bar)
        v.setContentsMargins(10, 14, 10, 14)
        v.setSpacing(4)

        title = QLabel("DHMONSTERS")
        title.setStyleSheet("color: #ffffff; font-size: 20px; font-weight: 700;")
        v.addWidget(title)
        v.addSpacing(12)

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
        self.btn_start = QPushButton("▶ 시작 (F1)")
        self.btn_start.setObjectName("primary")
        self.btn_stop = QPushButton("■ 정지")
        v.addWidget(self.btn_start)
        v.addWidget(self.btn_stop)
        return bar

    # ── 우측 로그 도크 ────────────────────────────────────────────────
    def _build_log_dock(self) -> QWidget:
        dock = QWidget()
        dock.setFixedWidth(300)
        v = QVBoxLayout(dock)
        v.setContentsMargins(8, 14, 10, 14)
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
        v.setContentsMargins(20, 20, 20, 20)
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
