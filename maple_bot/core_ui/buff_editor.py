# BuffEditor — 버프 목록(attack.normal_buffs) 편집기. 각 행: 사용/키/간격(초). config 양방향 저장
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QLineEdit, QSpinBox, QFrame,
)

from core_ui.theme import SPACING


class BuffEditor(QWidget):
    """attack.normal_buffs 리스트를 행 단위로 편집(사용 체크 + 키 + 간격초). 추가/삭제 즉시 저장."""

    def __init__(self, config, keys: tuple = ("attack", "normal_buffs")):
        super().__init__()
        self._cfg = config
        self._keys = keys
        self._buffs: list[dict] = list(config.get(*keys, default=[]) or [])

        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(0, 0, 0, 0)
        self._v.setSpacing(SPACING["xxs"])

        head = QHBoxLayout()
        head.addWidget(QLabel("버프 (사용 / 키 / 간격초)"))
        add = QPushButton("+ 버프 추가"); add.setFixedWidth(96)
        add.clicked.connect(self.add_buff)
        head.addStretch(); head.addWidget(add)
        self._v.addLayout(head)

        self._rows = QVBoxLayout(); self._rows.setSpacing(SPACING["xxs"])
        self._v.addLayout(self._rows)
        self._render()

    # ── API ───────────────────────────────────────────────────────────
    def row_count(self) -> int:
        return len(self._buffs)

    def add_buff(self) -> None:
        self._buffs.append({"enabled": True, "key": "", "interval_sec": 60})
        self._save_render()

    def remove_row(self, idx: int) -> None:
        if 0 <= idx < len(self._buffs):
            self._buffs.pop(idx)
            self._save_render()

    def set_field(self, idx: int, field: str, value) -> None:
        if 0 <= idx < len(self._buffs):
            self._buffs[idx][field] = value
            self._save()

    # ── 내부 ──────────────────────────────────────────────────────────
    def _save(self) -> None:
        self._cfg.set(*self._keys, self._buffs)
        self._cfg.save()

    def _save_render(self) -> None:
        self._save(); self._render()

    def _render(self) -> None:
        while self._rows.count():
            it = self._rows.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        for i, b in enumerate(self._buffs):
            self._rows.addWidget(self._build_row(i, b))

    def _build_row(self, idx: int, b: dict) -> QWidget:
        row = QFrame(); row.setObjectName("card")
        h = QHBoxLayout(row)
        h.setContentsMargins(SPACING["sm"], SPACING["xxs"], SPACING["sm"], SPACING["xxs"])
        h.setSpacing(SPACING["xs"])

        cb = QCheckBox("사용"); cb.setChecked(bool(b.get("enabled", True)))
        cb.toggled.connect(lambda v, i=idx: self.set_field(i, "enabled", bool(v)))
        h.addWidget(cb)

        key = QLineEdit(b.get("key", "")); key.setPlaceholderText("버프키"); key.setFixedWidth(90)
        key.textChanged.connect(lambda v, i=idx: self.set_field(i, "key", v))
        h.addWidget(key)

        iv = QSpinBox(); iv.setRange(1, 3600); iv.setSuffix(" 초"); iv.setFixedWidth(90)
        iv.setValue(int(b.get("interval_sec", 60)))
        iv.valueChanged.connect(lambda v, i=idx: self.set_field(i, "interval_sec", v))
        h.addWidget(iv)

        h.addStretch()
        rm = QPushButton("✕"); rm.setFixedWidth(28)
        rm.clicked.connect(lambda _=False, i=idx: self.remove_row(i))
        h.addWidget(rm)
        return row
