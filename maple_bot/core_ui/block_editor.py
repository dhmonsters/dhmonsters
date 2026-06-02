# BlockEditor — 좌표 동선 블록(route) 리스트 편집기. C routine_runner 스키마, config 양방향
# 행을 마우스로 드래그해 순서 변경(QListWidget InternalMove). 인덱스 API는 그대로 유지.
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QLineEdit, QListWidget, QListWidgetItem, QAbstractItemView,
)
from PyQt6.QtCore import Qt

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
    """floor_hunt.route 블록 리스트 편집. 추가/삭제/필드편집/드래그재정렬 → config 즉시 저장."""

    def __init__(self, config, keys: tuple, on_change=None):
        super().__init__()
        self._cfg = config
        self._keys = keys
        self._on_change = on_change or (lambda: None)
        self._route: list[dict] = list(config.get(*keys, default=[]) or [])
        self._reordering = False

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

        hint = QLabel("≡ 행을 위아래로 드래그해 실행 순서를 바꿀 수 있어요")
        hint.setObjectName("subtle")
        self._v.addWidget(hint)

        # 드래그 재정렬 리스트
        self._list = QListWidget()
        self._list.setObjectName("blockList")
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setSpacing(SPACING["xxs"])
        self._list.setMinimumHeight(360)   # 한 번에 ~6블록 보이게(캔버스가 커도 충분한 높이)
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        self._v.addWidget(self._list, 1)
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

    def move_row(self, src: int, dst: int) -> None:
        """src 위치 블록을 dst 위치로 이동(순서 변경). 드래그/프로그램 공용."""
        n = len(self._route)
        if not (0 <= src < n) or not (0 <= dst < n) or src == dst:
            return
        blk = self._route.pop(src)
        self._route.insert(dst, blk)
        self._save_render()

    # ── 드래그 재정렬 동기화 ──────────────────────────────────────────
    def _on_rows_moved(self, *args) -> None:
        """리스트에서 행을 드래그하면 화면 순서대로 self._route를 재구성."""
        if self._reordering:
            return
        order = [self._list.item(i).data(Qt.ItemDataRole.UserRole)
                 for i in range(self._list.count())]
        if any(o is None for o in order):
            return
        self._route = [self._route[o] for o in order]
        self._save_render()

    # ── 좌표 픽커 ──────────────────────────────────────────────────────
    def _grab_minimap(self):
        """미니맵 영역 캡처. 미설정이면 None."""
        import mss as _mss
        import numpy as np
        mm_x = int(self._cfg.get("minimap", "region_x", default=0))
        mm_y = int(self._cfg.get("minimap", "region_y", default=0))
        mm_w = int(self._cfg.get("minimap", "width", default=0))
        mm_h = int(self._cfg.get("minimap", "height", default=0))
        if mm_w <= 0:
            return None
        with _mss.mss() as sct:
            return np.array(sct.grab(
                {"left": mm_x, "top": mm_y, "width": mm_w, "height": mm_h}))[:, :, :3]

    def _pick_x(self, idx: int, field: str, spin,
                y_field: str | None = None, y_spin=None) -> None:
        """미니맵 클릭 → 상대 X를 field로 설정. y_field 주면 Y도 함께."""
        from core_ui.shot_selector import ClickPointPicker
        shot = self._grab_minimap()
        if shot is None:
            return
        dlg = ClickPointPicker(shot)

        def picked(x, y):
            self.set_field(idx, field, x)
            spin.setValue(x)
            if y_field is not None:
                self.set_field(idx, y_field, y)
                if y_spin is not None:
                    y_spin.setValue(y)
        dlg.point_picked.connect(picked)
        dlg.exec()

    def _pick_line(self, idx: int, start_spin, end_spin) -> None:
        """미니맵에서 시작→끝 한 번 드래그 → start_x/end_x 동시 설정(직선 표시)."""
        from core_ui.shot_selector import LinePointPicker
        shot = self._grab_minimap()
        if shot is None:
            return
        dlg = LinePointPicker(shot)

        def picked(sx, sy, ex, ey):
            lo, hi = (sx, ex) if sx <= ex else (ex, sx)
            self.set_field(idx, "start_x", lo)
            self.set_field(idx, "end_x", hi)
            start_spin.setValue(lo); end_spin.setValue(hi)
        dlg.line_picked.connect(picked)
        dlg.exec()

    def _pick_ladder(self, idx: int, x_spin, ybot_spin, ytop_spin) -> None:
        """미니맵에서 사다리 한 번 드래그 → X(평균)/위Y(작은Y)/아래Y(큰Y) 자동.
        위아래는 Y로 판단(미니맵은 위가 Y 작음)."""
        from core_ui.shot_selector import LinePointPicker
        shot = self._grab_minimap()
        if shot is None:
            return
        dlg = LinePointPicker(shot)

        def picked(sx, sy, ex, ey):
            lx = (sx + ex) // 2          # 사다리는 수직 → X 평균
            y_top = min(sy, ey)          # Y 작은 쪽 = 위
            y_bot = max(sy, ey)          # Y 큰 쪽 = 아래
            self.set_field(idx, "ladder_x", lx)
            self.set_field(idx, "y_top", y_top)
            self.set_field(idx, "y_bot", y_bot)
            x_spin.setValue(lx); ytop_spin.setValue(y_top); ybot_spin.setValue(y_bot)
        dlg.line_picked.connect(picked)
        dlg.exec()

    # ── 내부 ──────────────────────────────────────────────────────────
    def _save(self) -> None:
        valid = []
        for b in self._route:
            try:
                Block.from_dict(b)
                valid.append(b)
            except Exception:
                pass
        self._cfg.set(*self._keys, valid)
        self._cfg.save()
        self._on_change()

    def reload(self) -> None:
        """config에서 route를 다시 읽어 화면 갱신(외부 변경 반영)."""
        self._route = list(self._cfg.get(*self._keys, default=[]) or [])
        self._render()

    def _save_render(self) -> None:
        self._save()
        self._render()

    def _render(self) -> None:
        self._reordering = True
        self._list.clear()
        for i, blk in enumerate(self._route):
            item = QListWidgetItem(self._list)
            item.setData(Qt.ItemDataRole.UserRole, i)   # 현재 self._route 인덱스
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)
            row = self._build_row(i, blk)
            item.setSizeHint(row.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
        self._reordering = False

    def _build_row(self, idx: int, blk: dict) -> QWidget:
        # 2줄 카드: 윗줄=핸들·타입·옵션콤보·버튼·삭제 / 아랫줄=좌표 숫자(드래그로 채워짐)
        row = QWidget()
        v = QVBoxLayout(row)
        v.setContentsMargins(SPACING["xs"], SPACING["xxs"], SPACING["xs"], SPACING["xxs"])
        v.setSpacing(SPACING["xxs"])
        top = QHBoxLayout(); top.setSpacing(SPACING["xs"])
        bot = QHBoxLayout(); bot.setSpacing(SPACING["xs"])
        v.addLayout(top); v.addLayout(bot)

        handle = QLabel("≡"); handle.setObjectName("subtle"); handle.setFixedWidth(14)
        top.addWidget(handle)
        top.addWidget(QLabel(f"{idx+1}. {blk['type']}"))

        if blk["type"] == "move":
            md = QComboBox(); md.addItems(["count", "infinite", "pass"]); md.setFixedWidth(92)
            md.setCurrentText(blk.get("mode", "count"))
            md.currentTextChanged.connect(lambda val, i=idx: self.set_field(i, "mode", val))
            md.setToolTip("count=왕복횟수 / infinite=무한왕복 / pass=한방향 통과")
            top.addWidget(md)
            mt = QComboBox(); mt.addItems(["walk", "teleport"]); mt.setFixedWidth(92)
            mt.setCurrentText(blk.get("move_type", "walk"))
            mt.currentTextChanged.connect(lambda val, i=idx: self.set_field(i, "move_type", val))
            top.addWidget(mt)
            sw = QSpinBox(); sw.setRange(1, 99); sw.setPrefix("왕복 "); sw.setFixedWidth(90)
            sw.setValue(int(blk.get("sweeps", 1)))
            sw.valueChanged.connect(lambda val, i=idx: self.set_field(i, "sweeps", val))
            top.addWidget(sw)

            s_sx = QSpinBox(); s_sx.setRange(0, 4000); s_sx.setPrefix("시작 "); s_sx.setFixedWidth(106)
            s_sx.setValue(int(blk.get("start_x", 0)))
            s_sx.valueChanged.connect(lambda val, i=idx: self.set_field(i, "start_x", val))
            bot.addWidget(s_sx)
            e_sx = QSpinBox(); e_sx.setRange(0, 4000); e_sx.setPrefix("끝 "); e_sx.setFixedWidth(100)
            e_sx.setValue(int(blk.get("end_x", 0)))
            e_sx.valueChanged.connect(lambda val, i=idx: self.set_field(i, "end_x", val))
            bot.addWidget(e_sx)
            ln = QPushButton("📏 구간 긋기"); ln.setFixedWidth(100)
            ln.clicked.connect(lambda _=False, i=idx, sw_=s_sx, ew_=e_sx:
                               self._pick_line(i, sw_, ew_))
            bot.addWidget(ln)
        elif blk["type"] == "attack":
            sk = QLineEdit(blk.get("skill_key", "")); sk.setPlaceholderText("스킬키")
            sk.setFixedWidth(120)
            sk.textChanged.connect(lambda val, i=idx: self.set_field(i, "skill_key", val))
            top.addWidget(sk)
        elif blk["type"] == "ladder":
            dr = QComboBox(); dr.addItems(["up", "down"]); dr.setFixedWidth(80)
            dr.setCurrentText(blk.get("ladder_dir", "up"))
            dr.currentTextChanged.connect(lambda val, i=idx: self.set_field(i, "ladder_dir", val))
            dr.setToolTip("up=등반(y_top까지) / down=하강(아래+점프)")
            top.addWidget(dr)
            es = QComboBox(); es.addItems(["left", "right"]); es.setFixedWidth(74)
            es.setCurrentText(blk.get("exit_side", "left"))
            es.currentTextChanged.connect(lambda val, i=idx: self.set_field(i, "exit_side", val))
            es.setToolTip("하강 시 뛰어내릴 방향")
            top.addWidget(es)
            gs = QComboBox(); gs.addItems(["auto", "left", "right", "random"]); gs.setFixedWidth(86)
            gs.setCurrentText(blk.get("grab_side", "auto"))
            gs.currentTextChanged.connect(lambda val, i=idx: self.set_field(i, "grab_side", val))
            gs.setToolTip("밧줄 잡는 방향: auto=가까운쪽 / random=좌우 랜덤")
            top.addWidget(gs)

            lx = QSpinBox(); lx.setRange(0, 4000); lx.setPrefix("X "); lx.setFixedWidth(98)
            lx.setValue(int(blk.get("ladder_x", 0)))
            lx.valueChanged.connect(lambda val, i=idx: self.set_field(i, "ladder_x", val))
            bot.addWidget(lx)
            yb = QSpinBox(); yb.setRange(0, 4000); yb.setPrefix("아래Y "); yb.setFixedWidth(108)
            yb.setValue(int(blk.get("y_bot", 0)))
            yb.valueChanged.connect(lambda val, i=idx: self.set_field(i, "y_bot", val))
            bot.addWidget(yb)
            yt = QSpinBox(); yt.setRange(0, 4000); yt.setPrefix("위Y "); yt.setFixedWidth(100)
            yt.setValue(int(blk.get("y_top", 0)))
            yt.valueChanged.connect(lambda val, i=idx: self.set_field(i, "y_top", val))
            bot.addWidget(yt)
            ln = QPushButton("📏 사다리 긋기"); ln.setFixedWidth(108)
            ln.clicked.connect(lambda _=False, i=idx, xw=lx, ybw=yb, ytw=yt:
                               self._pick_ladder(i, xw, ybw, ytw))
            bot.addWidget(ln)

        top.addStretch()
        bot.addStretch()
        rm = QPushButton("✕"); rm.setFixedWidth(28)
        rm.clicked.connect(lambda _=False, i=idx: self.remove_row(i))
        top.addWidget(rm)
        return row
