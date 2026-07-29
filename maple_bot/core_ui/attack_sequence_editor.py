# 전투 탭에서 공격 연속기 순서와 입력 시간을 편집한다.
from __future__ import annotations

from copy import deepcopy

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core_ui.theme import SPACING


class AttackSequenceEditor(QFrame):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._cfg = config
        self.setObjectName("attackSequenceEditor")
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._sequences = deepcopy(config.get("attack", "sequences", default=[]) or [])
        if not self._sequences:
            self._sequences = [{
                "enabled": True,
                "name": "기본 공격",
                "keys": [str(config.get("attack", "key", default="ctrl") or "ctrl")],
                "key_hold_sec": [0.05],
                "key_interval_sec": 0.15,
                "repeat_interval_sec": float(
                    config.get("attack", "delay_sec", default=0.4) or 0.4
                ),
            }]
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"])
        outer.setSpacing(SPACING["sm"])

        head = QHBoxLayout()
        title = QLabel("공격 연속기")
        title.setObjectName("presetTitle")
        head.addWidget(title)
        head.addStretch()
        add = QPushButton("+ 연속기 추가")
        add.clicked.connect(self.add_sequence)
        head.addWidget(add)
        outer.addLayout(head)

        guide = QLabel(
            "가로 키는 순서대로 실행되고, 아래 각 줄은 자기 반복 주기로 독립 실행됩니다. "
            "모든 초 단위 입력은 실행 시 기준값에서 최대 5% 범위로 랜덤 보정됩니다."
        )
        guide.setObjectName("presetDescription")
        guide.setWordWrap(True)
        outer.addWidget(guide)

        self._rows = QVBoxLayout()
        self._rows.setSpacing(SPACING["xs"])
        outer.addLayout(self._rows)
        self._render()

    def add_sequence(self) -> None:
        self._sequences.append({
            "enabled": True,
            "name": f"연속기 {len(self._sequences) + 1}",
            "keys": [""],
            "key_hold_sec": [0.05],
            "key_interval_sec": 0.15,
            "repeat_interval_sec": 1.0,
        })
        self._save_render()

    def remove_sequence(self, index: int) -> None:
        if 0 <= index < len(self._sequences):
            self._sequences.pop(index)
            self._save_render()

    def add_key(self, row_index: int) -> None:
        if 0 <= row_index < len(self._sequences):
            sequence = self._sequences[row_index]
            sequence.setdefault("keys", []).append("")
            sequence.setdefault("key_hold_sec", []).append(0.05)
            self._save_render()

    def remove_key(self, row_index: int, key_index: int) -> None:
        if 0 <= row_index < len(self._sequences):
            keys = self._sequences[row_index].setdefault("keys", [])
            if 0 <= key_index < len(keys):
                keys.pop(key_index)
                holds = self._sequences[row_index].setdefault("key_hold_sec", [])
                if key_index < len(holds):
                    holds.pop(key_index)
                self._save_render()

    def set_field(self, row_index: int, field: str, value) -> None:
        if 0 <= row_index < len(self._sequences):
            self._sequences[row_index][field] = value
            self._save()

    def set_key(self, row_index: int, key_index: int, value: str) -> None:
        if 0 <= row_index < len(self._sequences):
            keys = self._sequences[row_index].setdefault("keys", [])
            if 0 <= key_index < len(keys):
                keys[key_index] = value
                self._save()

    def set_key_hold(self, row_index: int, key_index: int, value: float) -> None:
        if 0 <= row_index < len(self._sequences):
            holds = self._sequences[row_index].setdefault("key_hold_sec", [])
            while len(holds) <= key_index:
                holds.append(0.05)
            holds[key_index] = float(value)
            self._save()

    def _save(self) -> None:
        self._cfg.set("attack", "sequences", deepcopy(self._sequences))
        for sequence in self._sequences:
            keys = [str(key).strip() for key in sequence.get("keys", []) if str(key).strip()]
            if sequence.get("enabled", True) and keys:
                self._cfg.set("attack", "key", keys[0])
                self._cfg.set(
                    "attack", "delay_sec", float(sequence.get("repeat_interval_sec", 0.4))
                )
                break
        self._cfg.save()

    def _save_render(self) -> None:
        self._save()
        self._render()

    def _render(self) -> None:
        while self._rows.count():
            item = self._rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for row_index, sequence in enumerate(self._sequences):
            self._rows.addWidget(self._build_row(row_index, sequence))

    def _build_row(self, row_index: int, sequence: dict) -> QWidget:
        row = QFrame()
        row.setObjectName("card")
        row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(SPACING["sm"], SPACING["xs"], SPACING["sm"], SPACING["xs"])
        layout.setSpacing(SPACING["xs"])

        header = QHBoxLayout()
        header.setSpacing(SPACING["xs"])
        enabled = QCheckBox("사용")
        enabled.setChecked(bool(sequence.get("enabled", True)))
        enabled.toggled.connect(
            lambda value, index=row_index: self.set_field(index, "enabled", bool(value))
        )
        header.addWidget(enabled)

        name = QLineEdit(str(sequence.get("name", "연속기")))
        name.setMinimumWidth(110)
        name.setMaximumWidth(220)
        name.textChanged.connect(
            lambda value, index=row_index: self.set_field(index, "name", value)
        )
        header.addWidget(name)
        header.addStretch()

        remove = QPushButton("삭제")
        remove.clicked.connect(lambda _=False, index=row_index: self.remove_sequence(index))
        header.addWidget(remove)
        layout.addLayout(header)

        keys_scroll = QScrollArea()
        keys_scroll.setObjectName("sequenceKeysScroll")
        keys_scroll.setFrameShape(QFrame.Shape.NoFrame)
        keys_scroll.setWidgetResizable(True)
        keys_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        keys_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        keys_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        keys_widget = QWidget()
        keys_layout = QHBoxLayout(keys_widget)
        keys_layout.setContentsMargins(0, 0, 0, 0)
        keys_layout.setSpacing(SPACING["xs"])
        keys = sequence.get("keys", []) or []
        holds = sequence.setdefault("key_hold_sec", [])
        while len(holds) < len(keys):
            holds.append(0.05)
        for key_index, key_value in enumerate(keys):
            if key_index:
                keys_layout.addWidget(QLabel("->"))
            key = QLineEdit(str(key_value))
            key.setPlaceholderText("키")
            key.setFixedWidth(105)
            key.textChanged.connect(
                lambda value, row=row_index, col=key_index: self.set_key(row, col, value)
            )
            keys_layout.addWidget(key)
            hold = QDoubleSpinBox()
            hold.setRange(0.0, 10.0)
            hold.setDecimals(2)
            hold.setSingleStep(0.05)
            hold.setSuffix(" 초")
            hold.setPrefix("유지 ")
            hold.setValue(float(holds[key_index]))
            hold.setFixedWidth(150)
            hold.valueChanged.connect(
                lambda value, row=row_index, col=key_index: self.set_key_hold(row, col, value)
            )
            keys_layout.addWidget(hold)
            remove_key = QPushButton("-")
            remove_key.setFixedWidth(24)
            remove_key.clicked.connect(
                lambda _=False, row=row_index, col=key_index: self.remove_key(row, col)
            )
            keys_layout.addWidget(remove_key)

        keys_layout.addStretch()
        keys_scroll.setWidget(keys_widget)

        keys_bar = QHBoxLayout()
        keys_bar.setSpacing(SPACING["xs"])
        keys_bar.addWidget(keys_scroll, 1)
        add_key = QPushButton("+ 키 추가")
        add_key.setMinimumWidth(105)
        add_key.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        add_key.clicked.connect(lambda _=False, index=row_index: self.add_key(index))
        keys_bar.addWidget(add_key)
        layout.addLayout(keys_bar)

        timing = QHBoxLayout()
        timing.setSpacing(SPACING["xs"])
        timing.addWidget(QLabel("키 간격"))
        key_interval = QDoubleSpinBox()
        key_interval.setRange(0.0, 10.0)
        key_interval.setDecimals(2)
        key_interval.setSingleStep(0.05)
        key_interval.setSuffix(" 초")
        key_interval.setMinimumWidth(150)
        key_interval.setValue(float(sequence.get("key_interval_sec", 0.15)))
        key_interval.valueChanged.connect(
            lambda value, index=row_index: self.set_field(index, "key_interval_sec", float(value))
        )
        timing.addWidget(key_interval)

        timing.addWidget(QLabel("반복 주기"))
        repeat = QDoubleSpinBox()
        repeat.setRange(0.05, 3600.0)
        repeat.setDecimals(2)
        repeat.setSingleStep(0.05)
        repeat.setSuffix(" 초")
        repeat.setMinimumWidth(150)
        repeat.setValue(float(sequence.get("repeat_interval_sec", 1.0)))
        repeat.valueChanged.connect(
            lambda value, index=row_index: self.set_field(index, "repeat_interval_sec", float(value))
        )
        timing.addWidget(repeat)
        timing.addStretch()
        layout.addLayout(timing)
        return row


