# 회복 탭 - HP/MP 포션 자동 사용 및 바 좌표 설정 UI
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QLabel, QSpinBox, QDoubleSpinBox,
    QLineEdit, QPushButton, QScrollArea,
)
from PyQt6.QtCore import Qt

from core.screen_reader import ScreenReader
from ui.region_selector import RegionSelector


class TabRecovery(QWidget):
    def __init__(self, config, hotkey_manager=None):
        super().__init__()
        self.config = config
        self._hk = hotkey_manager
        self._selector = None  # RegionSelector 참조 유지 (GC 방지)
        self._screen = ScreenReader()
        self._build_ui()
        self.load_from_config()

    # ── UI 구성 ───────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(10)

        layout.addWidget(self._build_bar_coord_group())   # ← 맨 위 배치 (먼저 설정해야 포션 감지 작동)
        layout.addWidget(self._build_hp_group())
        layout.addWidget(self._build_mp_group())
        layout.addWidget(self._build_pet_food_group())

        btn_save = QPushButton("설정 저장")
        btn_save.clicked.connect(self.save_to_config)
        layout.addWidget(btn_save)
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        outer = QVBoxLayout(self)
        outer.addWidget(scroll)

    def _build_hp_group(self) -> QGroupBox:
        group = QGroupBox("HP 포션")
        layout = QVBoxLayout(group)

        self.chk_hp = QCheckBox("HP 자동 회복 활성화")
        layout.addWidget(self.chk_hp)

        row = QHBoxLayout()
        row.addWidget(QLabel("HP %이하일 때"))
        self.spin_hp_threshold = QSpinBox()
        self.spin_hp_threshold.setRange(1, 99)
        self.spin_hp_threshold.setValue(70)
        self.spin_hp_threshold.setSuffix(" %")
        self.spin_hp_threshold.setFixedWidth(80)
        row.addWidget(self.spin_hp_threshold)

        row.addSpacing(16)
        row.addWidget(QLabel("포션 키"))
        self.edit_hp_key = QLineEdit("9")
        self.edit_hp_key.setFixedWidth(50)
        row.addWidget(self.edit_hp_key)

        row.addSpacing(16)
        row.addWidget(QLabel("쿨다운"))
        self.spin_hp_cooldown = QDoubleSpinBox()
        self.spin_hp_cooldown.setRange(0.5, 60.0)
        self.spin_hp_cooldown.setValue(3.0)
        self.spin_hp_cooldown.setSingleStep(0.5)
        self.spin_hp_cooldown.setSuffix(" 초")
        self.spin_hp_cooldown.setFixedWidth(80)
        row.addWidget(self.spin_hp_cooldown)
        row.addStretch()
        layout.addLayout(row)

        return group

    def _build_mp_group(self) -> QGroupBox:
        group = QGroupBox("MP 포션")
        layout = QVBoxLayout(group)

        self.chk_mp = QCheckBox("MP 자동 회복 활성화")
        layout.addWidget(self.chk_mp)

        row = QHBoxLayout()
        row.addWidget(QLabel("MP %이하일 때"))
        self.spin_mp_threshold = QSpinBox()
        self.spin_mp_threshold.setRange(1, 99)
        self.spin_mp_threshold.setValue(50)
        self.spin_mp_threshold.setSuffix(" %")
        self.spin_mp_threshold.setFixedWidth(80)
        row.addWidget(self.spin_mp_threshold)

        row.addSpacing(16)
        row.addWidget(QLabel("포션 키"))
        self.edit_mp_key = QLineEdit("0")
        self.edit_mp_key.setFixedWidth(50)
        row.addWidget(self.edit_mp_key)

        row.addSpacing(16)
        row.addWidget(QLabel("쿨다운"))
        self.spin_mp_cooldown = QDoubleSpinBox()
        self.spin_mp_cooldown.setRange(0.5, 60.0)
        self.spin_mp_cooldown.setValue(3.0)
        self.spin_mp_cooldown.setSingleStep(0.5)
        self.spin_mp_cooldown.setSuffix(" 초")
        self.spin_mp_cooldown.setFixedWidth(80)
        row.addWidget(self.spin_mp_cooldown)
        row.addStretch()
        layout.addLayout(row)

        return group

    def _build_pet_food_group(self) -> QGroupBox:
        group = QGroupBox("펫먹이 포션")
        layout = QVBoxLayout(group)

        self.chk_pet_food = QCheckBox("펫먹이 자동 급여 활성화")
        layout.addWidget(self.chk_pet_food)

        row = QHBoxLayout()
        row.addWidget(QLabel("펫 마리수"))
        self.spin_pet_count = QSpinBox()
        self.spin_pet_count.setRange(1, 3)
        self.spin_pet_count.setValue(1)
        self.spin_pet_count.setFixedWidth(55)
        row.addWidget(self.spin_pet_count)

        row.addSpacing(16)
        row.addWidget(QLabel("먹이 키"))
        self.edit_pet_key = QLineEdit()
        self.edit_pet_key.setPlaceholderText("예: z")
        self.edit_pet_key.setFixedWidth(50)
        row.addWidget(self.edit_pet_key)

        row.addSpacing(16)
        row.addWidget(QLabel("간격"))
        self.spin_pet_interval = QSpinBox()
        self.spin_pet_interval.setRange(1, 120)
        self.spin_pet_interval.setValue(20)
        self.spin_pet_interval.setSuffix(" 분")
        self.spin_pet_interval.setFixedWidth(75)
        row.addWidget(self.spin_pet_interval)
        row.addWidget(QLabel("(15~30분 사이 추천)"))
        row.addStretch()
        layout.addLayout(row)

        return group

    def _build_bar_coord_group(self) -> QGroupBox:
        group = QGroupBox("① HP / MP 바 좌표 설정  ← 먼저 설정하세요")
        group.setStyleSheet("QGroupBox { font-weight: bold; }")
        layout = QVBoxLayout(group)

        note = QLabel("게임 인터페이스의 HP/MP 바를 드래그해서 지정합니다. (포션 자동사용의 전제조건)")
        note.setStyleSheet("color: #555; font-size: 10px;")
        note.setWordWrap(True)
        layout.addWidget(note)

        # ── HP 바 ──
        hp_header = QHBoxLayout()
        hp_header.addWidget(QLabel("HP 바"))
        self.lbl_hp_status = QLabel("미설정")
        self.lbl_hp_status.setStyleSheet("color: red;")
        hp_header.addWidget(self.lbl_hp_status)
        hp_header.addStretch()
        layout.addLayout(hp_header)

        hp_row = QHBoxLayout()
        self.spin_hp_x = QSpinBox(); self.spin_hp_x.setRange(0, 9999); self.spin_hp_x.setPrefix("X ")
        self.spin_hp_y = QSpinBox(); self.spin_hp_y.setRange(0, 9999); self.spin_hp_y.setPrefix("Y ")
        self.spin_hp_w = QSpinBox(); self.spin_hp_w.setRange(0, 2000); self.spin_hp_w.setPrefix("너비 ")
        for w in [self.spin_hp_x, self.spin_hp_y, self.spin_hp_w]:
            w.setFixedWidth(90)
            hp_row.addWidget(w)
        btn_hp_sel = QPushButton("📍 HP 영역 지정")
        btn_hp_sel.setFixedHeight(30)
        btn_hp_sel.setStyleSheet("QPushButton { background-color: #c0392b; color: white; font-weight: bold; border-radius: 4px; } QPushButton:hover { background-color: #e74c3c; }")
        btn_hp_sel.clicked.connect(lambda: self._select_bar_region("hp"))
        btn_hp_reset = QPushButton("초기화")
        btn_hp_reset.setFixedWidth(55)
        btn_hp_reset.clicked.connect(lambda: self._reset_bar_region("hp"))
        hp_row.addWidget(btn_hp_sel)
        hp_row.addWidget(btn_hp_reset)
        hp_row.addStretch()
        layout.addLayout(hp_row)

        layout.addWidget(QLabel("✔ 색상 자동 감지 (빨간=HP / 파란=MP)"))

        # ── MP 바 ──
        layout.addSpacing(4)
        mp_header = QHBoxLayout()
        mp_header.addWidget(QLabel("MP 바"))
        self.lbl_mp_status = QLabel("미설정")
        self.lbl_mp_status.setStyleSheet("color: red;")
        mp_header.addWidget(self.lbl_mp_status)
        mp_header.addStretch()
        layout.addLayout(mp_header)

        mp_row = QHBoxLayout()
        self.spin_mp_x = QSpinBox(); self.spin_mp_x.setRange(0, 9999); self.spin_mp_x.setPrefix("X ")
        self.spin_mp_y = QSpinBox(); self.spin_mp_y.setRange(0, 9999); self.spin_mp_y.setPrefix("Y ")
        self.spin_mp_w = QSpinBox(); self.spin_mp_w.setRange(0, 2000); self.spin_mp_w.setPrefix("너비 ")
        for w in [self.spin_mp_x, self.spin_mp_y, self.spin_mp_w]:
            w.setFixedWidth(90)
            mp_row.addWidget(w)
        btn_mp_sel = QPushButton("📍 MP 영역 지정")
        btn_mp_sel.setFixedHeight(30)
        btn_mp_sel.setStyleSheet("QPushButton { background-color: #2980b9; color: white; font-weight: bold; border-radius: 4px; } QPushButton:hover { background-color: #3498db; }")
        btn_mp_sel.clicked.connect(lambda: self._select_bar_region("mp"))
        btn_mp_reset = QPushButton("초기화")
        btn_mp_reset.setFixedWidth(55)
        btn_mp_reset.clicked.connect(lambda: self._reset_bar_region("mp"))
        mp_row.addWidget(btn_mp_sel)
        mp_row.addWidget(btn_mp_reset)
        mp_row.addStretch()
        layout.addLayout(mp_row)

        # 현재 HP/MP 비율 실시간 확인
        test_row = QHBoxLayout()
        btn_test = QPushButton("현재 HP/MP % 확인")
        btn_test.clicked.connect(self._test_ratio)
        self.lbl_ratio = QLabel("HP: -  MP: -")
        test_row.addWidget(btn_test)
        test_row.addWidget(self.lbl_ratio)
        test_row.addStretch()
        layout.addLayout(test_row)

        return group

    def _select_bar_region(self, bar_type: str) -> None:
        """RegionSelector로 HP 또는 MP 바 영역을 드래그 지정.

        relative 모드: 창 크기 대비 비율로 저장 → 창 이동/크기 변경 모두 대응.
        absolute 모드: 픽셀 절대 좌표로 저장.
        """
        from core.config_manager import get_game_window_rect

        def _on_selected(x: int, y: int, w: int, h: int) -> None:
            ox, oy, cw, ch = get_game_window_rect(self.config)

            if cw > 0 and ch > 0:
                # relative 모드 — 논리 좌표 기준 비율로 저장
                x_ratio = (x - ox) / cw
                y_ratio = (y - oy) / ch
                w_ratio = w / cw
                coord = {"x_ratio": x_ratio, "y_ratio": y_ratio, "width_ratio": w_ratio}
                rx, ry, rw = int(x - ox), int(y - oy), w
            else:
                # absolute 모드 — 논리 절대 좌표로 저장
                coord = {"x": x, "y": y, "width": w}
                rx, ry, rw = x, y, w

            if bar_type == "hp":
                self.spin_hp_x.setValue(rx)
                self.spin_hp_y.setValue(ry)
                self.spin_hp_w.setValue(rw)
                self.config.set("coordinate", "hp", coord)
            else:
                self.spin_mp_x.setValue(rx)
                self.spin_mp_y.setValue(ry)
                self.spin_mp_w.setValue(rw)
                self.config.set("coordinate", "mp", coord)

            self.config.save()
            label = "HP" if bar_type == "hp" else "MP"
            mode  = "비율 저장" if cw > 0 else "픽셀 저장"
            self.lbl_ratio.setText(f"{label} 바 좌표 {mode} ✓")
            self._refresh_bar_status()

        self._selector = RegionSelector()
        self._selector.region_selected.connect(_on_selected)
        self._selector.show()

    def _reset_bar_region(self, bar_type: str) -> None:
        """HP 또는 MP 바 좌표를 초기화한다."""
        empty = {"x": 0, "y": 0, "width": 0}
        if bar_type == "hp":
            self.config.set("coordinate", "hp", empty)
            self.spin_hp_x.setValue(0); self.spin_hp_y.setValue(0); self.spin_hp_w.setValue(0)
        else:
            self.config.set("coordinate", "mp", empty)
            self.spin_mp_x.setValue(0); self.spin_mp_y.setValue(0); self.spin_mp_w.setValue(0)
        self.config.save()
        self._refresh_bar_status()
        self.lbl_ratio.setText("HP: -  MP: -")

    def _refresh_bar_status(self) -> None:
        """HP/MP 설정 상태 레이블을 갱신한다."""
        hp = self.config.get("coordinate", "hp") or {}
        if hp.get("x_ratio") is not None or hp.get("width", 0) > 0:
            self.lbl_hp_status.setText("✔ 설정됨")
            self.lbl_hp_status.setStyleSheet("color: green;")
        else:
            self.lbl_hp_status.setText("미설정")
            self.lbl_hp_status.setStyleSheet("color: red;")

        mp = self.config.get("coordinate", "mp") or {}
        if mp.get("x_ratio") is not None or mp.get("width", 0) > 0:
            self.lbl_mp_status.setText("✔ 설정됨")
            self.lbl_mp_status.setStyleSheet("color: green;")
        else:
            self.lbl_mp_status.setText("미설정")
            self.lbl_mp_status.setStyleSheet("color: red;")

    # ── HP/MP 비율 테스트 ─────────────────────────────────────────────
    def _test_ratio(self) -> None:
        hp_coord = self.config.get("coordinate", "hp") or {}
        mp_coord = self.config.get("coordinate", "mp") or {}
        hp_set = hp_coord.get("x_ratio") is not None or hp_coord.get("width", 0) > 0
        mp_set = mp_coord.get("x_ratio") is not None or mp_coord.get("width", 0) > 0
        if not hp_set and not mp_set:
            self.lbl_ratio.setText("⚠ HP/MP 바 좌표가 설정되지 않았습니다. '영역 지정'으로 먼저 설정하세요.")
            return
        from core.detector import Detector
        detector = Detector(self._screen, self.config)
        hp = detector.hp_ratio()
        mp = detector.mp_ratio()
        hp_str = f"{hp*100:.0f}%" if hp_set else "미설정"
        mp_str = f"{mp*100:.0f}%" if mp_set else "미설정"
        self.lbl_ratio.setText(f"HP: {hp_str}  MP: {mp_str}")

    def set_hotkey_manager(self, hk) -> None:
        self._hk = hk

    # ── 저장 / 로드 ───────────────────────────────────────────────────
    def save_to_config(self) -> None:
        self.config.set("recovery", "hp_potion", {
            "enabled":      self.chk_hp.isChecked(),
            "threshold":    self.spin_hp_threshold.value(),
            "key":          self.edit_hp_key.text().strip() or "9",
            "cooldown_sec": self.spin_hp_cooldown.value(),
        })
        self.config.set("recovery", "mp_potion", {
            "enabled":      self.chk_mp.isChecked(),
            "threshold":    self.spin_mp_threshold.value(),
            "key":          self.edit_mp_key.text().strip() or "0",
            "cooldown_sec": self.spin_mp_cooldown.value(),
        })
        self.config.set("recovery", "pet_food", {
            "enabled":      self.chk_pet_food.isChecked(),
            "pet_count":    self.spin_pet_count.value(),
            "key":          self.edit_pet_key.text().strip(),
            "interval_min": self.spin_pet_interval.value(),
        })
        # 비율 좌표가 이미 저장된 경우 스핀박스 픽셀값으로 덮어쓰지 않음
        # (비율 저장은 _select_bar_region에서 직접 처리)
        if self.config.get("coordinate", "hp", "x_ratio") is None:
            self.config.set("coordinate", "hp", {
                "x":     self.spin_hp_x.value(),
                "y":     self.spin_hp_y.value(),
                "width": self.spin_hp_w.value(),
            })
        if self.config.get("coordinate", "mp", "x_ratio") is None:
            self.config.set("coordinate", "mp", {
                "x":     self.spin_mp_x.value(),
                "y":     self.spin_mp_y.value(),
                "width": self.spin_mp_w.value(),
            })
        self.config.save()

    def load_from_config(self) -> None:
        hp = self.config.get("recovery", "hp_potion") or {}
        self.chk_hp.setChecked(hp.get("enabled", False))
        self.spin_hp_threshold.setValue(hp.get("threshold", 70))
        self.edit_hp_key.setText(hp.get("key", "9"))
        self.spin_hp_cooldown.setValue(hp.get("cooldown_sec", 3.0))

        mp = self.config.get("recovery", "mp_potion") or {}
        self.chk_mp.setChecked(mp.get("enabled", False))
        self.spin_mp_threshold.setValue(mp.get("threshold", 50))
        self.edit_mp_key.setText(mp.get("key", "0"))
        self.spin_mp_cooldown.setValue(mp.get("cooldown_sec", 3.0))

        pet = self.config.get("recovery", "pet_food") or {}
        self.chk_pet_food.setChecked(pet.get("enabled", False))
        self.spin_pet_count.setValue(pet.get("pet_count", 1))
        self.edit_pet_key.setText(pet.get("key", ""))
        self.spin_pet_interval.setValue(pet.get("interval_min", 20))

        from core.config_manager import get_game_window_rect
        _, _, cw, ch = get_game_window_rect(self.config)

        hp_coord = self.config.get("coordinate", "hp") or {}
        if hp_coord.get("x_ratio") is not None and cw > 0 and ch > 0:
            self.spin_hp_x.setValue(int(hp_coord["x_ratio"] * cw))
            self.spin_hp_y.setValue(int(hp_coord["y_ratio"] * ch))
            self.spin_hp_w.setValue(int(hp_coord["width_ratio"] * cw))
        else:
            self.spin_hp_x.setValue(hp_coord.get("x", 0))
            self.spin_hp_y.setValue(hp_coord.get("y", 0))
            self.spin_hp_w.setValue(hp_coord.get("width", 0))

        mp_coord = self.config.get("coordinate", "mp") or {}
        if mp_coord.get("x_ratio") is not None and cw > 0 and ch > 0:
            self.spin_mp_x.setValue(int(mp_coord["x_ratio"] * cw))
            self.spin_mp_y.setValue(int(mp_coord["y_ratio"] * ch))
            self.spin_mp_w.setValue(int(mp_coord["width_ratio"] * cw))
        else:
            self.spin_mp_x.setValue(mp_coord.get("x", 0))
            self.spin_mp_y.setValue(mp_coord.get("y", 0))
            self.spin_mp_w.setValue(mp_coord.get("width", 0))

        self._refresh_bar_status()

