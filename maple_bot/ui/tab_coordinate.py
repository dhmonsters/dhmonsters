# 醫뚰몴 ??- ?щ깷???꾨━??/ 誘몃땲留?/ 援ъ뿭 / 諛㏃쨪 / 怨듦꺽 ?ㅼ젙 UI
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QSpinBox, QDoubleSpinBox, QPushButton, QListWidget,
    QLineEdit, QFileDialog, QComboBox, QRadioButton,
    QButtonGroup, QScrollArea, QMessageBox, QCheckBox,
    QDialog, QDialogButtonBox, QSlider,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor

from core.minimap_reader import MinimapConfig, Zone, RopePoint, MinimapReader
from core.screen_reader import ScreenReader
from ui.region_selector import RegionSelector
from ui.widgets import HotkeyCapture


class _ZoneEditDialog(QDialog):
    """援ъ뿭 ?띿꽦???몄쭛?섎뒗 ?ㅼ씠?쇰줈洹?"""

    def __init__(self, zone: Zone, pattern_presets: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"援ъ뿭 ?몄쭛 ??{zone.name}")
        self.setMinimumWidth(380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        # ?대쫫
        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("?대쫫"))
        self.edit_name = QLineEdit(zone.name)
        self.edit_name.setFixedWidth(100)
        row_name.addWidget(self.edit_name)
        row_name.addStretch()
        lay.addLayout(row_name)

        # X 踰붿쐞
        row_x = QHBoxLayout()
        row_x.addWidget(QLabel("X 踰붿쐞"))
        self.spin_lx = QSpinBox(); self.spin_lx.setRange(0, 9999); self.spin_lx.setValue(zone.left_x); self.spin_lx.setPrefix("?쇱そ ")
        self.spin_rx = QSpinBox(); self.spin_rx.setRange(0, 9999); self.spin_rx.setValue(zone.right_x); self.spin_rx.setPrefix("?ㅻⅨ履?")
        for w in [self.spin_lx, self.spin_rx]:
            w.setFixedWidth(105); row_x.addWidget(w)
        row_x.addStretch()
        lay.addLayout(row_x)

        # Y 踰붿쐞
        row_y = QHBoxLayout()
        row_y.addWidget(QLabel("Y 踰붿쐞"))
        self.spin_ymin = QSpinBox(); self.spin_ymin.setRange(0, 9999); self.spin_ymin.setValue(zone.y_min); self.spin_ymin.setPrefix("理쒖냼 ")
        self.spin_ymax = QSpinBox(); self.spin_ymax.setRange(0, 9999); self.spin_ymax.setValue(zone.y_max); self.spin_ymax.setPrefix("理쒕? ")
        for w in [self.spin_ymin, self.spin_ymax]:
            w.setFixedWidth(100); row_y.addWidget(w)
        row_y.addStretch()
        lay.addLayout(row_y)

        # ?뺣났 ?잛닔
        row_sw = QHBoxLayout()
        row_sw.addWidget(QLabel("?뺣났 ?잛닔"))
        self.spin_sweeps = QDoubleSpinBox()
        self.spin_sweeps.setRange(0, 99)
        self.spin_sweeps.setSingleStep(0.5)
        self.spin_sweeps.setDecimals(1)
        self.spin_sweeps.setValue(float(zone.sweeps))
        self.spin_sweeps.setToolTip("0 = 통과, 0.5 단위 입력 가능")
        self.spin_sweeps.setFixedWidth(70)
        row_sw.addWidget(self.spin_sweeps)
        row_sw.addWidget(QLabel("?? (0=?듦낵, 0.5 ?⑥쐞)"))
        row_sw.addStretch()
        lay.addLayout(row_sw)

        # ?쒕뜡 ?꾪솚 ?ъ쑀
        row_mg = QHBoxLayout()
        row_mg.addWidget(QLabel("?쒕뜡 ?꾪솚 ?ъ쑀"))
        self.spin_mg_min = QSpinBox(); self.spin_mg_min.setRange(0, 200); self.spin_mg_min.setValue(zone.random_margin_min); self.spin_mg_min.setPrefix("理쒖냼 "); self.spin_mg_min.setSuffix("px"); self.spin_mg_min.setFixedWidth(90)
        self.spin_mg_max = QSpinBox(); self.spin_mg_max.setRange(0, 200); self.spin_mg_max.setValue(zone.random_margin_max); self.spin_mg_max.setPrefix("理쒕? "); self.spin_mg_max.setSuffix("px"); self.spin_mg_max.setFixedWidth(90)
        row_mg.addWidget(self.spin_mg_min)
        row_mg.addWidget(self.spin_mg_max)
        row_mg.addStretch()
        lay.addLayout(row_mg)

        # 怨듦꺽 ?⑦꽩
        row_pat = QHBoxLayout()
        row_pat.addWidget(QLabel("怨듦꺽 ?⑦꽩"))
        self.cmb_pattern = QComboBox()
        self.cmb_pattern.setMinimumWidth(130)
        self.cmb_pattern.addItem("(湲곕낯)")
        for p in sorted(pattern_presets):
            self.cmb_pattern.addItem(p)
        # ?꾩옱 媛??좏깮
        cur = zone.key_pattern or "(湲곕낯)"
        idx = self.cmb_pattern.findText(cur)
        self.cmb_pattern.setCurrentIndex(idx if idx >= 0 else 0)
        row_pat.addWidget(self.cmb_pattern)
        row_pat.addStretch()
        lay.addLayout(row_pat)

        # ?뺤씤 / 痍⑥냼
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def get_zone_data(self) -> dict:
        """?몄쭛??媛믪쓣 dict濡?諛섑솚?쒕떎."""
        pat = self.cmb_pattern.currentText()
        return {
            "name":               self.edit_name.text().strip() or "援ъ뿭",
            "left_x":             self.spin_lx.value(),
            "right_x":            self.spin_rx.value(),
            "y_min":              self.spin_ymin.value(),
            "y_max":              self.spin_ymax.value(),
            "sweeps":             float(self.spin_sweeps.value()),
            "random_margin_min":  self.spin_mg_min.value(),
            "random_margin_max":  self.spin_mg_max.value(),
            "key_pattern":        "" if pat == "(湲곕낯)" else pat,
        }


