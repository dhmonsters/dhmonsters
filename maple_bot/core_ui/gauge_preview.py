# HP/MP 실시간 % 미리보기 — A Detector의 고정 상대좌표로 게이지를 읽어 색상 바로 표시.
# 창 위치/크기가 바뀌어도 비율 기반이라 동일하게 인식. 사용자는 % 실시간 확인만 한다.
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
)
from PyQt6.QtCore import QTimer


class GaugePreview(QWidget):
    """detector.hp_ratio()/mp_ratio()를 주기적으로 읽어 HP/MP %를 색상 바로 표시."""

    def __init__(self, detector, interval_ms: int = 700):
        super().__init__()
        self._d = detector
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 4, 0, 4)
        v.setSpacing(4)
        cap = QLabel("HP/MP 실시간 인식 (게임 실행 중 자동 표시)")
        cap.setObjectName("subtle")
        v.addWidget(cap)

        self.hp_lbl, self.hp_bar = self._make_row(v, "HP", "#f04452")
        self.mp_lbl, self.mp_bar = self._make_row(v, "MP", "#4d7cff")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(interval_ms)
        self._refresh()

    def _make_row(self, parent_layout, name: str, color: str):
        row = QHBoxLayout(); row.setSpacing(8)
        lbl = QLabel(f"{name} --%"); lbl.setFixedWidth(70)
        bar = QProgressBar(); bar.setRange(0, 100); bar.setTextVisible(False)
        bar.setFixedHeight(14)
        bar.setStyleSheet(
            "QProgressBar{background:#1a1b1d;border:1px solid #23252a;border-radius:6px;}"
            f"QProgressBar::chunk{{background:{color};border-radius:5px;}}")
        row.addWidget(lbl); row.addWidget(bar)
        w = QWidget(); w.setLayout(row)
        parent_layout.addWidget(w)
        return lbl, bar

    def _refresh(self) -> None:
        try:
            hp = max(0, min(100, int(round(self._d.hp_ratio() * 100))))
            mp = max(0, min(100, int(round(self._d.mp_ratio() * 100))))
        except Exception:
            return
        self.hp_lbl.setText(f"HP {hp}%"); self.hp_bar.setValue(hp)
        self.mp_lbl.setText(f"MP {mp}%"); self.mp_bar.setValue(mp)
