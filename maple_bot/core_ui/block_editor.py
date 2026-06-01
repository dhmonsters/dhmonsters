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

    def _pick_x(self, idx: int, field: str, spin,
                y_field: str | None = None, y_spin=None) -> None:
        """미니맵 클릭 → 상대 X를 field로 설정. y_field 주면 Y도 함께(사다리 시작/끝점)."""
        import mss as _mss
        import numpy as np
        from core_ui.shot_selector import ClickPointPicker
        mm_x = int(self._cfg.get("minimap", "region_x", default=0))
        mm_y = int(self._cfg.get("minimap", "region_y", default=0))
        mm_w = int(self._cfg.get("minimap", "width", default=0))
        mm_h = int(self._cfg.get("minimap", "height", default=0))
        if mm_w <= 0:
            return  # 미니맵 미설정
        with _mss.mss() as sct:
            shot = np.array(sct.grab(
                {"left": mm_x, "top": mm_y, "width": mm_w, "height": mm_h}))[:, :, :3]
        dlg = ClickPointPicker(shot)

        def picked(x, y):
            self.set_field(idx, field, x)   # 미니맵 상대 X
            spin.setValue(x)
            if y_field is not None:
                self.set_field(idx, y_field, y)   # 미니맵 상대 Y (사다리 발판 높이)
                if y_spin is not None:
                    y_spin.setValue(y)
        dlg.point_picked.connect(picked)
        dlg.exec()

    def _pick_line(self, idx: int, start_spin, end_spin) -> None:
        """미니맵에서 시작→끝 한 번 드래그 → start_x/end_x 동시 설정(직선 표시)."""
        import mss as _mss
        import numpy as np
        from core_ui.shot_selector import LinePointPicker
        mm_x = int(self._cfg.get("minimap", "region_x", default=0))
        mm_y = int(self._cfg.get("minimap", "region_y", default=0))
        mm_w = int(self._cfg.get("minimap", "width", default=0))
        mm_h = int(self._cfg.get("minimap", "height", default=0))
        if mm_w <= 0:
            return
        with _mss.mss() as sct:
            shot = np.array(sct.grab(
                {"left": mm_x, "top": mm_y, "width": mm_w, "height": mm_h}))[:, :, :3]
        dlg = LinePointPicker(shot)

        def picked(sx, sy, ex, ey):
            # start_x < end_x 정규화 (구간 왕복은 좌→우 기준)
            lo, hi = (sx, ex) if sx <= ex else (ex, sx)
            self.set_field(idx, "start_x", lo)
            self.set_field(idx, "end_x", hi)
            start_spin.setValue(lo); end_spin.setValue(hi)
        dlg.line_picked.connect(picked)
        dlg.exec()

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
            # 구간 왕복: 시작~끝을 한 번에 드래그(📏) + 왕복 횟수
            s_sx = QSpinBox(); s_sx.setRange(0, 4000); s_sx.setPrefix("시작 ")
            s_sx.setValue(int(blk.get("start_x", 0)))
            s_sx.valueChanged.connect(lambda v, i=idx: self.set_field(i, "start_x", v))
            h.addWidget(s_sx)
            e_sx = QSpinBox(); e_sx.setRange(0, 4000); e_sx.setPrefix("끝 ")
            e_sx.setValue(int(blk.get("end_x", 0)))
            e_sx.valueChanged.connect(lambda v, i=idx: self.set_field(i, "end_x", v))
            h.addWidget(e_sx)
            ln = QPushButton("📏 구간 긋기"); ln.setFixedWidth(90)
            ln.clicked.connect(lambda _=False, i=idx, sw_=s_sx, ew_=e_sx:
                               self._pick_line(i, sw_, ew_))
            h.addWidget(ln)

            sw = QSpinBox(); sw.setRange(1, 99); sw.setPrefix("왕복 ")
            sw.setValue(int(blk.get("sweeps", 1)))
            sw.valueChanged.connect(lambda v, i=idx: self.set_field(i, "sweeps", v))
            h.addWidget(sw)

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
            # 사다리: 시작점(아래 발판 X,Y) 📍 + 끝점(위 발판 Y) 📍 + 내릴 방향
            lx = QSpinBox(); lx.setRange(0, 4000); lx.setPrefix("X ")
            lx.setValue(int(blk.get("ladder_x", 0)))
            lx.valueChanged.connect(lambda v, i=idx: self.set_field(i, "ladder_x", v))
            h.addWidget(lx)
            yb = QSpinBox(); yb.setRange(0, 4000); yb.setPrefix("아래Y ")
            yb.setValue(int(blk.get("y_bot", 0)))
            yb.valueChanged.connect(lambda v, i=idx: self.set_field(i, "y_bot", v))
            h.addWidget(yb)
            sp = QPushButton("📍시작"); sp.setFixedWidth(56)
            sp.clicked.connect(lambda _=False, i=idx, xw=lx, yw=yb:
                               self._pick_x(i, "ladder_x", xw, "y_bot", yw))
            h.addWidget(sp)
            yt = QSpinBox(); yt.setRange(0, 4000); yt.setPrefix("위Y ")
            yt.setValue(int(blk.get("y_top", 0)))
            yt.valueChanged.connect(lambda v, i=idx: self.set_field(i, "y_top", v))
            h.addWidget(yt)
            tp = QPushButton("📍끝"); tp.setFixedWidth(48)
            # 끝점(위 발판): 같은 사다리라 X 갱신 + 위 Y 갱신
            tp.clicked.connect(lambda _=False, i=idx, xw=lx, yw=yt:
                               self._pick_x(i, "ladder_x", xw, "y_top", yw))
            h.addWidget(tp)
            es = QComboBox(); es.addItems(["left", "right"])
            es.setCurrentText(blk.get("exit_side", "left"))
            es.currentTextChanged.connect(lambda v, i=idx: self.set_field(i, "exit_side", v))
            h.addWidget(es)

        h.addStretch()
        rm = QPushButton("✕"); rm.setFixedWidth(28)
        rm.clicked.connect(lambda _=False, i=idx: self.remove_row(i))
        h.addWidget(rm)
        return row
