# HP/MP 실시간 % 미리보기 — A Detector의 고정 상대좌표로 게이지를 읽어 색상 바로 표시.
# 창 위치/크기가 바뀌어도 비율 기반이라 동일하게 인식. 이름·바·% 분리로 깔끔하게.
from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import QTimer


class GaugePreview(QWidget):
    """detector.hp_ratio()/mp_ratio()를 주기적으로 읽어 HP/MP %를 색상 바로 표시.
    compact=True면 하단 컨트롤바용 작은 크기."""

    def __init__(self, detector, interval_ms: int = 700, compact: bool = False):
        super().__init__()
        self._d = detector
        self._barw = 120 if compact else 170
        v = QVBoxLayout(self)
        if compact:
            v.setContentsMargins(0, 0, 0, 0); v.setSpacing(3)
            self.setFixedWidth(self._barw + 70)
            self.setFixedHeight(38)
        else:
            v.setContentsMargins(0, 4, 0, 4); v.setSpacing(5)
            cap = QLabel("HP/MP 실시간 인식 (게임 실행 중 자동 표시)")
            cap.setObjectName("subtle")
            v.addWidget(cap)

        self.hp_pct, self.hp_bar = self._make_row(v, "HP", "#f23f43")
        self.mp_pct, self.mp_bar = self._make_row(v, "MP", "#4d7cff")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(interval_ms)
        self._refresh()

    def _make_row(self, parent_layout, name: str, color: str):
        row = QHBoxLayout(); row.setSpacing(6); row.setContentsMargins(0, 0, 0, 0)
        name_lbl = QLabel(name); name_lbl.setFixedWidth(22)
        name_lbl.setStyleSheet(f"color:{color}; background:transparent; font-weight:600;")
        bar = QProgressBar(); bar.setRange(0, 100); bar.setTextVisible(False)
        bar.setFixedHeight(10); bar.setMinimumWidth(self._barw)
        bar.setStyleSheet(
            "QProgressBar{background:#15161a;border:none;border-radius:5px;}"
            f"QProgressBar::chunk{{background:{color};border-radius:5px;}}")
        pct = QLabel("--%"); pct.setFixedWidth(38)
        pct.setStyleSheet("background:transparent; color:#b5bac1;")
        row.addWidget(name_lbl); row.addWidget(bar); row.addWidget(pct)
        w = QWidget(); w.setLayout(row)
        parent_layout.addWidget(w)
        return pct, bar

    def _refresh(self) -> None:
        try:
            hp = max(0, min(100, int(round(self._d.hp_ratio() * 100))))
            mp = max(0, min(100, int(round(self._d.mp_ratio() * 100))))
        except Exception:
            return
        self.hp_pct.setText(f"{hp}%"); self.hp_bar.setValue(hp)
        self.mp_pct.setText(f"{mp}%"); self.mp_bar.setValue(mp)
