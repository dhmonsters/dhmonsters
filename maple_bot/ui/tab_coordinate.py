# 좌표 탭 - 사냥터 프리셋 / 미니맵 / 구역 / 밧줄 / 공격 설정 UI
from __future__ import annotations
import glob
import os

import cv2
import mss
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QSpinBox, QDoubleSpinBox, QPushButton, QListWidget,
    QLineEdit, QFileDialog, QComboBox, QRadioButton,
    QButtonGroup, QScrollArea, QMessageBox, QCheckBox,
    QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor

from core.minimap_reader import MinimapConfig, Zone, RopePoint, MinimapReader
from core.screen_reader import ScreenReader
from ui.region_selector import RegionSelector
from ui.widgets import HotkeyCapture


class _ZoneEditDialog(QDialog):
    """구역 속성을 편집하는 다이얼로그."""

    def __init__(self, zone: Zone, pattern_presets: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"구역 편집 — {zone.name}")
        self.setMinimumWidth(380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        # 이름
        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("이름"))
        self.edit_name = QLineEdit(zone.name)
        self.edit_name.setFixedWidth(100)
        row_name.addWidget(self.edit_name)
        row_name.addStretch()
        lay.addLayout(row_name)

        # X 범위
        row_x = QHBoxLayout()
        row_x.addWidget(QLabel("X 범위"))
        self.spin_lx = QSpinBox(); self.spin_lx.setRange(0, 9999); self.spin_lx.setValue(zone.left_x); self.spin_lx.setPrefix("왼쪽 ")
        self.spin_rx = QSpinBox(); self.spin_rx.setRange(0, 9999); self.spin_rx.setValue(zone.right_x); self.spin_rx.setPrefix("오른쪽 ")
        for w in [self.spin_lx, self.spin_rx]:
            w.setFixedWidth(105); row_x.addWidget(w)
        row_x.addStretch()
        lay.addLayout(row_x)

        # Y 범위
        row_y = QHBoxLayout()
        row_y.addWidget(QLabel("Y 범위"))
        self.spin_ymin = QSpinBox(); self.spin_ymin.setRange(0, 9999); self.spin_ymin.setValue(zone.y_min); self.spin_ymin.setPrefix("최소 ")
        self.spin_ymax = QSpinBox(); self.spin_ymax.setRange(0, 9999); self.spin_ymax.setValue(zone.y_max); self.spin_ymax.setPrefix("최대 ")
        for w in [self.spin_ymin, self.spin_ymax]:
            w.setFixedWidth(100); row_y.addWidget(w)
        row_y.addStretch()
        lay.addLayout(row_y)

        # 왕복 횟수
        row_sw = QHBoxLayout()
        row_sw.addWidget(QLabel("왕복 횟수"))
        self.spin_sweeps = QDoubleSpinBox()
        self.spin_sweeps.setRange(0, 99)
        self.spin_sweeps.setSingleStep(0.5)
        self.spin_sweeps.setDecimals(1)
        self.spin_sweeps.setValue(float(zone.sweeps))
        self.spin_sweeps.setToolTip("0 = 무제한, 0.5 단위 가능")
        self.spin_sweeps.setFixedWidth(70)
        row_sw.addWidget(self.spin_sweeps)
        row_sw.addWidget(QLabel("회  (0=무제한, 0.5 단위)"))
        row_sw.addStretch()
        lay.addLayout(row_sw)

        # 랜덤 전환 여유
        row_mg = QHBoxLayout()
        row_mg.addWidget(QLabel("랜덤 전환 여유"))
        self.spin_mg_min = QSpinBox(); self.spin_mg_min.setRange(0, 200); self.spin_mg_min.setValue(zone.random_margin_min); self.spin_mg_min.setPrefix("최소 "); self.spin_mg_min.setSuffix("px"); self.spin_mg_min.setFixedWidth(90)
        self.spin_mg_max = QSpinBox(); self.spin_mg_max.setRange(0, 200); self.spin_mg_max.setValue(zone.random_margin_max); self.spin_mg_max.setPrefix("최대 "); self.spin_mg_max.setSuffix("px"); self.spin_mg_max.setFixedWidth(90)
        row_mg.addWidget(self.spin_mg_min)
        row_mg.addWidget(self.spin_mg_max)
        row_mg.addStretch()
        lay.addLayout(row_mg)

        # 공격 패턴
        row_pat = QHBoxLayout()
        row_pat.addWidget(QLabel("공격 패턴"))
        self.cmb_pattern = QComboBox()
        self.cmb_pattern.setMinimumWidth(130)
        self.cmb_pattern.addItem("(기본)")
        for p in sorted(pattern_presets):
            self.cmb_pattern.addItem(p)
        # 현재 값 선택
        cur = zone.key_pattern or "(기본)"
        idx = self.cmb_pattern.findText(cur)
        self.cmb_pattern.setCurrentIndex(idx if idx >= 0 else 0)
        row_pat.addWidget(self.cmb_pattern)
        row_pat.addStretch()
        lay.addLayout(row_pat)

        # 확인 / 취소
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def get_zone_data(self) -> dict:
        """편집된 값을 dict로 반환한다."""
        pat = self.cmb_pattern.currentText()
        return {
            "name":               self.edit_name.text().strip() or "구역",
            "left_x":             self.spin_lx.value(),
            "right_x":            self.spin_rx.value(),
            "y_min":              self.spin_ymin.value(),
            "y_max":              self.spin_ymax.value(),
            "sweeps":             float(self.spin_sweeps.value()),
            "random_margin_min":  self.spin_mg_min.value(),
            "random_margin_max":  self.spin_mg_max.value(),
            "key_pattern":        "" if pat == "(기본)" else pat,
        }


