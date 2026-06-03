# BlockEditor — 좌표 동선 블록(route) 리스트 편집기. C routine_runner 스키마, config 양방향
# 행을 마우스로 드래그해 순서 변경(QListWidget InternalMove). 인덱스 API는 그대로 유지.
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QSpinBox, QLineEdit, QListWidget, QListWidgetItem, QAbstractItemView,
    QSizePolicy, QAbstractSpinBox,
)
from PyQt6.QtCore import Qt, QSize

from core_ui.theme import SPACING
from core.navigation.block import Block

# 블록 타입별 기본값 (C routine_runner 스키마)
_DEFAULTS = {
    "move":   {"type": "move", "target_x": 0, "move_type": "walk", "direction": "right"},
    "attack": {"type": "attack", "skill_key": "", "attack_mode": "duration", "attack_value": 1.0},
    "ladder": {"type": "ladder", "ladder_x": 0, "y_top": 0, "y_bot": 0, "exit_side": "left"},
    "jump":   {"type": "jump", "direction": "right"},
}

# 블록 타입 한글 표시명 (저장값은 영문 유지)
_TYPE_KO = {"move": "이동", "attack": "공격", "ladder": "사다리",
            "jump": "점프", "teleport": "텔포"}


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
        self._list.setSpacing(SPACING["xs"])
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
            sh = row.sizeHint()
            item.setSizeHint(QSize(sh.width(), max(sh.height(), 80)))  # 2줄+버튼 세로 안 잘리게
            self._list.addItem(item)
            self._list.setItemWidget(item, row)
        self._reordering = False

    @staticmethod
    def _grow(w, min_w: int):
        """창 크기에 따라 늘고/줄도록: 최소폭 + 가로 Expanding. (고정폭 대신)
        스핀박스는 업/다운 버튼 제거 → 어수선함 없이 깔끔한 둥근칸(좌표는 긋기/입력으로)."""
        w.setMinimumWidth(min_w)
        w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if isinstance(w, QSpinBox):
            w.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        return w

    def _kv_combo(self, idx: int, field: str, pairs: list, current: str,
                  tooltip: str = "") -> QComboBox:
        """한글 표시 + 영문 저장값 콤보. pairs=[(한글, 저장값), ...]. 변경 시 set_field(저장값)."""
        cb = QComboBox()
        for label, val in pairs:
            cb.addItem(label, val)
        i = cb.findData(current)
        if i >= 0:
            cb.setCurrentIndex(i)
        cb.currentIndexChanged.connect(
            lambda _i, i_=idx, f=field, c=cb: self.set_field(i_, f, c.currentData()))
        if tooltip:
            cb.setToolTip(tooltip)
        return cb

    def _build_row(self, idx: int, blk: dict) -> QWidget:
        # 2줄 카드: 윗줄=핸들·타입·옵션콤보·삭제 / 아랫줄=좌표 숫자+긋기
        # 모든 입력은 최소폭+Expanding이라 창 크기에 따라 자연스럽게 늘고/줄어든다.
        row = QWidget()
        v = QVBoxLayout(row)
        v.setContentsMargins(SPACING["xs"], SPACING["xxs"], SPACING["xs"], SPACING["xxs"])
        v.setSpacing(SPACING["xs"])
        top = QHBoxLayout(); top.setSpacing(SPACING["xs"])
        bot = QHBoxLayout(); bot.setSpacing(SPACING["xs"])
        v.addLayout(top); v.addLayout(bot)
        g = self._grow

        handle = QLabel("≡"); handle.setObjectName("subtle"); handle.setFixedWidth(14)
        top.addWidget(handle)
        tl = QLabel(f"{idx+1}. {_TYPE_KO.get(blk['type'], blk['type'])}"); tl.setMinimumWidth(60)
        top.addWidget(tl)

        if blk["type"] == "move":
            md = self._kv_combo(idx, "mode",
                                [("횟수왕복", "count"), ("무한왕복", "infinite"), ("통과", "pass")],
                                blk.get("mode", "count"),
                                "횟수왕복=지정 횟수 / 무한왕복=계속 / 통과=한방향 1회")
            top.addWidget(g(md, 84), 1)
            mt = self._kv_combo(idx, "move_type",
                                [("걷기", "walk"), ("텔레포트", "teleport")],
                                blk.get("move_type", "walk"))
            top.addWidget(g(mt, 84), 1)
            sw = QSpinBox(); sw.setRange(1, 99); sw.setPrefix("왕복 ")
            sw.setValue(int(blk.get("sweeps", 1)))
            sw.valueChanged.connect(lambda val, i=idx: self.set_field(i, "sweeps", val))
            top.addWidget(g(sw, 74), 1)
            rm = QSpinBox(); rm.setRange(0, 99); rm.setPrefix("랜덤 ")
            rm.setValue(int(blk.get("rand_margin", 0)))
            rm.setToolTip("왕복 끝점 랜덤폭(px). 구간 안에서 매번 다른 지점에서 턴(0=정확 끝점)")
            rm.valueChanged.connect(lambda val, i=idx: self.set_field(i, "rand_margin", val))
            top.addWidget(g(rm, 74), 1)

            s_sx = QSpinBox(); s_sx.setRange(0, 4000); s_sx.setPrefix("시작 ")
            s_sx.setValue(int(blk.get("start_x", 0)))
            s_sx.valueChanged.connect(lambda val, i=idx: self.set_field(i, "start_x", val))
            bot.addWidget(g(s_sx, 92), 1)
            e_sx = QSpinBox(); e_sx.setRange(0, 4000); e_sx.setPrefix("끝 ")
            e_sx.setValue(int(blk.get("end_x", 0)))
            e_sx.valueChanged.connect(lambda val, i=idx: self.set_field(i, "end_x", val))
            bot.addWidget(g(e_sx, 88), 1)
            ln = QPushButton("구간 긋기")   # 글자 크기에 맞춰 자동(스핀박스만 늘어남)
            ln.clicked.connect(lambda _=False, i=idx, sw_=s_sx, ew_=e_sx:
                               self._pick_line(i, sw_, ew_))
            bot.addWidget(ln)
        elif blk["type"] == "attack":
            sk = QLineEdit(blk.get("skill_key", "")); sk.setPlaceholderText("스킬키")
            sk.textChanged.connect(lambda val, i=idx: self.set_field(i, "skill_key", val))
            top.addWidget(g(sk, 120), 1)
        elif blk["type"] == "ladder":
            dr = self._kv_combo(idx, "ladder_dir",
                                [("등반", "up"), ("하강", "down")],
                                blk.get("ladder_dir", "up"),
                                "등반=위Y까지 올라감 / 하강=아래+점프로 내림")
            top.addWidget(g(dr, 72), 1)
            es = self._kv_combo(idx, "exit_side",
                                [("왼쪽", "left"), ("오른쪽", "right"), ("양쪽", "both")],
                                blk.get("exit_side", "left"),
                                "하강 시 뛰어내릴 방향 (양쪽=좌우 랜덤)")
            top.addWidget(g(es, 72), 1)
            gs = self._kv_combo(idx, "grab_side",
                                [("자동", "auto"), ("왼쪽", "left"), ("오른쪽", "right"), ("랜덤", "random")],
                                blk.get("grab_side", "auto"),
                                "밧줄 잡는 방향: 자동=가까운쪽 / 랜덤=좌우 랜덤")
            top.addWidget(g(gs, 84), 1)

            lx = QSpinBox(); lx.setRange(0, 4000); lx.setPrefix("X ")
            lx.setValue(int(blk.get("ladder_x", 0)))
            lx.valueChanged.connect(lambda val, i=idx: self.set_field(i, "ladder_x", val))
            bot.addWidget(g(lx, 80), 1)
            yb = QSpinBox(); yb.setRange(0, 4000); yb.setPrefix("아래Y ")
            yb.setValue(int(blk.get("y_bot", 0)))
            yb.valueChanged.connect(lambda val, i=idx: self.set_field(i, "y_bot", val))
            bot.addWidget(g(yb, 100), 1)
            yt = QSpinBox(); yt.setRange(0, 4000); yt.setPrefix("위Y ")
            yt.setValue(int(blk.get("y_top", 0)))
            yt.valueChanged.connect(lambda val, i=idx: self.set_field(i, "y_top", val))
            bot.addWidget(g(yt, 92), 1)
            ln = QPushButton("사다리 긋기")   # 글자 크기에 맞춰 자동
            ln.clicked.connect(lambda _=False, i=idx, xw=lx, ybw=yb, ytw=yt:
                               self._pick_ladder(i, xw, ybw, ytw))
            bot.addWidget(ln)

        rm = QPushButton("✕"); rm.setFixedWidth(28)
        rm.clicked.connect(lambda _=False, i=idx: self.remove_row(i))
        top.addWidget(rm)
        return row