class _RopeEditDialog(QDialog):
    """諛㏃쨪 ?띿꽦???몄쭛?섎뒗 ?ㅼ씠?쇰줈洹?"""

    def __init__(self, rope: RopePoint, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"諛㏃쨪 ?몄쭛 ??{rope.name}")
        self.setMinimumWidth(340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        # ?대쫫
        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("?대쫫"))
        self.edit_name = QLineEdit(rope.name)
        self.edit_name.setFixedWidth(100)
        row_name.addWidget(self.edit_name)
        row_name.addStretch()
        lay.addLayout(row_name)

        # X 醫뚰몴 (?쎄린 ?꾩슜 ?쒖떆)
        row_x = QHBoxLayout()
        row_x.addWidget(QLabel(f"X 醫뚰몴  {rope.x}  (蹂寃쏀븯?ㅻ㈃ ?ъ텛媛)"))
        row_x.addStretch()
        lay.addLayout(row_x)

        # ?먰봽 諛⑺뼢
        row_ap = QHBoxLayout()
        row_ap.addWidget(QLabel("?먰봽 諛⑺뼢"))
        self._approach_grp = QButtonGroup(self)
        self.rb_left  = QRadioButton("?쇱そ")
        self.rb_both  = QRadioButton("?묒そ")
        self.rb_right = QRadioButton("오른쪽")
        for rb in [self.rb_left, self.rb_both, self.rb_right]:
            self._approach_grp.addButton(rb)
            row_ap.addWidget(rb)
        # ?꾩옱 媛??좏깮
        {"left": self.rb_left, "right": self.rb_right}.get(rope.approach, self.rb_both).setChecked(True)
        row_ap.addStretch()
        lay.addLayout(row_ap)

        # ?먰봽 ?ㅽ봽??
        row_off = QHBoxLayout()
        row_off.addWidget(QLabel("점프 거리"))
        self.spin_offset = QSpinBox()
        self.spin_offset.setRange(1, 50)
        self.spin_offset.setValue(rope.jump_offset)
        self.spin_offset.setSuffix(" px")
        self.spin_offset.setFixedWidth(75)
        row_off.addWidget(self.spin_offset)
        row_off.addStretch()
        lay.addLayout(row_off)

        # ?ㅻⅤ湲??쒓컙
        row_cs = QHBoxLayout()
        row_cs.addWidget(QLabel("?ㅻⅤ湲??쒓컙"))
        self.dspin_climb = QDoubleSpinBox()
        self.dspin_climb.setRange(0.3, 30.0)
        self.dspin_climb.setSingleStep(0.1)
        self.dspin_climb.setDecimals(1)
        self.dspin_climb.setValue(rope.climb_sec)
        self.dspin_climb.setSuffix(" 초")
        self.dspin_climb.setFixedWidth(85)
        self.dspin_climb.setToolTip("諛㏃쨪???꾩쟾???ㅻⅤ????嫄몃━???쒓컙")
        row_cs.addWidget(self.dspin_climb)
        row_cs.addStretch()
        lay.addLayout(row_cs)

        # ?뺤씤 / 痍⑥냼
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def get_rope_data(self) -> dict:
        """?몄쭛??媛믪쓣 dict濡?諛섑솚?쒕떎."""
        if self.rb_left.isChecked():   approach = "left"
        elif self.rb_right.isChecked(): approach = "right"
        else:                           approach = "both"
        return {
            "name":        self.edit_name.text().strip() or "諛㏃쨪",
            "approach":    approach,
            "jump_offset": self.spin_offset.value(),
            "climb_sec":   self.dspin_climb.value(),
        }


