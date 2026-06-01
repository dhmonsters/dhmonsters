# BlockEditor — 좌표 동선 블록(route) 리스트 편집기. C routine_runner 스키마, config 양방향
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QLineEdit, QFrame,
)

from core_ui.theme import SPACING
from core.navigation.block import Block

# 블록 타입별 기본값 (C routine_runner 스키마)
_DEFAULTS = {
    "move":   {"type": "move", "target_x": 0, "move_type": "walk", "direction": "right"},
    "attack": {"type": "attack", "skill_key": "", "attack_mode": "duration", "attack_value": 1.0},
    "ladder": {"type": "ladder", "ladder_x": 0, "y_top": 0, "y_bot": 0, "exit_side": "left"},
    "jump":   {"type": "jump", "direction": "right"},
}


class BlockEditor(QWidget):
    """floor_hunt.route 블록 리스트 편집. 추가/삭제/필드편집 → config 즉시 저장."""

    def __init__(self, config, keys: tuple):
        super().__init__()
        self._cfg = config
        self._keys = keys
        self._route: list[dict] = list(config.get(*keys, default=[]) or [])

        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(0, 0, 0, 0)
        self._v.setSpacing(SPACING["xxs"])

        # 추가 버튼 행
        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("블록 추가:"))
        for t, label in [("move", "이동"), ("attack", "공격"),
                         ("ladder", "사다리"), ("jump", "점프")]:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, tt=t: self.add_block(tt))
            add_row.addWidget(b)
        add_row.addStretch()
        self._v.addLayout(add_row)

        self._rows_box = QVBoxLayout()
        self._rows_box.setSpacing(SPACING["xxs"])
        self._v.addLayout(self._rows_box)
        self._render()

    # ── 공개 API (테스트/사용) ────────────────────────────────────────
    def row_count(self) -> int:
        return len(self._route)

    def add_block(self, block_type: str) -> None:
        self._route.append(dict(_DEFAULTS[block_type]))
        self._save_render()

    def remove_row(self, idx: int) -> None:
        if 0 <= idx < len(self._route):
            self._route.pop(idx)
            self._save_render()

    def set_field(self, idx: int, field: str, value) -> None:
        if 0 <= idx < len(self._route):
            self._route[idx][field] = value
            self._save()

    # ── 내부 ──────────────────────────────────────────────────────────
    def _save(self) -> None:
        # Block 검증 통과하는 것만 저장(전방호환)
        valid = []
        for b in self._route:
            try:
                Block.from_dict(b)
                valid.append(b)
            except Exception:
                pass
        self._cfg.set(*self._keys, valid)
        self._cfg.save()

    def _save_render(self) -> None:
        self._save()
        self._render()

    def _clear_rows(self) -> None:
        while self._rows_box.count():
            item = self._rows_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _render(self) -> None:
        self._clear_rows()
        for i, blk in enumerate(self._route):
            self._rows_box.addWidget(self._build_row(i, blk))

    def _build_row(self, idx: int, blk: dict) -> QWidget:
        row = QFrame()
        row.setObjectName("card")
        h = QHBoxLayout(row)
        h.setContentsMargins(SPACING["sm"], SPACING["xxs"], SPACING["sm"], SPACING["xxs"])
        h.addWidget(QLabel(f"{idx+1}. {blk['type']}"))

        if blk["type"] == "move":
            sx = QSpinBox(); sx.setRange(0, 4000); sx.setPrefix("X ")
            sx.setValue(int(blk.get("target_x", 0)))
            sx.valueChanged.connect(lambda v, i=idx: self.set_field(i, "target_x", v))
            h.addWidget(sx)
            mt = QComboBox(); mt.addItems(["walk", "teleport"])
            mt.setCurrentText(blk.get("move_type", "walk"))
            mt.currentTextChanged.connect(lambda v, i=idx: self.set_field(i, "move_type", v))
            h.addWidget(mt)
        elif blk["type"] == "attack":
            sk = QLineEdit(blk.get("skill_key", "")); sk.setPlaceholderText("스킬키")
            sk.setFixedWidth(70)
            sk.textChanged.connect(lambda v, i=idx: self.set_field(i, "skill_key", v))
            h.addWidget(sk)
        elif blk["type"] == "ladder":
            lx = QSpinBox(); lx.setRange(0, 4000); lx.setPrefix("사다리X ")
            lx.setValue(int(blk.get("ladder_x", 0)))
            lx.valueChanged.connect(lambda v, i=idx: self.set_field(i, "ladder_x", v))
            h.addWidget(lx)

        h.addStretch()
        rm = QPushButton("✕"); rm.setFixedWidth(28)
        rm.clicked.connect(lambda _=False, i=idx: self.remove_row(i))
        h.addWidget(rm)
        return row