class _RopeEditDialog(QDialog):
    """밧줄 속성을 편집하는 다이얼로그."""

    def __init__(self, rope: RopePoint, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"밧줄 편집 — {rope.name}")
        self.setMinimumWidth(340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        # 이름
        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("이름"))
        self.edit_name = QLineEdit(rope.name)
        self.edit_name.setFixedWidth(100)
        row_name.addWidget(self.edit_name)
        row_name.addStretch()
        lay.addLayout(row_name)

        # X 좌표 (읽기 전용 표시)
        row_x = QHBoxLayout()
        row_x.addWidget(QLabel(f"X 좌표  {rope.x}  (변경하려면 재추가)"))
        row_x.addStretch()
        lay.addLayout(row_x)

        # 점프 방향
        row_ap = QHBoxLayout()
        row_ap.addWidget(QLabel("점프 방향"))
        self._approach_grp = QButtonGroup(self)
        self.rb_left  = QRadioButton("왼쪽")
        self.rb_both  = QRadioButton("양쪽")
        self.rb_right = QRadioButton("오른쪽")
        for rb in [self.rb_left, self.rb_both, self.rb_right]:
            self._approach_grp.addButton(rb)
            row_ap.addWidget(rb)
        # 현재 값 선택
        {"left": self.rb_left, "right": self.rb_right}.get(rope.approach, self.rb_both).setChecked(True)
        row_ap.addStretch()
        lay.addLayout(row_ap)

        # 점프 오프셋
        row_off = QHBoxLayout()
        row_off.addWidget(QLabel("점프 오프셋"))
        self.spin_offset = QSpinBox()
        self.spin_offset.setRange(1, 50)
        self.spin_offset.setValue(rope.jump_offset)
        self.spin_offset.setSuffix(" px")
        self.spin_offset.setFixedWidth(75)
        row_off.addWidget(self.spin_offset)
        row_off.addStretch()
        lay.addLayout(row_off)

        # 오르기 시간
        row_cs = QHBoxLayout()
        row_cs.addWidget(QLabel("오르기 시간"))
        self.dspin_climb = QDoubleSpinBox()
        self.dspin_climb.setRange(0.3, 30.0)
        self.dspin_climb.setSingleStep(0.1)
        self.dspin_climb.setDecimals(1)
        self.dspin_climb.setValue(rope.climb_sec)
        self.dspin_climb.setSuffix(" 초")
        self.dspin_climb.setFixedWidth(85)
        self.dspin_climb.setToolTip("밧줄을 완전히 오르는 데 걸리는 시간")
        row_cs.addWidget(self.dspin_climb)
        row_cs.addStretch()
        lay.addLayout(row_cs)

        # 확인 / 취소
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def get_rope_data(self) -> dict:
        """편집된 값을 dict로 반환한다."""
        if self.rb_left.isChecked():   approach = "left"
        elif self.rb_right.isChecked(): approach = "right"
        else:                           approach = "both"
        return {
            "name":        self.edit_name.text().strip() or "밧줄",
            "approach":    approach,
            "jump_offset": self.spin_offset.value(),
            "climb_sec":   self.dspin_climb.value(),
        }


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
        layout.addWidget(self._build_anti_mob_group())
        layout.addWidget(self._build_town_scroll_group())
        layout.addWidget(self._build_hunting_return_group())
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
        self.spin_zone_sweeps = QDoubleSpinBox()
        self.spin_zone_sweeps.setRange(0, 99)
        self.spin_zone_sweeps.setSingleStep(0.5)
        self.spin_zone_sweeps.setDecimals(1)
        self.spin_zone_sweeps.setValue(2.0)
        self.spin_zone_sweeps.setFixedWidth(65)
        self.spin_zone_sweeps.setToolTip("층별 사냥 시 이 층에서 왕복할 횟수 (0 = 무제한, 0.5 단위)")
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
        self.zone_list.itemDoubleClicked.connect(self._edit_zone)
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

        # 오르기 시간 설정
        climb_row = QHBoxLayout()
        climb_row.addWidget(QLabel("오르기 시간"))
        self.dspin_climb_sec = QDoubleSpinBox()
        self.dspin_climb_sec.setRange(0.3, 30.0)
        self.dspin_climb_sec.setSingleStep(0.1)
        self.dspin_climb_sec.setDecimals(1)
        self.dspin_climb_sec.setValue(2.5)
        self.dspin_climb_sec.setSuffix(" 초")
        self.dspin_climb_sec.setFixedWidth(85)
        self.dspin_climb_sec.setToolTip("밧줄을 완전히 오르는 데 걸리는 시간 (맵마다 다름)")
        climb_row.addWidget(self.dspin_climb_sec)
        climb_row.addWidget(QLabel("(밧줄 길이에 맞게 조정)"))
        climb_row.addStretch()
        layout.addLayout(climb_row)

        btn_add_rope = QPushButton("+ 밧줄 추가")
        btn_add_rope.clicked.connect(self._add_rope)
        layout.addWidget(btn_add_rope)

        self.rope_list = QListWidget(); self.rope_list.setMaximumHeight(90)
        self.rope_list.itemDoubleClicked.connect(self._edit_rope)
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

        # 리스트 + 우측 ↑↓ 버튼
        list_row = QHBoxLayout()
        self.lst_route = QListWidget()
        self.lst_route.setMaximumHeight(120)
        list_row.addWidget(self.lst_route)

        btn_col = QVBoxLayout()
        btn_up   = QPushButton("↑")
        btn_down = QPushButton("↓")
        btn_up.setFixedSize(28, 32)
        btn_down.setFixedSize(28, 32)
        btn_up.setToolTip("선택 항목 위로")
        btn_down.setToolTip("선택 항목 아래로")
        btn_up.clicked.connect(self._route_step_up)
        btn_down.clicked.connect(self._route_step_down)
        btn_col.addWidget(btn_up)
        btn_col.addWidget(btn_down)
        btn_col.addStretch()
        list_row.addLayout(btn_col)
        route_lay.addLayout(list_row)

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

    def _route_step_up(self) -> None:
        row = self.lst_route.currentRow()
        if row <= 0:
            return
        item = self.lst_route.takeItem(row)
        self.lst_route.insertItem(row - 1, item)
        self.lst_route.setCurrentRow(row - 1)

    def _route_step_down(self) -> None:
        row = self.lst_route.currentRow()
        if row < 0 or row >= self.lst_route.count() - 1:
            return
        item = self.lst_route.takeItem(row)
        self.lst_route.insertItem(row + 1, item)
        self.lst_route.setCurrentRow(row + 1)

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
        town_key = self.btn_town_scroll_hk.current_key()
        if mm_key:
            self._apply_mm_hotkey(mm_key)
        if zone_key:
            self._apply_zone_hotkey(zone_key)
        if town_key:
            self._apply_town_scroll_hotkey(town_key)

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
            sweeps=float(self.spin_zone_sweeps.value()),
            key_pattern=key_pattern,
        )
        self._zones.append(zone)
        self.zone_list.addItem(zone.label())

    def _delete_zone(self) -> None:
        row = self.zone_list.currentRow()
        if row < 0: return
        self.zone_list.takeItem(row)
        del self._zones[row]

    def _edit_zone(self, item) -> None:
        """구역 아이템 더블클릭 시 편집 다이얼로그를 연다."""
        row = self.zone_list.row(item)
        if row < 0 or row >= len(self._zones):
            return
        zone = self._zones[row]
        presets = list((self.config.get("key_patterns", "presets") or {}).keys())
        dlg = _ZoneEditDialog(zone, presets, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_zone_data()
        # rope_x 는 기존 값 유지 (편집 다이얼로그 범위 밖)
        updated = Zone(
            name=data["name"],
            left_x=data["left_x"],
            right_x=data["right_x"],
            y_min=data["y_min"],
            y_max=data["y_max"],
            rope_x=zone.rope_x,
            random_margin_min=data["random_margin_min"],
            random_margin_max=data["random_margin_max"],
            sweeps=data["sweeps"],
            key_pattern=data["key_pattern"],
        )
        self._zones[row] = updated
        self.zone_list.item(row).setText(updated.label())

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
            climb_sec=self.dspin_climb_sec.value(),
        )
        self._ropes.append(rope)
        self.rope_list.addItem(rope.label())

    def _edit_rope(self, item) -> None:
        """밧줄 아이템 더블클릭 시 편집 다이얼로그를 연다."""
        row = self.rope_list.row(item)
        if row < 0 or row >= len(self._ropes):
            return
        rope = self._ropes[row]
        dlg = _RopeEditDialog(rope, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_rope_data()
        updated = RopePoint(
            name=data["name"],
            x=rope.x,                      # X 좌표는 변경 불가 — 기존 값 유지
            approach=data["approach"],
            jump_offset=data["jump_offset"],
            climb_sec=data["climb_sec"],
        )
        self._ropes[row] = updated
        self.rope_list.item(row).setText(updated.label())

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

        # 마을 귀환 주문서 설정 저장
        self.config.set("town_scroll", "enabled", self.chk_town_scroll.isChecked())
        self.config.set("town_scroll", "key",     self.edit_town_scroll_key.text().strip())
        self.config.set("town_scroll", "hotkey",  self.btn_town_scroll_hk.current_key() or "")

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

        # 매크로방지몹 설정 로드
        am = self.config.get("anti_mob") or {}
        self.chk_anti_mob.setChecked(bool(am.get("enabled", False)))
        type_map = {"click": 0, "item": 1, "basic": 2}
        self.combo_anti_mob_type.setCurrentIndex(type_map.get(am.get("type", "click"), 0))
        self.spin_anti_mob_x.setValue(int(am.get("target_x", 100)))
        self.edit_anti_mob_keys.setText(am.get("click_keys", "space,enter"))
        self.spin_anti_mob_count.setValue(int(am.get("basic_count", 5)))
        region = am.get("detect_region")
        if region and len(region) == 4:
            x, y, w, h = region
            self.lbl_anti_mob_region.setText(f"탐지 영역: X={x} Y={y} W={w} H={h}")
            self.lbl_anti_mob_region.setStyleSheet("color: green;")
        am_coords = am
        for key, lbl in self._anti_mob_item_coords.items():
            v = am_coords.get(key)
            if v and len(v) == 4:
                lbl.setText(f"X={v[0]} Y={v[1]} W={v[2]} H={v[3]}")
                lbl.setStyleSheet("color: green; font-size: 10px;")
        self._refresh_anti_mob_tpl_label()

        # 마을 귀환 주문서 설정 로드
        ts = self.config.get("town_scroll") or {}
        self.chk_town_scroll.setChecked(bool(ts.get("enabled", False)))
        self.edit_town_scroll_key.setText(ts.get("key", "9"))
        saved_hk = ts.get("hotkey", "")
        if saved_hk:
            self.btn_town_scroll_hk.set_key(saved_hk)

    # ── 6. 매크로방지몹 해제 ──────────────────────────────────────────
    def _build_anti_mob_group(self) -> QGroupBox:
        group = QGroupBox("매크로방지몹 해제")
        layout = QVBoxLayout(group)

        self.chk_anti_mob = QCheckBox("감지 활성화 (방지몹 발견 시 공격 정지 후 해제 동작)")
        layout.addWidget(self.chk_anti_mob)

        # 탐지 이미지
        layout.addWidget(QLabel("── 탐지 이미지 ─────────────────────"))
        tpl_row = QHBoxLayout()
        self.lbl_anti_mob_tpl = QLabel("없음")
        self.lbl_anti_mob_tpl.setStyleSheet("color: gray;")
        btn_tpl_add = QPushButton("+ 추가 캡처")
        btn_tpl_add.setFixedWidth(90)
        btn_tpl_add.setToolTip("방지몹 이미지 부분을 드래그해서 등록합니다. 여러 장 등록 가능.")
        btn_tpl_add.clicked.connect(self._capture_anti_mob_template)
        btn_tpl_del = QPushButton("전체 삭제")
        btn_tpl_del.setFixedWidth(70)
        btn_tpl_del.clicked.connect(self._clear_anti_mob_templates)
        tpl_row.addWidget(self.lbl_anti_mob_tpl)
        tpl_row.addStretch()
        tpl_row.addWidget(btn_tpl_add)
        tpl_row.addWidget(btn_tpl_del)
        layout.addLayout(tpl_row)

        # 탐지 영역
        region_row = QHBoxLayout()
        self.lbl_anti_mob_region = QLabel("탐지 영역: 전체 화면")
        self.lbl_anti_mob_region.setStyleSheet("color: gray;")
        btn_set_region = QPushButton("📍 영역 설정")
        btn_set_region.setFixedWidth(90)
        btn_set_region.setToolTip("방지몹이 나타나는 화면 영역만 좁게 지정하면 오탐이 줄어듭니다.")
        btn_set_region.clicked.connect(self._set_anti_mob_region)
        btn_rst_region = QPushButton("초기화")
        btn_rst_region.setFixedWidth(55)
        btn_rst_region.clicked.connect(self._reset_anti_mob_region)
        region_row.addWidget(self.lbl_anti_mob_region)
        region_row.addStretch()
        region_row.addWidget(btn_set_region)
        region_row.addWidget(btn_rst_region)
        layout.addLayout(region_row)

        # 이동 목표 + 해제 방식
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("이동 목표 (미니맵X)"))
        self.spin_anti_mob_x = QSpinBox()
        self.spin_anti_mob_x.setRange(0, 500)
        self.spin_anti_mob_x.setValue(100)
        self.spin_anti_mob_x.setFixedWidth(65)
        self.spin_anti_mob_x.setToolTip("방지몹 해제 동작을 수행할 미니맵 X 좌표.")
        row1.addWidget(self.spin_anti_mob_x)
        row1.addSpacing(16)
        row1.addWidget(QLabel("해제 방식"))
        self.combo_anti_mob_type = QComboBox()
        self.combo_anti_mob_type.addItems(["클릭형", "아이템 뿌리기형", "기본 공격형"])
        self.combo_anti_mob_type.setFixedWidth(140)
        row1.addWidget(self.combo_anti_mob_type)
        row1.addStretch()
        layout.addLayout(row1)

        # ── 클릭형 패널 ──────────────────────────────────────────────
        self._anti_mob_click_panel = QWidget()
        cp_lay = QVBoxLayout(self._anti_mob_click_panel)
        cp_lay.setContentsMargins(0, 4, 0, 0)
        cp_lay.addWidget(QLabel("── 클릭형: 키 시퀀스 ──────────────────"))
        ck_row = QHBoxLayout()
        ck_row.addWidget(QLabel("키 (쉼표 구분)"))
        self.edit_anti_mob_keys = QLineEdit()
        self.edit_anti_mob_keys.setPlaceholderText("예: space,right,enter")
        ck_row.addWidget(self.edit_anti_mob_keys)
        cp_lay.addLayout(ck_row)
        layout.addWidget(self._anti_mob_click_panel)

        # ── 아이템 뿌리기형 패널 ─────────────────────────────────────
        self._anti_mob_item_panel = QWidget()
        ip_lay = QVBoxLayout(self._anti_mob_item_panel)
        ip_lay.setContentsMargins(0, 4, 0, 0)
        ip_lay.addWidget(QLabel("── 아이템 뿌리기형 좌표 ──────────────"))
        self._anti_mob_item_coords: dict[str, QLabel] = {}
        for key, title in [("item_inv_tab", "인벤토리 기타탭"), ("item_slot", "버릴 아이템 슬롯")]:
            row = QHBoxLayout()
            lbl_t = QLabel(title)
            lbl_t.setFixedWidth(130)
            lbl_v = QLabel("미설정")
            lbl_v.setStyleSheet("color: gray; font-size: 10px;")
            self._anti_mob_item_coords[key] = lbl_v
            btn_s = QPushButton("📍 드래그")
            btn_s.setFixedWidth(78)
            btn_s.clicked.connect(lambda _, k=key: self._set_anti_mob_coord(k))
            btn_r = QPushButton("✕")
            btn_r.setFixedWidth(24)
            btn_r.clicked.connect(lambda _, k=key: self._reset_anti_mob_coord(k))
            row.addWidget(lbl_t)
            row.addWidget(lbl_v)
            row.addStretch()
            row.addWidget(btn_s)
            row.addWidget(btn_r)
            ip_lay.addLayout(row)
        layout.addWidget(self._anti_mob_item_panel)

        # ── 기본 공격형 패널 ──────────────────────────────────────────
        self._anti_mob_basic_panel = QWidget()
        bp_lay = QVBoxLayout(self._anti_mob_basic_panel)
        bp_lay.setContentsMargins(0, 4, 0, 0)
        bp_lay.addWidget(QLabel("── 기본 공격형 ──────────────────────"))
        bc_row = QHBoxLayout()
        bc_row.addWidget(QLabel("공격 횟수"))
        self.spin_anti_mob_count = QSpinBox()
        self.spin_anti_mob_count.setRange(1, 50)
        self.spin_anti_mob_count.setValue(5)
        self.spin_anti_mob_count.setFixedWidth(65)
        bc_row.addWidget(self.spin_anti_mob_count)
        bc_row.addWidget(QLabel("회 (attack 탭의 공격키 사용)"))
        bc_row.addStretch()
        bp_lay.addLayout(bc_row)
        layout.addWidget(self._anti_mob_basic_panel)

        # 저장 버튼
        btn_save = QPushButton("💾 저장")
        btn_save.setFixedWidth(70)
        btn_save.clicked.connect(self._save_anti_mob_settings)
        layout.addWidget(btn_save, alignment=Qt.AlignmentFlag.AlignRight)

        # 방식 변경 시 패널 전환
        self.combo_anti_mob_type.currentIndexChanged.connect(self._on_anti_mob_type_changed)
        self._on_anti_mob_type_changed(0)

        return group

    def _on_anti_mob_type_changed(self, idx: int) -> None:
        self._anti_mob_click_panel.setVisible(idx == 0)
        self._anti_mob_item_panel.setVisible(idx == 1)
        self._anti_mob_basic_panel.setVisible(idx == 2)

    def _refresh_anti_mob_tpl_label(self) -> None:
        count = len(glob.glob("templates/anti_mob_*.png"))
        if count:
            self.lbl_anti_mob_tpl.setText(f"✅ {count}개 등록됨")
            self.lbl_anti_mob_tpl.setStyleSheet("color: green;")
        else:
            self.lbl_anti_mob_tpl.setText("없음 (+ 추가 캡처로 등록하세요)")
            self.lbl_anti_mob_tpl.setStyleSheet("color: gray;")

    def _capture_anti_mob_template(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_anti_mob_template)
        self._anti_mob_tpl_selector = sel
        sel.show()

    def _save_anti_mob_template(self, x: int, y: int, w: int, h: int) -> None:
        os.makedirs("templates", exist_ok=True)
        existing = sorted(glob.glob("templates/anti_mob_*.png"))
        next_num = len(existing) + 1
        path = f"templates/anti_mob_{next_num}.png"
        with mss.mss() as sct:
            raw = sct.grab({"left": x, "top": y, "width": w, "height": h})
            img = cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR)
            cv2.imwrite(path, img)
        self._refresh_anti_mob_tpl_label()
        QMessageBox.information(self, "완료", f"방지몹 템플릿 {next_num}번 저장 완료 ({w}×{h}px)")

    def _clear_anti_mob_templates(self) -> None:
        files = glob.glob("templates/anti_mob_*.png")
        if not files:
            QMessageBox.information(self, "알림", "삭제할 템플릿이 없습니다.")
            return
        reply = QMessageBox.question(
            self, "삭제 확인", f"템플릿 {len(files)}개를 모두 삭제하시겠습니까?"
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for f in files:
            os.remove(f)
        self._refresh_anti_mob_tpl_label()

    def _set_anti_mob_region(self) -> None:
        sel = RegionSelector()
        sel.region_selected.connect(self._save_anti_mob_region)
        self._anti_mob_region_selector = sel
        sel.show()

    def _save_anti_mob_region(self, x: int, y: int, w: int, h: int) -> None:
        self.config.set("anti_mob", "detect_region", [x, y, w, h])
        self.config.save()
        self.lbl_anti_mob_region.setText(f"탐지 영역: X={x} Y={y} W={w} H={h}")
        self.lbl_anti_mob_region.setStyleSheet("color: green;")

    def _reset_anti_mob_region(self) -> None:
        self.config.set("anti_mob", "detect_region", None)
        self.config.save()
        self.lbl_anti_mob_region.setText("탐지 영역: 전체 화면")
        self.lbl_anti_mob_region.setStyleSheet("color: gray;")

    def _set_anti_mob_coord(self, key: str) -> None:
        self._pending_anti_mob_key = key
        sel = RegionSelector()
        sel.region_selected.connect(self._save_anti_mob_coord)
        self._anti_mob_coord_selector = sel
        sel.show()

    def _save_anti_mob_coord(self, x: int, y: int, w: int, h: int) -> None:
        key = self._pending_anti_mob_key
        val = [x, y, w, h]
        self.config.set("anti_mob", key, val)
        self.config.save()
        lbl = self._anti_mob_item_coords.get(key)
        if lbl:
            lbl.setText(f"X={x} Y={y} W={w} H={h}")
            lbl.setStyleSheet("color: green; font-size: 10px;")

    def _reset_anti_mob_coord(self, key: str) -> None:
        self.config.set("anti_mob", key, None)
        self.config.save()
        lbl = self._anti_mob_item_coords.get(key)
        if lbl:
            lbl.setText("미설정")
            lbl.setStyleSheet("color: gray; font-size: 10px;")

    def _save_anti_mob_settings(self) -> None:
        type_map = {"클릭형": "click", "아이템 뿌리기형": "item", "기본 공격형": "basic"}
        self.config.set("anti_mob", "enabled",     self.chk_anti_mob.isChecked())
        self.config.set("anti_mob", "type",        type_map.get(self.combo_anti_mob_type.currentText(), "click"))
        self.config.set("anti_mob", "target_x",    self.spin_anti_mob_x.value())
        self.config.set("anti_mob", "click_keys",  self.edit_anti_mob_keys.text().strip())
        self.config.set("anti_mob", "basic_count", self.spin_anti_mob_count.value())
        self.config.save()
        QMessageBox.information(self, "저장 완료", "매크로방지몹 해제 설정이 저장되었습니다.")

    # ── 7. 마을 귀환 주문서 ───────────────────────────────────────────
    def _build_town_scroll_group(self) -> QGroupBox:
        group = QGroupBox("마을 귀환 주문서")
        layout = QVBoxLayout(group)

        note = QLabel("단축키를 누르면 설정된 키를 눌러 마을로 귀환합니다.")
        note.setStyleSheet("color: gray; font-size: 10px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        row = QHBoxLayout()
        self.chk_town_scroll = QCheckBox("활성화")
        row.addWidget(self.chk_town_scroll)
        row.addSpacing(16)
        row.addWidget(QLabel("귀환 키"))
        self.edit_town_scroll_key = QLineEdit("9")
        self.edit_town_scroll_key.setFixedWidth(55)
        self.edit_town_scroll_key.setToolTip("귀환 주문서가 등록된 단축키 (예: 9, 0, F1)")
        row.addWidget(self.edit_town_scroll_key)
        row.addSpacing(16)
        row.addWidget(QLabel("단축키"))
        self.btn_town_scroll_hk = HotkeyCapture("", self._apply_town_scroll_hotkey)
        row.addWidget(self.btn_town_scroll_hk)
        row.addStretch()
        layout.addLayout(row)

        btn_save = QPushButton("💾 저장")
        btn_save.setFixedWidth(70)
        btn_save.clicked.connect(self._save_town_scroll_settings)
        layout.addWidget(btn_save, alignment=Qt.AlignmentFlag.AlignRight)

        return group

    def _apply_town_scroll_hotkey(self, key: str) -> None:
        """글로벌 단축키 등록 — 눌리면 귀환 키를 입력한다."""
        if not self._hk or not key:
            return

        def _use_scroll():
            if not self.chk_town_scroll.isChecked():
                return
            scroll_key = self.edit_town_scroll_key.text().strip()
            if not scroll_key:
                return
            from core.input_controller import InputController
            InputController("").press_key(scroll_key)

        self._hk.register("town_scroll", key, _use_scroll)

    def _save_town_scroll_settings(self) -> None:
        key = self.edit_town_scroll_key.text().strip()
        hk  = self.btn_town_scroll_hk.current_key() or ""
        self.config.set("town_scroll", "enabled", self.chk_town_scroll.isChecked())
        self.config.set("town_scroll", "key",     key)
        self.config.set("town_scroll", "hotkey",  hk)
        self.config.save()
        if hk and self._hk:
            self._apply_town_scroll_hotkey(hk)
        QMessageBox.information(self, "저장 완료", "마을 귀환 주문서 설정이 저장되었습니다.")

    # ── 8. 사냥터 복귀 (플레이스홀더) ────────────────────────────────
    def _build_hunting_return_group(self) -> QGroupBox:
        group = QGroupBox("사냥터 복귀")
        layout = QVBoxLayout(group)

        self.chk_hunting_return = QCheckBox("활성화")
        layout.addWidget(self.chk_hunting_return)

        note = QLabel("(기능 구현 예정)\n마을 귀환 후 사냥터로 자동 복귀합니다.")
        note.setStyleSheet("color: gray; font-size: 10px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        return group