class _ColorPickerOverlay(QWidget):
    """?꾪솕硫??щ챸 ?ㅻ쾭?덉씠 ???대┃???쎌? RGB瑜?諛섑솚?섎뒗 ?ㅽ룷?대뱶.

    紐⑤뱺 紐⑤땲?곕? 而ㅻ쾭?섎뒗 媛???곗뒪?ы넲 ?꾩껜 ?곸뿭???ㅻ쾭?덉씠瑜??꾩슫??
    grabKeyboard()濡?ESC ?낅젰??蹂댁옣?쒕떎.
    """
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
        import mss as _mss
        self._sct = _mss.mss()

        # 紐⑤뱺 紐⑤땲?곕? ?⑹튇 媛???곗뒪?ы넲 ?꾩껜 ?곸뿭???ㅻ쾭?덉씠 諛곗튂
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QRect
        total = QRect()
        for screen in QApplication.screens():
            total = total.united(screen.geometry())
        self.setGeometry(total)
        self.show()
        self.raise_()
        self.activateWindow()
        self.grabKeyboard()   # ESC ?낅젰 蹂댁옣

    def closeEvent(self, event):
        self.releaseKeyboard()
        super().closeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 18))
        painter.setPen(QColor(255, 255, 255, 180))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                         "誘몃땲留듭쓽 罹먮┃???꾪듃瑜??대┃?섏꽭??n(ESC: 痍⑥냼)")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            x = int(event.globalPosition().x())
            y = int(event.globalPosition().y())
            # ?ㅻ쾭?덉씠瑜?癒쇱? ?④릿 ??50ms ???쎌? 罹≪쿂 (?ㅻ쾭?덉씠媛 ?붾㈃?먯꽌 ?щ씪吏???罹≪쿂)
            self.hide()
            QTimer.singleShot(50, lambda: self._capture_pixel(x, y))
        else:
            self.close()

    def _capture_pixel(self, x: int, y: int) -> None:
        """?ㅻ쾭?덉씠 ?녿뒗 ?곹깭?먯꽌 ?쎌? ?됱긽??罹≪쿂???쒓렇?먮줈 ?꾨떖?쒕떎."""
        try:
            region = {"left": x, "top": y, "width": 1, "height": 1}
            img = self._sct.grab(region)
            # mss raw 諛붿씠???쒖꽌: B, G, R, A
            b, g, r = img.raw[0], img.raw[1], img.raw[2]
            self.color_picked.emit(r, g, b)
        except Exception:
            pass
        finally:
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
        layout.addWidget(self._build_pickup_timer_group())
        layout.addStretch()

        scroll_area.setWidget(inner)
        outer.addWidget(scroll_area)

        self.load_from_config()

    # ?? 1. ?щ깷???꾨━????????????????????????????????????????????????
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

    # ?? 2. 誘몃땲留??ㅼ젙 ????????????????????????????????????????????????
    def _build_minimap_group(self) -> QGroupBox:
        group = QGroupBox("미니맵 설정")
        layout = QVBoxLayout(group)

        # ?쒕옒洹?+ ?⑥텞??
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

        # ?꾩튂 / ?ш린
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

        # 罹먮┃???꾪듃 ??(?몃???湲곕낯: 255,255,0)
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
        btn_eyedrop.setToolTip("미니맵의 캐릭터 점을 클릭해 색상을 가져옵니다")
        btn_eyedrop.clicked.connect(self._pick_char_color)
        color_row.addWidget(btn_eyedrop)
        color_row.addStretch()
        layout.addLayout(color_row)

        detect_group = QGroupBox("캐릭터 색검출 보정")
        detect_layout = QVBoxLayout(detect_group)
        detect_desc = QLabel(
            "미검출이면 H 범위나 V 최소값을 조절하세요. 배경을 잡으면 S/V 최소값이나 점 크기 최대값을 올리면 됩니다."
        )
        detect_desc.setWordWrap(True)
        detect_layout.addWidget(detect_desc)

        def _add_slider(label: str, attr: str, min_v: int, max_v: int, value: int, suffix: str = ""):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(min_v, max_v)
            slider.setValue(value)
            spin = QSpinBox()
            spin.setRange(min_v, max_v)
            spin.setValue(value)
            spin.setSuffix(suffix)
            spin.setFixedWidth(80)
            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            row.addWidget(slider, 1)
            row.addWidget(spin)
            detect_layout.addLayout(row)
            setattr(self, f"slider_{attr}", slider)
            setattr(self, f"spin_{attr}", spin)

        _add_slider("H 색상 범위", "char_h_tol", 2, 30, 10)
        _add_slider("S 채도 최소", "char_s_min", 40, 255, 100)
        _add_slider("V 밝기 최소", "char_v_min", 80, 255, 200)
        _add_slider("점 크기 최소", "char_area_min", 1, 80, 3)
        _add_slider("점 크기 최대", "char_area_max", 10, 250, 100)
        layout.addWidget(detect_group)

        # ?꾩튂 ?뺤씤
        pos_check = QHBoxLayout()
        btn_pos = QPushButton("현재 위치 좌표 확인")
        btn_pos.clicked.connect(self._fetch_pos)
        self.lbl_pos = QLabel("위치: -")
        self.lbl_pos.setMinimumWidth(160)
        pos_check.addWidget(btn_pos)
        pos_check.addWidget(self.lbl_pos)
        pos_check.addStretch()
        layout.addLayout(pos_check)

        return group

    # ?? 3. 援ъ뿭 ?ㅼ젙 ??????????????????????????????????????????????????
    def _build_zone_group(self) -> QGroupBox:
        group = QGroupBox("구역 설정 (층별 이동 범위)")
        layout = QVBoxLayout(group)

        # ?쒕옒洹몃줈 援ъ뿭 吏??(誘몃땲留??꾩뿉???쒕옒洹????먮룞 蹂??
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

        # 寃쎄퀎 ?쒖떆 (?쒕옒洹??먮뒗 踰꾪듉?쇰줈 梨꾩썙吏?
        boundary = QHBoxLayout()
        btn_left = QPushButton("← 왼쪽 경계")
        btn_right = QPushButton("오른쪽 경계 →")
        btn_left.clicked.connect(self._set_left)
        btn_right.clicked.connect(self._set_right)
        self.lbl_left = QLabel("왼쪽 X: -")
        self.lbl_right = QLabel("오른쪽 X: -")
        boundary.addWidget(btn_left); boundary.addWidget(self.lbl_left)
        boundary.addSpacing(8)
        boundary.addWidget(btn_right); boundary.addWidget(self.lbl_right)
        boundary.addStretch()
        layout.addLayout(boundary)

        # Y 踰붿쐞 / ?대쫫 / ?뺣났 ?잛닔
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
        self.spin_zone_sweeps.setToolTip("이 구역에서 왕복할 횟수입니다. 0은 통과입니다.")
        opt.addWidget(self.spin_zone_sweeps)
        opt.addWidget(QLabel("회"))
        opt.addStretch()
        layout.addLayout(opt)

        # 怨듦꺽 ?⑦꽩 ?좏깮
        pat_row = QHBoxLayout()
        pat_row.addWidget(QLabel("공격 패턴"))
        self.cmb_zone_pattern = QComboBox()
        self.cmb_zone_pattern.setMinimumWidth(120)
        self.cmb_zone_pattern.setToolTip(
            "이 구역에서 사용할 반복 공격 패턴을 선택합니다.\n"
            "전투 탭에서 프리셋으로 저장한 뒤 여기서 선택하세요."
        )
        btn_refresh_pat = QPushButton("새로고침")
        btn_refresh_pat.setFixedWidth(30)
        btn_refresh_pat.setToolTip("전투 탭에 저장한 패턴 목록을 새로고침합니다.")
        btn_refresh_pat.clicked.connect(self._refresh_pattern_combo)
        pat_row.addWidget(self.cmb_zone_pattern)
        pat_row.addWidget(btn_refresh_pat)
        pat_row.addStretch()
        layout.addLayout(pat_row)
        self._refresh_pattern_combo()

        # ?쒕뜡 ?꾪솚 ?ъ쑀 ??寃쎄퀎 吏곸쟾 ?꾩쓽 嫄곕━?먯꽌 諛⑺뼢 ?꾪솚
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
        margin_row.addWidget(QLabel("(0이면 끝까지 이동)"))
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

    # ?? 4. 諛㏃쨪 ?ㅼ젙 ??????????????????????????????????????????????????
    def _build_rope_group(self) -> QGroupBox:
        group = QGroupBox("밧줄 / 로프 설정")
        layout = QVBoxLayout(group)

        note = QLabel(
            "밧줄 X 좌표에 도착하면 점프와 위 방향키로 올라갑니다.\n"
            "점프 방향은 밧줄 기준 어느 쪽에서 접근할지 선택합니다."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        # ?꾩옱 ?꾩튂濡?諛㏃쨪 X ?ㅼ젙
        set_row = QHBoxLayout()
        btn_set_rope = QPushButton("현재 위치를 밧줄로 설정")
        btn_set_rope.clicked.connect(self._set_rope_from_pos)
        self.lbl_rope_x = QLabel("밧줄 X: -")
        set_row.addWidget(btn_set_rope)
        set_row.addWidget(self.lbl_rope_x)
        set_row.addStretch()
        layout.addLayout(set_row)

        # ?대쫫 / ?먰봽 諛⑺뼢 / ?ㅽ봽??
        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel("이름"))
        self.edit_rope_name = QLineEdit("밧줄1"); self.edit_rope_name.setFixedWidth(70)
        opt_row.addWidget(self.edit_rope_name)
        opt_row.addSpacing(12)

        opt_row.addWidget(QLabel("점프 키"))
        self.edit_jump_key = QLineEdit("alt"); self.edit_jump_key.setFixedWidth(55)
        self.edit_jump_key.setToolTip("밧줄을 탈 때 사용할 점프 키입니다. 예: alt, space")
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

        opt_row.addWidget(QLabel("점프 거리"))
        self.spin_rope_offset = QSpinBox()
        self.spin_rope_offset.setRange(1, 50); self.spin_rope_offset.setValue(15)
        self.spin_rope_offset.setSuffix(" px"); self.spin_rope_offset.setFixedWidth(75)
        opt_row.addWidget(self.spin_rope_offset)
        opt_row.addStretch()
        layout.addLayout(opt_row)

        # ?ㅻⅤ湲??쒓컙 ?ㅼ젙
        climb_row = QHBoxLayout()
        climb_row.addWidget(QLabel("오르기 시간"))
        self.dspin_climb_sec = QDoubleSpinBox()
        self.dspin_climb_sec.setRange(0.3, 30.0)
        self.dspin_climb_sec.setSingleStep(0.1)
        self.dspin_climb_sec.setDecimals(1)
        self.dspin_climb_sec.setValue(2.5)
        self.dspin_climb_sec.setSuffix(" 초")
        self.dspin_climb_sec.setFixedWidth(85)
        self.dspin_climb_sec.setToolTip("밧줄을 완전히 오르는 데 걸리는 시간입니다.")
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

    # ?? 5. 痢듬퀎 ?щ깷 ?ㅼ젙 ?????????????????????????????????????????????
    def _build_floor_hunt_group(self) -> QGroupBox:
        group = QGroupBox("층별 사냥")
        layout = QVBoxLayout(group)

        # ?쒖꽦??泥댄겕諛뺤뒪
        row0 = QHBoxLayout()
        self.chk_floor_hunt = QCheckBox("층별 사냥 활성화")
        row0.addWidget(self.chk_floor_hunt)
        row0.addStretch()
        layout.addLayout(row0)

        # 紐⑤뱶 ?좏깮
        mode_row = QHBoxLayout()
        self.rb_auto  = QRadioButton("자동 왕복")
        self.rb_route = QRadioButton("수동 루트")
        self.rb_auto.setChecked(True)
        mode_row.addWidget(self.rb_auto)
        mode_row.addWidget(self.rb_route)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # ?섎룞 猷⑦듃 ?곸뿭
        self._route_widget = QWidget()
        route_lay = QVBoxLayout(self._route_widget)
        route_lay.setContentsMargins(0, 4, 0, 0)

        note = QLabel("위에서 아래 순서대로 이동합니다. 마지막 단계 완료 후 처음부터 반복합니다.")
        note.setStyleSheet("color: gray; font-size: 10px;")
        route_lay.addWidget(note)

        # 由ъ뒪??+ ?곗륫 ?묅넃 踰꾪듉
        list_row = QHBoxLayout()
        self.lst_route = QListWidget()
        self.lst_route.setMaximumHeight(120)
        list_row.addWidget(self.lst_route)

        btn_col = QVBoxLayout()
        btn_up   = QPushButton("▲")
        btn_down = QPushButton("▼")
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

        # ???踰꾪듉
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save = QPushButton("저장")
        btn_save.setFixedWidth(55)
        btn_save.clicked.connect(self._save_floor_hunt)
        btn_row.addWidget(btn_save)
        layout.addLayout(btn_row)

        return group

    def _refresh_route_combos(self) -> None:
        """援ъ뿭/諛㏃쨪 紐⑸줉??肄ㅻ낫諛뺤뒪??梨꾩슫??"""
        zones = self.config.get("zones") or []
        ropes = self.config.get("ropes") or []
        self.cmb_route_zone.clear()
        for z in sorted(zones, key=lambda x: x.get("name", "")):
            self.cmb_route_zone.addItem(z.get("name", ""))
        self.cmb_route_rope.clear()
        for r in ropes:
            self.cmb_route_rope.addItem(r.get("name", ""))
        # ?쎌뾽 ??대㉧ 肄ㅻ낫???숈씪?섍쾶 媛깆떊
        self.cmb_pickup_zone.clear()
        for z in sorted(zones, key=lambda x: x.get("name", "")):
            self.cmb_pickup_zone.addItem(z.get("name", ""))
        self.cmb_pickup_rope.clear()
        for r in ropes:
            self.cmb_pickup_rope.addItem(r.get("name", ""))

    def _add_route_step(self) -> None:
        to_zone = self.cmb_route_zone.currentText()
        rope    = self.cmb_route_rope.currentText()
        if to_zone and rope:
            self.lst_route.addItem(f"→ {to_zone}  (밧줄: {rope})")
            # ?꾩씠?쒖뿉 ?곗씠?????
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

    # ?? ?꾩씠???섏쭛 ??대㉧ ????????????????????????????????????????????
    def _build_pickup_timer_group(self) -> QGroupBox:
        """?꾩씠???섏쭛 ??대㉧ UI."""
        group = QGroupBox("아이템 수집 타이머")
        layout = QVBoxLayout(group)

        note = QLabel(
            "설정한 주기마다 사냥을 잠시 멈추고 수집 루트를 실행합니다.\n"
            "수집 루트는 아래에서 구역과 밧줄 조합으로 지정합니다."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(note)

        row0 = QHBoxLayout()
        self.chk_pickup = QCheckBox("타이머 활성화")
        row0.addWidget(self.chk_pickup)
        row0.addStretch()
        layout.addLayout(row0)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("수집 주기"))
        self.spin_pickup_interval = QSpinBox()
        self.spin_pickup_interval.setRange(10, 600)
        self.spin_pickup_interval.setValue(110)
        self.spin_pickup_interval.setSuffix(" 초")
        self.spin_pickup_interval.setFixedWidth(80)
        row1.addWidget(self.spin_pickup_interval)
        row1.addSpacing(16)
        row1.addWidget(QLabel("픽업 키"))
        self.edit_pickup_key = QLineEdit("z")
        self.edit_pickup_key.setFixedWidth(45)
        row1.addWidget(self.edit_pickup_key)
        row1.addSpacing(16)
        row1.addWidget(QLabel("키 유지"))
        self.dspin_pickup_hold = QDoubleSpinBox()
        self.dspin_pickup_hold.setRange(0.1, 10.0)
        self.dspin_pickup_hold.setSingleStep(0.1)
        self.dspin_pickup_hold.setValue(1.5)
        self.dspin_pickup_hold.setSuffix(" 초")
        self.dspin_pickup_hold.setFixedWidth(75)
        row1.addWidget(self.dspin_pickup_hold)
        row1.addStretch()
        layout.addLayout(row1)

        layout.addWidget(QLabel("수집 루트 (위에서 아래 순서 실행)"))

        list_row = QHBoxLayout()
        self.lst_pickup_route = QListWidget()
        self.lst_pickup_route.setMaximumHeight(100)
        list_row.addWidget(self.lst_pickup_route)

        btn_col = QVBoxLayout()
        btn_pu = QPushButton("▲"); btn_pu.setFixedSize(28, 32)
        btn_pd = QPushButton("▼"); btn_pd.setFixedSize(28, 32)
        btn_pu.clicked.connect(self._pickup_step_up)
        btn_pd.clicked.connect(self._pickup_step_down)
        btn_col.addWidget(btn_pu)
        btn_col.addWidget(btn_pd)
        btn_col.addStretch()
        list_row.addLayout(btn_col)
        layout.addLayout(list_row)

        add_row = QHBoxLayout()
        add_row.addWidget(QLabel("목적지"))
        self.cmb_pickup_zone = QComboBox()
        self.cmb_pickup_zone.setMinimumWidth(80)
        add_row.addWidget(self.cmb_pickup_zone)
        add_row.addWidget(QLabel("밧줄"))
        self.cmb_pickup_rope = QComboBox()
        self.cmb_pickup_rope.setMinimumWidth(80)
        add_row.addWidget(self.cmb_pickup_rope)
        btn_add_pu = QPushButton("+ 추가")
        btn_add_pu.setFixedWidth(60)
        btn_del_pu = QPushButton("삭제")
        btn_del_pu.setFixedWidth(50)
        btn_add_pu.clicked.connect(self._add_pickup_step)
        btn_del_pu.clicked.connect(self._del_pickup_step)
        add_row.addWidget(btn_add_pu)
        add_row.addWidget(btn_del_pu)
        add_row.addStretch()
        layout.addLayout(add_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_save_pu = QPushButton("저장")
        btn_save_pu.setFixedWidth(55)
        btn_save_pu.clicked.connect(self._save_pickup_timer)
        btn_row.addWidget(btn_save_pu)
        layout.addLayout(btn_row)

        return group

    def _add_pickup_step(self) -> None:
        to_zone = self.cmb_pickup_zone.currentText()
        rope    = self.cmb_pickup_rope.currentText()
        if to_zone and rope:
            self.lst_pickup_route.addItem(f"→ {to_zone}  (밧줄: {rope})")
            item = self.lst_pickup_route.item(self.lst_pickup_route.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, {"to_zone": to_zone, "rope": rope})

    def _del_pickup_step(self) -> None:
        row = self.lst_pickup_route.currentRow()
        if row >= 0:
            self.lst_pickup_route.takeItem(row)

    def _pickup_step_up(self) -> None:
        row = self.lst_pickup_route.currentRow()
        if row <= 0:
            return
        item = self.lst_pickup_route.takeItem(row)
        self.lst_pickup_route.insertItem(row - 1, item)
        self.lst_pickup_route.setCurrentRow(row - 1)

    def _pickup_step_down(self) -> None:
        row = self.lst_pickup_route.currentRow()
        if row < 0 or row >= self.lst_pickup_route.count() - 1:
            return
        item = self.lst_pickup_route.takeItem(row)
        self.lst_pickup_route.insertItem(row + 1, item)
        self.lst_pickup_route.setCurrentRow(row + 1)

    def _save_pickup_timer(self) -> None:
        route = []
        for i in range(self.lst_pickup_route.count()):
            data = self.lst_pickup_route.item(i).data(Qt.ItemDataRole.UserRole)
            if data:
                route.append(data)
        self.config.set("pickup_timer", "enabled",      self.chk_pickup.isChecked())
        self.config.set("pickup_timer", "interval_sec", self.spin_pickup_interval.value())
        self.config.set("pickup_timer", "pickup_key",   self.edit_pickup_key.text().strip() or "z")
        self.config.set("pickup_timer", "key_hold_sec", self.dspin_pickup_hold.value())
        self.config.set("pickup_timer", "route",        route)
        self.config.save()

    # ?? ?쒕옒洹?/ ?⑥텞?????????????????????????????????????????????????
    def _select_minimap_region(self) -> None:
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._apply_minimap_region)

    def _apply_minimap_region(self, x: int, y: int, w: int, h: int) -> None:
        from ui.region_selector import logical_to_physical, _copy_text_to_clipboard
        from core.config_manager import get_game_window_rect
        px, py, pw, ph = logical_to_physical(x, y, w, h)
        ox, oy, cw, ch = get_game_window_rect(self.config)
        rx, ry = px - ox, py - oy

        self.spin_rx.setValue(rx); self.spin_ry.setValue(ry)
        self.spin_rw.setValue(pw); self.spin_rh.setValue(ph)

        # minimap ?뱀뀡??利됱떆 ???(鍮꾩쑉 ?ы븿)
        mm = dict(self.config.get("minimap") or {})
        mm.update({"region_x": rx, "region_y": ry, "width": pw, "height": ph})
        if cw > 0 and ch > 0:
            mm.update({
                "region_x_ratio": rx / cw,
                "region_y_ratio": ry / ch,
                "width_ratio":    pw / cw,
                "height_ratio":   ph / ch,
            })
        self.config.set("minimap", mm)
        _copy_text_to_clipboard(
            "minimap={"
            f"'region_x': {rx}, 'region_y': {ry}, "
            f"'width': {pw}, 'height': {ph}"
            "}\n"
            "runtime={"
            f"'left': {rx}, 'top': {ry}, "
            f"'width': {pw}, 'height': {ph}"
            "}\n"
            "screen={"
            f"'left': {px}, 'top': {py}, "
            f"'width': {pw}, 'height': {ph}"
            "}"
        )

        mode = " [비율 저장]" if cw > 0 else ""
        self.lbl_mm_hk.setText(f"({rx},{ry}) {pw}횞{ph}{mode}")

    def _apply_mm_hotkey(self, key: str) -> None:
        if not self._hk:
            return
        err = self._hk.register("coord_minimap", key, self._select_minimap_region)
        self.lbl_mm_hk.setText("등록됨" if not err else f"오류: {err}")

    def _select_zone_region(self) -> None:
        """?쒕옒洹??ㅻ쾭?덉씠濡?援ъ뿭??吏?뺥븳?? ?붾㈃ 醫뚰몴瑜?誘몃땲留??곷? 醫뚰몴濡?蹂??"""
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._apply_zone_region)

    def _apply_zone_region(self, x: int, y: int, w: int, h: int) -> None:
        """?쒕옒洹몃맂 ?붾㈃ ?곸뿭??誘몃땲留?湲곗? 醫뚰몴濡?蹂?섑빐 寃쎄퀎媛믪쓣 梨꾩슫??"""
        from ui.region_selector import logical_to_physical, _copy_text_to_clipboard
        from core.config_manager import resolve_minimap_coords
        px, py, pw, ph = logical_to_physical(x, y, w, h)
        stored_mm = self.config.get("minimap") or {}
        mm_x, mm_y, _, _ = resolve_minimap_coords(self.config, stored_mm)
        left_x  = max(0, px - mm_x)
        right_x = max(0, px + pw - mm_x)
        y_min   = max(0, py - mm_y)
        y_max   = max(0, py + ph - mm_y)
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
        self.lbl_zone_hk.setText("등록됨" if not err else f"오류: {err}")

    def set_hotkey_manager(self, hk) -> None:
        self._hk = hk
        mm_key = self.btn_mm_hotkey.current_key()
        zone_key = self.btn_zone_hotkey.current_key()
        if mm_key:
            self._apply_mm_hotkey(mm_key)
        if zone_key:
            self._apply_zone_hotkey(zone_key)

    # ?? ?ㅽ룷?대뱶 ?됱긽 ?좏깮 ????????????????????????????????????????????
    def _pick_char_color(self) -> None:
        """?꾪솕硫??ㅻ쾭?덉씠瑜??꾩썙 ?대┃???쎌? ?됱긽??罹먮┃???됱쑝濡??ㅼ젙?쒕떎."""
        self._overlay = _ColorPickerOverlay()  # GC 諛⑹?瑜??꾪빐 ?몄뒪?댁뒪 蹂?섎줈 ???
        self._overlay.color_picked.connect(self._apply_char_color)

    def _apply_char_color(self, r: int, g: int, b: int) -> None:
        self.spin_cr.setValue(r)
        self.spin_cg.setValue(g)
        self.spin_cb.setValue(b)
        self.lbl_pos.setText(f"색상 적용: R{r} G{g} B{b}")

    # ?? 罹먮┃???꾩튂 ???????????????????????????????????????????????????
    def _fetch_pos(self) -> None:
        self._sync_minimap_config()
        pos = None
        try:
            from core.sensing.char_scanner import find_char_in_hsv, hsv_range_from_rgb
            frame = self._minimap_reader.capture_minimap()
            area_min = min(self.spin_char_area_min.value(), self.spin_char_area_max.value())
            area_max = max(self.spin_char_area_min.value(), self.spin_char_area_max.value())
            lo, hi = hsv_range_from_rgb(
                self.spin_cr.value(),
                self.spin_cg.value(),
                self.spin_cb.value(),
                h_tol=self.spin_char_h_tol.value(),
                s_min=self.spin_char_s_min.value(),
                v_min=self.spin_char_v_min.value(),
            )
            pos = find_char_in_hsv(frame, lo, hi, area_min, area_max, previous_position=self._last_pos)
        except Exception:
            pos = self._minimap_reader.get_character_pos()
        if pos:
            self._last_pos = pos
            x, y = int(pos[0]), int(pos[1])
            mm_w = max(1, int(self.spin_rw.value()))
            mm_h = max(1, int(self.spin_rh.value()))
            rx = x / mm_w
            ry = y / mm_h
            text = f"현재 위치: X={x}  Y={y} / 상대 X={rx:.4f}, Y={ry:.4f}"
            self.lbl_pos.setText(text)
            try:
                from PyQt6.QtWidgets import QApplication
                QApplication.clipboard().setText(
                    f"X={x}, Y={y}, x_ratio={rx:.4f}, y_ratio={ry:.4f}"
                )
            except Exception:
                pass
        else:
            self.lbl_pos.setText("현재 위치: 감지 실패 - H/S/V/점 크기 보정값을 조절해 주세요")

    def _sync_minimap_config(self) -> None:
        from core.config_manager import resolve_minimap_coords
        stored_mm = self.config.get("minimap") or {}
        region_x, region_y, width, height = resolve_minimap_coords(self.config, stored_mm)
        self._minimap_reader.set_config(MinimapConfig(
            region_x=region_x, region_y=region_y,
            width=width, height=height,
            char_r=self.spin_cr.value(), char_g=self.spin_cg.value(),
            char_b=self.spin_cb.value(), tolerance=self.spin_tol.value(),
        ))

    # ?? 援ъ뿭 踰꾪듉 ?????????????????????????????????????????????????????
    def _set_left(self) -> None:
        if self._last_pos:
            self._pending_left_x = self._last_pos[0]
            self.lbl_left.setText(f"왼쪽 X: {self._pending_left_x}")

    def _set_right(self) -> None:
        if self._last_pos:
            self._pending_right_x = self._last_pos[0]
            self.lbl_right.setText(f"오른쪽 X: {self._pending_right_x}")

    def _refresh_pattern_combo(self) -> None:
        """key_patterns.presets 紐⑸줉??怨듦꺽 ?⑦꽩 肄ㅻ낫諛뺤뒪??梨꾩슫??"""
        current = self.cmb_zone_pattern.currentText()
        self.cmb_zone_pattern.clear()
        self.cmb_zone_pattern.addItem("(기본)")
        presets = self.config.get("key_patterns", "presets") or {}
        for name in sorted(presets.keys()):
            self.cmb_zone_pattern.addItem(name)
        # ?댁쟾 ?좏깮媛?蹂듭썝
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
        key_pattern = "" if pat_text == "(湲곕낯)" else pat_text
        zone = Zone(
            name=self.edit_zone_name.text() or "援ъ뿭",
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
        """援ъ뿭 ?꾩씠???붾툝?대┃ ???몄쭛 ?ㅼ씠?쇰줈洹몃? ?곕떎."""
        row = self.zone_list.row(item)
        if row < 0 or row >= len(self._zones):
            return
        zone = self._zones[row]
        presets = list((self.config.get("key_patterns", "presets") or {}).keys())
        dlg = _ZoneEditDialog(zone, presets, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.get_zone_data()
        # rope_x ??湲곗〈 媛??좎? (?몄쭛 ?ㅼ씠?쇰줈洹?踰붿쐞 諛?
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

    # ?? 諛㏃쨪 踰꾪듉 ?????????????????????????????????????????????????????
    def _set_rope_from_pos(self) -> None:
        # 踰꾪듉 ?대┃ ???ㅼ떆媛?罹먮┃???꾩튂瑜??쎌뼱 諛㏃쨪 X濡??ㅼ젙
        self._sync_minimap_config()
        pos = self._minimap_reader.get_character_pos()
        if pos:
            self._last_pos = pos
            self._pending_rope_x = pos[0]
            self.lbl_pos.setText(f"?꾩튂: X={pos[0]}  Y={pos[1]}")
            self.lbl_rope_x.setText(f"諛㏃쨪 X: {self._pending_rope_x}")
        else:
            self.lbl_rope_x.setText("媛먯? ?ㅽ뙣 ??誘몃땲留??ㅼ젙 ?뺤씤 ?꾩슂")

    def _approach_str(self) -> str:
        if self.radio_left.isChecked():  return "left"
        if self.radio_right.isChecked(): return "right"
        return "both"

    def _add_rope(self) -> None:
        if self._pending_rope_x is None:
            return
        rope = RopePoint(
            name=self.edit_rope_name.text() or "諛㏃쨪",
            x=self._pending_rope_x,
            approach=self._approach_str(),
            jump_offset=self.spin_rope_offset.value(),
            climb_sec=self.dspin_climb_sec.value(),
        )
        self._ropes.append(rope)
        self.rope_list.addItem(rope.label())

    def _edit_rope(self, item) -> None:
        """諛㏃쨪 ?꾩씠???붾툝?대┃ ???몄쭛 ?ㅼ씠?쇰줈洹몃? ?곕떎."""
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
            x=rope.x,                      # X 醫뚰몴??蹂寃?遺덇? ??湲곗〈 媛??좎?
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

    # ?? ?꾨━??愿由????????????????????????????????????????????????????
    def _current_preset_dict(self) -> dict:
        """?꾩옱 UI ?곹깭瑜??꾨━??dict濡?諛섑솚. 鍮꾩쑉 ?ㅺ? ?덉쑝硫??④퍡 蹂댁〈."""
        mm = {
            "region_x": self.spin_rx.value(), "region_y": self.spin_ry.value(),
            "width": self.spin_rw.value(), "height": self.spin_rh.value(),
            "char_r": self.spin_cr.value(), "char_g": self.spin_cg.value(),
            "char_b": self.spin_cb.value(), "tolerance": self.spin_tol.value(),
            "char_h_tol": self.spin_char_h_tol.value(),
            "char_s_min": self.spin_char_s_min.value(),
            "char_v_min": self.spin_char_v_min.value(),
            "char_area_min": self.spin_char_area_min.value(),
            "char_area_max": self.spin_char_area_max.value(),
            "jump_key": self.edit_jump_key.text().strip() or "alt",
            "hotkey_region": self.btn_mm_hotkey.current_key(),
            "hotkey_zone":   self.btn_zone_hotkey.current_key(),
        }
        # config????λ맂 鍮꾩쑉 ?ㅺ? ?덉쑝硫??꾨━?뗭뿉 ?④퍡 ?ы븿
        stored_mm = self.config.get("minimap") or {}
        for k in ("region_x_ratio", "region_y_ratio", "width_ratio", "height_ratio"):
            if k in stored_mm:
                mm[k] = stored_mm[k]

        # 誘몃땲留??꾩옱 ?쎌? ?ш린濡?zone/rope 鍮꾩쑉 怨꾩궛
        mm_w = self.spin_rw.value()
        mm_h = self.spin_rh.value()
        return {
            "minimap": mm,
            "zones": [z.to_dict(mm_w, mm_h) for z in self._zones],
            "ropes": [r.to_dict(mm_w)        for r in self._ropes],
        }

    def _apply_preset_dict(self, p: dict) -> None:
        """?꾨━??dict瑜?UI??諛섏쁺. 鍮꾩쑉 ?ㅺ? ?덉쑝硫??꾩옱 李??ш린濡???궛."""
        from core.config_manager import resolve_minimap_coords
        mm = p.get("minimap", {})

        # 誘몃땲留??꾩튂/?ш린 ??鍮꾩쑉???덉쑝硫??꾩옱 李??ш린濡???궛
        from core.config_manager import get_game_window_rect
        rx = mm.get("region_x", 0)
        ry = mm.get("region_y", 0)
        rw = mm.get("width", 200)
        rh = mm.get("height", 120)
        if mm.get("region_x_ratio") is not None:
            _, _, raw_cw, raw_ch = get_game_window_rect(self.config)
            if raw_cw > 0 and raw_ch > 0:
                rx = int(mm["region_x_ratio"] * raw_cw)
                ry = int(mm["region_y_ratio"] * raw_ch)
                rw = max(1, int(mm.get("width_ratio",  0.1)  * raw_cw))
                rh = max(1, int(mm.get("height_ratio", 0.07) * raw_ch))

        self.spin_rx.setValue(rx); self.spin_ry.setValue(ry)
        self.spin_rw.setValue(rw); self.spin_rh.setValue(rh)
        self.spin_cr.setValue(mm.get("char_r", 255))
        self.spin_cg.setValue(mm.get("char_g", 255))
        self.spin_cb.setValue(mm.get("char_b", 0))
        self.spin_tol.setValue(mm.get("tolerance", 40))
        self.spin_char_h_tol.setValue(int(mm.get("char_h_tol", 10)))
        self.spin_char_s_min.setValue(int(mm.get("char_s_min", 100)))
        self.spin_char_v_min.setValue(int(mm.get("char_v_min", 200)))
        self.spin_char_area_min.setValue(int(mm.get("char_area_min", 3)))
        self.spin_char_area_max.setValue(int(mm.get("char_area_max", 100)))
        self.edit_jump_key.setText(mm.get("jump_key", "alt"))
        self.btn_mm_hotkey.set_key(mm.get("hotkey_region", "f11"))
        self.btn_zone_hotkey.set_key(mm.get("hotkey_zone", "f12"))

        # zone/rope ???꾩옱 誘몃땲留??쎌? ?ш린濡?鍮꾩쑉 ??궛
        mm_w, mm_h = rw, rh
        self._zones = [Zone.from_dict(z, mm_w, mm_h) for z in p.get("zones", [])]
        self.zone_list.clear()
        for z in self._zones:
            self.zone_list.addItem(z.label())

        self._ropes = [RopePoint.from_dict(r, mm_w) for r in p.get("ropes", [])]
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
        reply = QMessageBox.question(self, "??젣 ?뺤씤", f"'{name}' ?꾨━?뗭쓣 ??젣?섏떆寃좎뒿?덇퉴?")
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

    # ?? ???/ 濡쒕뱶 ???????????????????????????????????????????????????
    def save_to_config(self) -> None:
        """?꾩옱 UI ?곹깭瑜??쒖꽦 ?꾨━?뗭쑝濡????
        ?대쫫 ?낅젰???鍮꾩뼱 ?덉쑝硫?肄ㅻ낫諛뺤뒪???꾩옱 ?좏깮 ?꾨━?뗭쑝濡????"""
        name = self.edit_preset_name.text().strip()
        if not name:
            # 肄ㅻ낫???좏깮???꾨━?뗭씠 ?덉쑝硫?洹멸쾬?쇰줈 ???
            name = self.combo_preset.currentText().strip()
            if name:
                self.edit_preset_name.setText(name)

        if name:
            self._save_preset()

        # ?덇굅???ㅼ뿉????긽 ???(bot_loop 諛??대쫫 ?놁쓣 ???명솚)
        p = self._current_preset_dict()
        mm = p["minimap"]
        for k, v in mm.items():
            self.config.set("minimap", k, v)
        self.config.set("zones", p["zones"])
        self.config.set("ropes", p.get("ropes", []))
        self.config.save()

    def load_from_config(self) -> None:
        self._refresh_combo(self.config.get("hunt_grounds", "active") or "")

        # ?쒖꽦 ?꾨━??濡쒕뱶
        active = self.config.get("hunt_grounds", "active") or ""
        presets = self.config.get("hunt_grounds", "presets") or {}
        if active and active in presets:
            self._apply_preset_dict(presets[active])
            self.edit_preset_name.setText(active)
        else:
            # ?덇굅??config 濡쒕뱶
            mm = self.config.get("minimap") or {}
            self.spin_rx.setValue(mm.get("region_x", 0))
            self.spin_ry.setValue(mm.get("region_y", 0))
            self.spin_rw.setValue(mm.get("width", 200))
            self.spin_rh.setValue(mm.get("height", 120))
            self.spin_cr.setValue(mm.get("char_r", 255))
            self.spin_cg.setValue(mm.get("char_g", 255))
            self.spin_cb.setValue(mm.get("char_b", 0))
            self.spin_tol.setValue(mm.get("tolerance", 40))
            self.spin_char_h_tol.setValue(int(mm.get("char_h_tol", 10)))
            self.spin_char_s_min.setValue(int(mm.get("char_s_min", 100)))
            self.spin_char_v_min.setValue(int(mm.get("char_v_min", 200)))
            self.spin_char_area_min.setValue(int(mm.get("char_area_min", 3)))
            self.spin_char_area_max.setValue(int(mm.get("char_area_max", 100)))
            self.btn_mm_hotkey.set_key(mm.get("hotkey_region", "f11"))
            self.btn_zone_hotkey.set_key(mm.get("hotkey_zone", "f12"))

            raw_zones = self.config.get("zones") or []
            mm_w = mm.get("width", 200); mm_h = mm.get("height", 120)
            self._zones = [Zone.from_dict(z, mm_w, mm_h) for z in raw_zones]
            self.zone_list.clear()
            for z in self._zones:
                self.zone_list.addItem(z.label())

            raw_ropes = self.config.get("ropes") or []
            self._ropes = [RopePoint.from_dict(r, mm_w) for r in raw_ropes]
            self.rope_list.clear()
            for r in self._ropes:
                self.rope_list.addItem(r.label())

        # 痢듬퀎 ?щ깷 ?ㅼ젙 濡쒕뱶
        fh = self.config.get("floor_hunt") or {}
        self.chk_floor_hunt.setChecked(bool(fh.get("enabled", False)))
        route_mode = bool(fh.get("route_mode", False))
        self.rb_route.setChecked(route_mode)
        self.rb_auto.setChecked(not route_mode)
        self._route_widget.setVisible(route_mode)

        # 猷⑦듃 紐⑸줉 蹂듭썝
        self.lst_route.clear()
        for step in fh.get("route", []):
            to_zone = step.get("to_zone", "")
            rope    = step.get("rope", "")
            item_text = f"??{to_zone}  (諛㏃쨪: {rope})"
            self.lst_route.addItem(item_text)
            item = self.lst_route.item(self.lst_route.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, step)

        # 肄ㅻ낫諛뺤뒪 梨꾩슦湲?
        self._refresh_route_combos()

        # ?쎌뾽 ??대㉧ ?ㅼ젙 濡쒕뱶
        pt = self.config.get("pickup_timer") or {}
        self.chk_pickup.setChecked(bool(pt.get("enabled", False)))
        self.spin_pickup_interval.setValue(int(pt.get("interval_sec", 110)))
        self.edit_pickup_key.setText(pt.get("pickup_key", "z"))
        self.dspin_pickup_hold.setValue(float(pt.get("key_hold_sec", 1.5)))
        self.lst_pickup_route.clear()
        for step in pt.get("route", []):
            to_zone = step.get("to_zone", "")
            rope    = step.get("rope", "")
            self.lst_pickup_route.addItem(f"??{to_zone}  (諛㏃쨪: {rope})")
            item = self.lst_pickup_route.item(self.lst_pickup_route.count() - 1)
            item.setData(Qt.ItemDataRole.UserRole, step)


