# 좌표 탭 - 사냥터 프리셋 / 미니맵 / 구역 / 밧줄 / 공격 설정 UI
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QSpinBox, QPushButton, QListWidget,
    QLineEdit, QFileDialog, QComboBox, QRadioButton,
    QButtonGroup, QScrollArea, QMessageBox, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor

from core.minimap_reader import MinimapConfig, Zone, RopePoint, MinimapReader
from core.screen_reader import ScreenReader
from ui.region_selector import RegionSelector
from ui.widgets import HotkeyCapture


class _ColorPickerOverlay(QWidget):
    """전화면 투명 오버레이 — 클릭한 픽셀 RGB를 반환하는 스포이드."""
    color_picked = pyqtSignal(int, int, int)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._screen = ScreenReader()
        self.showFullScreen()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 18))
        painter.setPen(QColor(255, 255, 255, 180))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                         "미니맵의 캐릭터 도트를 클릭하세요\n(ESC: 취소)")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x = int(event.globalPosition().x())
            y = int(event.globalPosition().y())
            r, g, b = self._screen.get_pixel_color(x, y)
            self.color_picked.emit(r, g, b)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()


class TabCoordinate(QWidget):
    def __init__(self, config, hotkey_manager=None):
        super().__init__()
        self.config = config
        self._hk = hotkey_manager
        self._selector = None

        self._zones: list[Zone] = []
        self._ropes: list[RopePoint] = []
        self._last_pos: tuple[int, int] | None = None
        self._pending_left_x: int | None = None
        self._pending_right_x: int | None = None
        self._pending_rope_x: int | None = None

        self._screen = ScreenReader()
        self._minimap_reader = MinimapReader(self._screen)

        outer = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(8)

        layout.addWidget(self._build_preset_group())
        layout.addWidget(self._build_minimap_group())
        layout.addWidget(self._build_zone_group())
        layout.addWidget(self._build_rope_group())
        layout.addWidget(self._build_floor_hunt_group())
        layout.addStretch()

        scroll_area.setWidget(inner)
        outer.addWidget(scroll_area)

        self.load_from_config()

    # ── 1. 사냥터 프리셋 ──────────────────────────────────────────────
    def _build_preset_group(self) -> QGroupBox:
        group = QGroupBox("사냥터 프리셋")
        layout = QVBoxLayout(group)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("이름"))
        self.edit_preset_name = QLineEdit()
        self.edit_preset_name.setPlaceholderText("사냥터 이름 입력")
        row1.addWidget(self.edit_preset_name)
        btn_save = QPushButton("저장")
        btn_save.setFixedWidth(55)
        btn_save.clicked.connect(self._save_preset)
        row1.addWidget(btn_save)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("불러오기"))
        self.combo_preset = QComboBox()
        self.combo_preset.setMinimumWidth(150)
        row2.addWidget(self.combo_preset)
        btn_load = QPushButton("불러오기")
        btn_load.setFixedWidth(70)
        btn_load.clicked.connect(self._load_preset)
        btn_del = QPushButton("삭제")
        btn_del.setFixedWidth(50)
        btn_del.clicked.connect(self._delete_preset)
        row2.addWidget(btn_load)
        row2.addWidget(btn_del)
        row2.addStretch()
        layout.addLayout(row2)

        return group

    # ── 2. 미니맵 설정 ────────────────────────────────────────────────
    def _build_minimap_group(self) -> QGroupBox:
        group = QGroupBox("미니맵 설정")
        layout = QVBoxLayout(group)

        # 드래그 + 단축키
        drag_row = QHBoxLayout()
        btn_drag = QPushButton("드래그로 미니맵 영역 지정")
        btn_drag.clicked.connect(self._select_minimap_region)
        drag_row.addWidget(btn_drag)
        drag_row.addSpacing(8)
        drag_row.addWidget(QLabel("단축키"))
        self.btn_mm_hotkey = HotkeyCapture("f11", self._apply_mm_hotkey)
        self.lbl_mm_hk = QLabel("")
        drag_row.addWidget(self.btn_mm_hotkey)
        drag_row.addWidget(self.lbl_mm_hk)
        drag_row.addStretch()
        layout.addLayout(drag_row)

        # 위치 / 크기
        pos_row = QHBoxLayout()
        pos_row.addWidget(QLabel("위치/크기"))
        self.spin_rx = QSpinBox(); self.spin_rx.setRange(0, 9999); self.spin_rx.setPrefix("X ")
        self.spin_ry = QSpinBox(); self.spin_ry.setRange(0, 9999); self.spin_ry.setPrefix("Y ")
        self.spin_rw = QSpinBox(); self.spin_rw.setRange(1, 2000); self.spin_rw.setPrefix("너비 "); self.spin_rw.setValue(200)
        self.spin_rh = QSpinBox(); self.spin_rh.setRange(1, 2000); self.spin_rh.setPrefix("높이 "); self.spin_rh.setValue(120)
        for w in [self.spin_rx, self.spin_ry, self.spin_rw, self.spin_rh]:
            w.setFixedWidth(90); pos_row.addWidget(w)
        pos_row.addStretch()
        layout.addLayout(pos_row)

        # 캐릭터 도트 색 (노란색 기본: 255,255,0)
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("캐릭터 색"))
        self.spin_cr = QSpinBox(); self.spin_cr.setRange(0,255); self.spin_cr.setPrefix("R "); self.spin_cr.setValue(255)
        self.spin_cg = QSpinBox(); self.spin_cg.setRange(0,255); self.spin_cg.setPrefix("G "); self.spin_cg.setValue(255)
        self.spin_cb = QSpinBox(); self.spin_cb.setRange(0,255); self.spin_cb.setPrefix("B "); self.spin_cb.setValue(0)
        self.spin_tol = QSpinBox(); self.spin_tol.setRange(1,100); self.spin_tol.setPrefix("허용 "); self.spin_tol.setValue(40)
        for w in [self.spin_cr, self.spin_cg, self.spin_cb, self.spin_tol]:
            w.setFixedWidth(90); color_row.addWidget(w)
        btn_eyedrop = QPushButton("스포이드")
        btn_eyedrop.setFixedWidth(70)
        btn_eyedrop.setToolTip("클릭 후 미니맵의 캐릭터 도트를 클릭해 색상을 자동으로 가져옵니다")
        btn_eyedrop.clicked.connect(self._pick_char_color)
        color_row.addWidget(btn_eyedrop)
        color_row.addStretch()
        layout.addLayout(color_row)

        # 위치 확인
        pos_check = QHBoxLayout()
        btn_pos = QPushButton("캐릭터 위치 확인")
        btn_pos.clicked.connect(self._fetch_pos)
        self.lbl_pos = QLabel("위치: -")
        self.lbl_pos.setMinimumWidth(160)
        pos_check.addWidget(btn_pos)
        pos_check.addWidget(self.lbl_pos)
        pos_check.addStretch()
        layout.addLayout(pos_check)

        return group

    # ── 3. 구역 설정 ──────────────────────────────────────────────────
    def _build_zone_group(self) -> QGroupBox:
        group = QGroupBox("구역 설정 (층별 이동 범위)")
        layout = QVBoxLayout(group)

        # 드래그로 구역 지정 (미니맵 위에서 드래그 → 자동 변환)
        drag_row = QHBoxLayout()
        btn_drag_zone = QPushButton("드래그로 구역 지정")
        btn_drag_zone.clicked.connect(self._select_zone_region)
        drag_row.addWidget(btn_drag_zone)
        drag_row.addSpacing(8)
        drag_row.addWidget(QLabel("단축키"))
        self.btn_zone_hotkey = HotkeyCapture("f12", self._apply_zone_hotkey)
        self.lbl_zone_hk = QLabel("")
        drag_row.addWidget(self.btn_zone_hotkey)
        drag_row.addWidget(self.lbl_zone_hk)
        drag_row.addStretch()
        layout.addLayout(drag_row)

        # 경계 표시 (드래그 또는 버튼으로 채워짐)
        boundary = QHBoxLayout()
        btn_left = QPushButton("← 왼쪽 경계")
        btn_right = QPushButton("→ 오른쪽 경계")
        btn_left.clicked.connect(self._set_left)
        btn_right.clicked.connect(self._set_right)
        self.lbl_left = QLabel("왼쪽 X: -")
        self.lbl_right = QLabel("오른쪽 X: -")
        boundary.addWidget(btn_left); boundary.addWidget(self.lbl_left)
        boundary.addSpacing(8)
        boundary.addWidget(btn_right); boundary.addWidget(self.lbl_right)
        boundary.addStretch()
        layout.addLayout(boundary)

        # Y 범위 / 이름 / 왕복 횟수
        opt = QHBoxLayout()
        opt.addWidget(QLabel("Y 범위"))
        self.spin_ymin = QSpinBox(); self.spin_ymin.setRange(0, 9999); self.spin_ymin.setPrefix("최소 ")
        self.spin_ymax = QSpinBox(); self.spin_ymax.setRange(0, 9999); self.spin_ymax.setPrefix("최대 "); self.spin_ymax.setValue(9999)
        for w in [self.spin_ymin, self.spin_ymax]:
            w.setFixedWidth(90); opt.addWidget(w)
        opt.addSpacing(8)
        opt.addWidget(QLabel("이름"))
        self.edit_zone_name = QLineEdit("1층"); self.edit_zone_name.setFixedWidth(70)
        opt.addWidget(self.edit_zone_name)
        opt.addSpacing(8)
        opt.addWidget(QLabel("왕복"))
        self.spin_zone_sweeps = QSpinBox()
        self.spin_zone_sweeps.setRange(0, 99)
        self.spin_zone_sweeps.setValue(2)
        self.spin_zone_sweeps.setFixedWidth(55)
        self.spin_zone_sweeps.setToolTip("층별 사냥 시 이 층에서 왕복할 횟수 (0 = 무제한)")
        opt.addWidget(self.spin_zone_sweeps)
        opt.addWidget(QLabel("회"))
        opt.addStretch()
        layout.addLayout(opt)

        # 공격 패턴 선택
        pat_row = QHBoxLayout()
        pat_row.addWidget(QLabel("공격 패턴"))
        self.cmb_zone_pattern = QComboBox()
        self.cmb_zone_pattern.setMinimumWidth(120)
        self.cmb_zone_pattern.setToolTip(
            "이 구역에서 사용할 키 반복 패턴을 선택합니다.\n"
            "사냥 탭에서 '프리셋으로 저장' 후 여기서 선택하세요."
        )
        btn_refresh_pat = QPushButton("🔄")
        btn_refresh_pat.setFixedWidth(30)
        btn_refresh_pat.setToolTip("사냥 탭에서 저장한 패턴 목록을 새로고침합니다.")
        btn_refresh_pat.clicked.connect(self._refresh_pattern_combo)
        pat_row.addWidget(self.cmb_zone_pattern)
        pat_row.addWidget(btn_refresh_pat)
        pat_row.addStretch()
        layout.addLayout(pat_row)
        self._refresh_pattern_combo()

        # 랜덤 전환 여유 — 경계 직전 임의 거리에서 방향 전환
        margin_row = QHBoxLayout()
        margin_row.addWidget(QLabel("랜덤 전환 여유"))
        self.spin_margin_min = QSpinBox()
        self.spin_margin_min.setRange(0, 200)
        self.spin_margin_min.setPrefix("최소 ")
        self.spin_margin_min.setSuffix(" px")
        self.spin_margin_min.setFixedWidth(95)
        self.spin_margin_max = QSpinBox()
        self.spin_margin_max.setRange(0, 200)
        self.spin_margin_max.setPrefix("최대 ")
        self.spin_margin_max.setSuffix(" px")
        self.spin_margin_max.setFixedWidth(95)
        self.spin_margin_max.setValue(10)
        margin_row.addWidget(self.spin_margin_min)
        margin_row.addWidget(self.spin_margin_max)
        margin_row.addWidget(QLabel("(0이면 항상 끝까지)"))
        margin_row.addStretch()
        layout.addLayout(margin_row)

        btn_add = QPushButton("+ 구역 추가")
        btn_add.clicked.connect(self._add_zone)
        layout.addWidget(btn_add)

        self.zone_list = QListWidget(); self.zone_list.setMaximumHeight(100)
        layout.addWidget(self.zone_list)

        zone_btn_row = QHBoxLayout()
        btn_del = QPushButton("삭제")
        btn_del.clicked.connect(self._delete_zone)
        btn_zone_save = QPushButton("프리셋에 저장")
        btn_zone_save.clicked.connect(self.save_to_config)
        zone_btn_row.addWidget(btn_del)
        zone_btn_row.addWidget(btn_zone_save)
        zone_btn_row.addStretch()
        layout.addLayout(zone_btn_row)

        return group

    # ── 4. 밧줄 설정 ──────────────────────────────────────────────────
    def _build_rope_group(self) -> QGroupBox:
        group = QGroupBox("밧줄 / 로프 설정")
        layout = QVBoxLayout(group)

        note = QLabel(
            "밧줄 X 좌표: 봇이 경계에 도달하면 밧줄 위치로 이동해 점프 후 오릅니다.\n"
            "점프 방향은 밧줄 기준으로 어느 쪽에서 점프할지 선택합니다."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        # 현재 위치로 밧줄 X 설정
        set_row = QHBoxLayout()
        btn_set_rope = QPushButton("현재 위치를 밧줄로 설정")
        btn_set_rope.clicked.connect(self._set_rope_from_pos)
        self.lbl_rope_x = QLabel("밧줄 X: -")
        set_row.addWidget(btn_set_rope)
        set_row.addWidget(self.lbl_rope_x)
        set_row.addStretch()
        layout.addLayout(set_row)

        # 이름 / 점프 방향 / 오프셋
        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel("이름"))
        self.edit_rope_name = QLineEdit("밧줄1"); self.edit_rope_name.setFixedWidth(70)
        opt_row.addWidget(self.edit_rope_name)
        opt_row.addSpacing(12)

        opt_row.addWidget(QLabel("점프 키"))
        self.edit_jump_key = QLineEdit("alt"); self.edit_jump_key.setFixedWidth(55)
        self.edit_jump_key.setToolTip("밧줄 올라갈 때 사용할 점프 키 (예: alt, space)")
        opt_row.addWidget(self.edit_jump_key)
        opt_row.addSpacing(12)

        opt_row.addWidget(QLabel("점프 방향"))
        self._rope_approach_group = QButtonGroup(self)
        self.radio_left  = QRadioButton("왼쪽")
        self.radio_both  = QRadioButton("양쪽"); self.radio_both.setChecked(True)
        self.radio_right = QRadioButton("오른쪽")
        for r in [self.radio_left, self.radio_both, self.radio_right]:
            self._rope_approach_group.addButton(r)
            opt_row.addWidget(r)
        opt_row.addSpacing(12)

        opt_row.addWidget(QLabel("오프셋"))
        self.spin_rope_offset = QSpinBox()
        self.spin_rope_offset.setRange(1, 50); self.spin_rope_offset.setValue(15)
        self.spin_rope_offset.setSuffix(" px"); self.spin_rope_offset.setFixedWidth(75)
        opt_row.addWidget(self.spin_rope_offset)
        opt_row.addStretch()
        layout.addLayout(opt_row)

        btn_add_rope = QPushButton("+ 밧줄 추가")
        btn_add_rope.clicked.connect(self._add_rope)
        layout.addWidget(btn_add_rope)

        self.rope_list = QListWidget(); self.rope_list.setMaximumHeight(90)
        layout.addWidget(self.rope_list)

        rope_btn_row = QHBoxLayout()
        btn_del_rope = QPushButton("삭제")
        btn_del_rope.clicked.connect(self._delete_rope)
        btn_rope_save = QPushButton("프리셋에 저장")
        btn_rope_save.clicked.connect(self.save_to_config)
        rope_btn_row.addWidget(btn_del_rope)
        rope_btn_row.addWidget(btn_rope_save)
        rope_btn_row.addStretch()
        layout.addLayout(rope_btn_row)

        return group

    # ── 5. 층별 사냥 설정 ─────────────────────────────────────────────
    def _build_floor_hunt_group(self) -> QGroupBox:
        group = QGroupBox("층별 사냥")
        layout = QVBoxLayout(group)

        # 활성화 체크박스
        row0 = QHBoxLayout()
        self.chk_floor_hunt = QCheckBox("층별 사냥 활성화")
        row0.addWidget(self.chk_floor_hunt)
        row0.addStretch()
        layout.addLayout(row0)

        # 모드 선택
        mode_row = QHBoxLayout()
        self.rb_auto  = QRadioButton("자동 왕복 (1→2→3→2→1)")
        self.rb_route = QRadioButton("수동 루트 (직접 순서 지정)")
        self.rb_auto.setChecked(True)
        mode_row.addWidget(self.rb_auto)
        mode_row.addWidget(self.rb_route)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # 수동 루트 영역
        self._route_widget = QWidget()
        route_lay = QVBoxLayout(self._route_widget)
        route_lay.setContentsMargins(0, 4, 0, 0)

        note = QLabel("순서대로 이동합니다. 마지막 단계 완료 후 처음부터 반복합니다.")
        note.setStyleSheet("color: gray; font-size: 10px;")
        route_lay.addWidget(note)

        self.lst_route = QListWidget()
        self.lst_route.setMaximumHeight(110)
        route_lay.addWidget(self.lst_route)

        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("목적지"))
        self.cmb_route_zone = QComboBox()
        self.cmb_route_zone.setMinimumWidth(80)
        add_row.addWidget(self.cmb_route_zone)
        add_row.addWidget(QLabel("밧줄"))
        self.cmb_route_rope = QComboBox()
        self.cmb_route_rope.setMinimumWidth(80)
        add_row.addWidget(self.cmb_route_rope)
        btn_add_step = QPushButton("+ 추가")
        btn_add_step.setFixedWidth(60)
        btn_add_step.clicked.connect(self._add_route_step)
        add_row.addWidget(btn_add_step)
        btn_del_step = QPushButton("삭제")
        btn_del_step.setFixedWidth(50)
        btn_del_step.clicked.connect(self._del_route_step)
        add_row.addWidget(btn_del_step)
        route_lay.addLayout(add_row)

        layout.addWidget(self._route_widget)
        self._route_widget.setVisible(False)

        self.rb_route.toggled.connect(self._route_widget.setVisible)

        # 저장 버튼
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = QPushButton("저장")
        btn_save.setFixedWidth(55)
        btn_save.clicked.connect(self._save_floor_hunt)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

        return group

    def _refresh_route_combos(self) -> None:
        """구역/밧줄 목록을 콤보박스에 채운다."""
        zones = self.config.get("zones") or []
        ropes = self.config.get("ropes") or []
        self.cmb_route_zone.clear()
        for z in sorted(zones, key=lambda x: x.get("name", "")):
            self.cmb_route_zone.addItem(z.get("name", ""))
        self.cmb_route_rope.clear()
        for r in ropes:
            self.cmb_route_rope.addItem(r.get("name", ""))

    def _add_route_step(self) -> None:
        to_zone = self.cmb_route_zone.currentText()
        rope    = self.cmb_route_rope.currentText()
        if to_zone and rope:
            self.lst_route.addItem(f"→ {to_zone}  (밧줄: {rope})")
            # 아이템에 데이터 저장
            item = self.lst_route.item(self.lst_route.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, {"to_zone": to_zone, "rope": rope})

    def _del_route_step(self) -> None:
        row = self.lst_route.currentRow()
        if row >= 0:
            self.lst_route.takeItem(row)

    def _save_floor_hunt(self) -> None:
        route_mode = self.rb_route.isChecked()
        route = []
        for i in range(self.lst_route.count()):
            data = self.lst_route.item(i).data(Qt.ItemDataRole.UserRole)
            if data:
                route.append(data)
        self.config.set("floor_hunt", "enabled",    self.chk_floor_hunt.isChecked())
        self.config.set("floor_hunt", "route_mode", route_mode)
        self.config.set("floor_hunt", "route",      route)
        self.config.save()

    # ── 드래그 / 단축키 ───────────────────────────────────────────────
    def _select_minimap_region(self) -> None:
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._apply_minimap_region)

    def _apply_minimap_region(self, x: int, y: int, w: int, h: int) -> None:
        self.spin_rx.setValue(x); self.spin_ry.setValue(y)
        self.spin_rw.setValue(w); self.spin_rh.setValue(h)
        self.lbl_mm_hk.setText(f"({x},{y}) {w}×{h}")

    def _apply_mm_hotkey(self, key: str) -> None:
        if not self._hk:
            return
        err = self._hk.register("coord_minimap", key, self._select_minimap_region)
        self.lbl_mm_hk.setText("등록됨" if not err else f"오류:{err}")

    def _select_zone_region(self) -> None:
        """드래그 오버레이로 구역을 지정한다. 화면 좌표를 미니맵 상대 좌표로 변환."""
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._apply_zone_region)

    def _apply_zone_region(self, x: int, y: int, w: int, h: int) -> None:
        """드래그된 화면 영역을 미니맵 기준 좌표로 변환해 경계값을 채운다."""
        rx, ry = self.spin_rx.value(), self.spin_ry.value()
        left_x  = max(0, x - rx)
        right_x = max(0, x + w - rx)
        y_min   = max(0, y - ry)
        y_max   = max(0, y + h - ry)
        self._pending_left_x  = left_x
        self._pending_right_x = right_x
        self.lbl_left.setText(f"왼쪽 X: {left_x}")
        self.lbl_right.setText(f"오른쪽 X: {right_x}")
        self.spin_ymin.setValue(y_min)
        self.spin_ymax.setValue(y_max)
        self.lbl_zone_hk.setText(f"X {left_x}~{right_x}  Y {y_min}~{y_max}")

    def _apply_zone_hotkey(self, key: str) -> None:
        if not self._hk:
            return
        err = self._hk.register("coord_zone", key, self._select_zone_region)
        self.lbl_zone_hk.setText("등록됨" if not err else f"오류:{err}")

    def set_hotkey_manager(self, hk) -> None:
        self._hk = hk
        mm_key = self.btn_mm_hotkey.current_key()
        zone_key = self.btn_zone_hotkey.current_key()
        if mm_key:
            self._apply_mm_hotkey(mm_key)
        if zone_key:
            self._apply_zone_hotkey(zone_key)

    # ── 스포이드 색상 선택 ────────────────────────────────────────────
    def _pick_char_color(self) -> None:
        """전화면 오버레이를 띄워 클릭한 픽셀 색상을 캐릭터 색으로 설정한다."""
        self._overlay = _ColorPickerOverlay()  # GC 방지를 위해 인스턴스 변수로 저장
        self._overlay.color_picked.connect(self._apply_char_color)

    def _apply_char_color(self, r: int, g: int, b: int) -> None:
        self.spin_cr.setValue(r)
        self.spin_cg.setValue(g)
        self.spin_cb.setValue(b)
        self.lbl_pos.setText(f"색상 적용: R{r} G{g} B{b}")

    # ── 캐릭터 위치 ───────────────────────────────────────────────────
    def _fetch_pos(self) -> None:
        self._sync_minimap_config()
        pos = self._minimap_reader.get_character_pos()
        if pos:
            self._last_pos = pos
            self.lbl_pos.setText(f"위치: X={pos[0]}  Y={pos[1]}")
        else:
            self.lbl_pos.setText("위치: 감지 실패")

    def _sync_minimap_config(self) -> None:
        self._minimap_reader.set_config(MinimapConfig(
            region_x=self.spin_rx.value(), region_y=self.spin_ry.value(),
            width=self.spin_rw.value(), height=self.spin_rh.value(),
            char_r=self.spin_cr.value(), char_g=self.spin_cg.value(),
            char_b=self.spin_cb.value(), tolerance=self.spin_tol.value(),
        ))

    # ── 구역 버튼 ─────────────────────────────────────────────────────
    def _set_left(self) -> None:
        if self._last_pos:
            self._pending_left_x = self._last_pos[0]
            self.lbl_left.setText(f"왼쪽 X: {self._pending_left_x}")

    def _set_right(self) -> None:
        if self._last_pos:
            self._pending_right_x = self._last_pos[0]
            self.lbl_right.setText(f"오른쪽 X: {self._pending_right_x}")

    def _refresh_pattern_combo(self) -> None:
        """key_patterns.presets 목록을 공격 패턴 콤보박스에 채운다."""
        current = self.cmb_zone_pattern.currentText()
        self.cmb_zone_pattern.clear()
        self.cmb_zone_pattern.addItem("(기본)")
        presets = self.config.get("key_patterns", "presets") or {}
        for name in sorted(presets.keys()):
            self.cmb_zone_pattern.addItem(name)
        # 이전 선택값 복원
        idx = self.cmb_zone_pattern.findText(current)
        if idx >= 0:
            self.cmb_zone_pattern.setCurrentIndex(idx)

    def _add_zone(self) -> None:
        lx, rx = self._pending_left_x, self._pending_right_x
        if lx is None or rx is None:
            return
        if lx > rx:
            lx, rx = rx, lx
        pat_text = self.cmb_zone_pattern.currentText()
        key_pattern = "" if pat_text == "(기본)" else pat_text
        zone = Zone(
            name=self.edit_zone_name.text() or "구역",
            left_x=lx, right_x=rx,
            y_min=self.spin_ymin.value(), y_max=self.spin_ymax.value(),
            random_margin_min=self.spin_margin_min.value(),
            random_margin_max=self.spin_margin_max.value(),
            sweeps=self.spin_zone_sweeps.value(),
            key_pattern=key_pattern,
        )
        self._zones.append(zone)
        self.zone_list.addItem(zone.label())

    def _delete_zone(self) -> None:
        row = self.zone_list.currentRow()
        if row < 0: return
        self.zone_list.takeItem(row)
        del self._zones[row]

    # ── 밧줄 버튼 ─────────────────────────────────────────────────────
    def _set_rope_from_pos(self) -> None:
        # 버튼 클릭 시 바로 현재 위치를 읽어 사용
        self._sync_minimap_config()
        pos = self._minimap_reader.get_character_pos()
        if pos:
            self._last_pos = pos
            self.lbl_pos.setText(f"위치: X={pos[0]}  Y={pos[1]}")
        if pos or self._last_pos:
            self._pending_rope_x = (pos or self._last_pos)[0]
            self.lbl_rope_x.setText(f"밧줄 X: {self._pending_rope_x}")
        else:
            self.lbl_rope_x.setText("감지 실패 — 미니맵 설정 확인 필요")

    def _approach_str(self) -> str:
        if self.radio_left.isChecked():  return "left"
        if self.radio_right.isChecked(): return "right"
        return "both"

    def _add_rope(self) -> None:
        if self._pending_rope_x is None:
            return
        rope = RopePoint(
            name=self.edit_rope_name.text() or "밧줄",
            x=self._pending_rope_x,
            approach=self._approach_str(),
            jump_offset=self.spin_rope_offset.value(),
        )
        self._ropes.append(rope)
        self.rope_list.addItem(rope.label())

    def _delete_rope(self) -> None:
        row = self.rope_list.currentRow()
        if row < 0: return
        self.rope_list.takeItem(row)
        del self._ropes[row]

    # ── 프리셋 관리 ───────────────────────────────────────────────────
    def _current_preset_dict(self) -> dict:
        """현재 UI 상태를 프리셋 dict로 반환."""
        return {
            "minimap": {
                "region_x": self.spin_rx.value(), "region_y": self.spin_ry.value(),
                "width": self.spin_rw.value(), "height": self.spin_rh.value(),
                "char_r": self.spin_cr.value(), "char_g": self.spin_cg.value(),
                "char_b": self.spin_cb.value(), "tolerance": self.spin_tol.value(),
                "jump_key": self.edit_jump_key.text().strip() or "alt",
                "hotkey_region": self.btn_mm_hotkey.current_key(),
                "hotkey_zone":   self.btn_zone_hotkey.current_key(),
            },
            "zones": [z.to_dict() for z in self._zones],
            "ropes": [r.to_dict() for r in self._ropes],
        }

    def _apply_preset_dict(self, p: dict) -> None:
        """프리셋 dict를 UI에 반영."""
        mm = p.get("minimap", {})
        self.spin_rx.setValue(mm.get("region_x", 0))
        self.spin_ry.setValue(mm.get("region_y", 0))
        self.spin_rw.setValue(mm.get("width", 200))
        self.spin_rh.setValue(mm.get("height", 120))
        self.spin_cr.setValue(mm.get("char_r", 255))
        self.spin_cg.setValue(mm.get("char_g", 255))
        self.spin_cb.setValue(mm.get("char_b", 0))
        self.spin_tol.setValue(mm.get("tolerance", 40))
        self.edit_jump_key.setText(mm.get("jump_key", "alt"))
        self.btn_mm_hotkey.set_key(mm.get("hotkey_region", "f11"))
        self.btn_zone_hotkey.set_key(mm.get("hotkey_zone", "f12"))

        self._zones = [Zone.from_dict(z) for z in p.get("zones", [])]
        self.zone_list.clear()
        for z in self._zones:
            self.zone_list.addItem(z.label())

        self._ropes = [RopePoint.from_dict(r) for r in p.get("ropes", [])]
        self.rope_list.clear()
        for r in self._ropes:
            self.rope_list.addItem(r.label())

    def _save_preset(self) -> None:
        name = self.edit_preset_name.text().strip()
        if not name:
            return
        presets = self.config.get("hunt_grounds", "presets") or {}
        presets[name] = self._current_preset_dict()
        self.config.set("hunt_grounds", "presets", presets)
        self.config.set("hunt_grounds", "active", name)
        self.config.save()
        self._refresh_combo(name)

    def _load_preset(self) -> None:
        name = self.combo_preset.currentText()
        if not name:
            return
        presets = self.config.get("hunt_grounds", "presets") or {}
        if name not in presets:
            return
        self._apply_preset_dict(presets[name])
        self.edit_preset_name.setText(name)
        self.config.set("hunt_grounds", "active", name)

    def _delete_preset(self) -> None:
        name = self.combo_preset.currentText()
        if not name:
            return
        presets = self.config.get("hunt_grounds", "presets") or {}
        if name not in presets:
            return
        reply = QMessageBox.question(self, "삭제 확인", f"'{name}' 프리셋을 삭제하시겠습니까?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        del presets[name]
        self.config.set("hunt_grounds", "presets", presets)
        active = self.config.get("hunt_grounds", "active") or ""
        if active == name:
            self.config.set("hunt_grounds", "active", "")
        self.config.save()
        self._refresh_combo("")

    def _refresh_combo(self, select: str = "") -> None:
        presets = self.config.get("hunt_grounds", "presets") or {}
        self.combo_preset.clear()
        self.combo_preset.addItems(sorted(presets.keys()))
        if select and self.combo_preset.findText(select) >= 0:
            self.combo_preset.setCurrentText(select)

    # ── 저장 / 로드 ───────────────────────────────────────────────────
    def save_to_config(self) -> None:
        """현재 UI 상태를 활성 프리셋으로 저장.
        이름 입력란이 비어 있으면 콤보박스의 현재 선택 프리셋으로 저장."""
        name = self.edit_preset_name.text().strip()
        if not name:
            # 콤보에 선택된 프리셋이 있으면 그것으로 저장
            name = self.combo_preset.currentText().strip()
            if name:
                self.edit_preset_name.setText(name)

        if name:
            self._save_preset()

        # 레거시 키에도 항상 저장 (bot_loop 및 이름 없을 때 호환)
        p = self._current_preset_dict()
        mm = p["minimap"]
        for k, v in mm.items():
            self.config.set("minimap", k, v)
        self.config.set("zones", p["zones"])
        self.config.set("ropes", p.get("ropes", []))
        self.config.save()

    def load_from_config(self) -> None:
        self._refresh_combo(self.config.get("hunt_grounds", "active") or "")

        # 활성 프리셋 로드
        active = self.config.get("hunt_grounds", "active") or ""
        presets = self.config.get("hunt_grounds", "presets") or {}
        if active and active in presets:
            self._apply_preset_dict(presets[active])
            self.edit_preset_name.setText(active)
        else:
            # 레거시 config 로드
            mm = self.config.get("minimap") or {}
            self.spin_rx.setValue(mm.get("region_x", 0))
            self.spin_ry.setValue(mm.get("region_y", 0))
            self.spin_rw.setValue(mm.get("width", 200))
            self.spin_rh.setValue(mm.get("height", 120))
            self.spin_cr.setValue(mm.get("char_r", 255))
            self.spin_cg.setValue(mm.get("char_g", 255))
            self.spin_cb.setValue(mm.get("char_b", 0))
            self.spin_tol.setValue(mm.get("tolerance", 40))
            self.btn_mm_hotkey.set_key(mm.get("hotkey_region", "f11"))
            self.btn_zone_hotkey.set_key(mm.get("hotkey_zone", "f12"))

            raw_zones = self.config.get("zones") or []
            self._zones = [Zone.from_dict(z) for z in raw_zones]
            self.zone_list.clear()
            for z in self._zones:
                self.zone_list.addItem(z.label())

            raw_ropes = self.config.get("ropes") or []
            self._ropes = [RopePoint.from_dict(r) for r in raw_ropes]
            self.rope_list.clear()
            for r in self._ropes:
                self.rope_list.addItem(r.label())

        # 층별 사냥 설정 로드
        fh = self.config.get("floor_hunt") or {}
        self.chk_floor_hunt.setChecked(bool(fh.get("enabled", False)))
        route_mode = bool(fh.get("route_mode", False))
        self.rb_route.setChecked(route_mode)
        self.rb_auto.setChecked(not route_mode)
        self._route_widget.setVisible(route_mode)

        # 루트 목록 복원
        self.lst_route.clear()
        for step in fh.get("route", []):
            to_zone = step.get("to_zone", "")
            rope    = step.get("rope", "")
            item_text = f"→ {to_zone}  (밧줄: {rope})"
            self.lst_route.addItem(item_text)
            item = self.lst_route.item(self.lst_route.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, step)

        # 콤보박스 채우기
        self._refresh_route_combos()
