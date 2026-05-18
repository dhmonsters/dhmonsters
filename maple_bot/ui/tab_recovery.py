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

        layout.addWidget(self._build_hp_group())
        layout.addWidget(self._build_mp_group())
        layout.addWidget(self._build_pet_food_group())
        layout.addWidget(self._build_bar_coord_group())

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
        group = QGroupBox("HP / MP 바 좌표 설정")
        layout = QVBoxLayout(group)

        note = QLabel(
            "드래그로 HP/MP 바 영역을 선택하거나 단축키를 설정해 게임 화면에서 직접 지정하세요."
        )
        note.setWordWrap(True)
        layout.addWidget(note)

        # ── HP 바 ──
        layout.addWidget(QLabel("HP 바"))

        hp_btn_row = QHBoxLayout()
        btn_hp = QPushButton("드래그로 HP 바 지정")
        btn_hp.clicked.connect(self._select_hp_region)
        hp_btn_row.addWidget(btn_hp)
        hp_btn_row.addSpacing(12)
        hp_btn_row.addWidget(QLabel("단축키"))
        self.edit_hp_hotkey = QLineEdit()
        self.edit_hp_hotkey.setPlaceholderText("예: f9")
        self.edit_hp_hotkey.setFixedWidth(70)
        btn_hp_hk = QPushButton("적용")
        btn_hp_hk.setFixedWidth(45)
        btn_hp_hk.clicked.connect(self._apply_hp_hotkey)
        self.edit_hp_hotkey.returnPressed.connect(self._apply_hp_hotkey)
        self.lbl_hp_hk_status = QLabel("")
        hp_btn_row.addWidget(self.edit_hp_hotkey)
        hp_btn_row.addWidget(btn_hp_hk)
        hp_btn_row.addWidget(self.lbl_hp_hk_status)
        hp_btn_row.addStretch()
        layout.addLayout(hp_btn_row)

        hp_spin_row = QHBoxLayout()
        self.spin_hp_x = QSpinBox(); self.spin_hp_x.setRange(0, 9999); self.spin_hp_x.setPrefix("X ")
        self.spin_hp_y = QSpinBox(); self.spin_hp_y.setRange(0, 9999); self.spin_hp_y.setPrefix("Y ")
        self.spin_hp_w = QSpinBox(); self.spin_hp_w.setRange(0, 2000); self.spin_hp_w.setPrefix("너비 ")
        for w in [self.spin_hp_x, self.spin_hp_y, self.spin_hp_w]:
            w.setFixedWidth(90)
            hp_spin_row.addWidget(w)
        hp_spin_row.addStretch()
        layout.addLayout(hp_spin_row)

        # HSV 자동 감지 — 별도 색상 샘플링 불필요
        layout.addWidget(QLabel("✔ 색상 자동 감지 (빨간=HP / 파란=MP, 흰색 텍스트 자동 제외)"))

        # ── MP 바 ──
        layout.addSpacing(6)
        layout.addWidget(QLabel("MP 바"))

        mp_btn_row = QHBoxLayout()
        btn_mp = QPushButton("드래그로 MP 바 지정")
        btn_mp.clicked.connect(self._select_mp_region)
        mp_btn_row.addWidget(btn_mp)
        mp_btn_row.addSpacing(12)
        mp_btn_row.addWidget(QLabel("단축키"))
        self.edit_mp_hotkey = QLineEdit()
        self.edit_mp_hotkey.setPlaceholderText("예: f10")
        self.edit_mp_hotkey.setFixedWidth(70)
        btn_mp_hk = QPushButton("적용")
        btn_mp_hk.setFixedWidth(45)
        btn_mp_hk.clicked.connect(self._apply_mp_hotkey)
        self.edit_mp_hotkey.returnPressed.connect(self._apply_mp_hotkey)
        self.lbl_mp_hk_status = QLabel("")
        mp_btn_row.addWidget(self.edit_mp_hotkey)
        mp_btn_row.addWidget(btn_mp_hk)
        mp_btn_row.addWidget(self.lbl_mp_hk_status)
        mp_btn_row.addStretch()
        layout.addLayout(mp_btn_row)

        mp_spin_row = QHBoxLayout()
        self.spin_mp_x = QSpinBox(); self.spin_mp_x.setRange(0, 9999); self.spin_mp_x.setPrefix("X ")
        self.spin_mp_y = QSpinBox(); self.spin_mp_y.setRange(0, 9999); self.spin_mp_y.setPrefix("Y ")
        self.spin_mp_w = QSpinBox(); self.spin_mp_w.setRange(0, 2000); self.spin_mp_w.setPrefix("너비 ")
        for w in [self.spin_mp_x, self.spin_mp_y, self.spin_mp_w]:
            w.setFixedWidth(90)
            mp_spin_row.addWidget(w)
        mp_spin_row.addStretch()
        layout.addLayout(mp_spin_row)


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

    # ── HP/MP 비율 테스트 ─────────────────────────────────────────────
    def _test_ratio(self) -> None:
        """현재 화면에서 HP/MP 비율을 읽어 표시한다."""
        from core.detector import Detector
        from core.config_manager import ConfigManager
        detector = Detector(self._screen, self.config)
        hp = detector.hp_ratio()
        mp = detector.mp_ratio()
        self.lbl_ratio.setText(f"HP: {hp*100:.0f}%  MP: {mp*100:.0f}%")

    # ── 드래그 선택 ───────────────────────────────────────────────────
    def _select_hp_region(self) -> None:
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._apply_hp_region)

    def _select_mp_region(self) -> None:
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._apply_mp_region)

    def _apply_hp_region(self, x: int, y: int, w: int, h: int) -> None:
        self.spin_hp_x.setValue(x)
        self.spin_hp_y.setValue(y + h // 2)
        self.spin_hp_w.setValue(w)

    def _apply_mp_region(self, x: int, y: int, w: int, h: int) -> None:
        self.spin_mp_x.setValue(x)
        self.spin_mp_y.setValue(y + h // 2)
        self.spin_mp_w.setValue(w)

    # ── 단축키 등록 ───────────────────────────────────────────────────
    def _apply_hp_hotkey(self) -> None:
        if not self._hk:
            self.lbl_hp_hk_status.setText("단축키 매니저 없음")
            return
        key = self.edit_hp_hotkey.text().strip()
        err = self._hk.register("recovery_hp", key, self._select_hp_region)
        self.lbl_hp_hk_status.setText("등록됨" if not err else f"오류: {err}")

    def _apply_mp_hotkey(self) -> None:
        if not self._hk:
            self.lbl_mp_hk_status.setText("단축키 매니저 없음")
            return
        key = self.edit_mp_hotkey.text().strip()
        err = self._hk.register("recovery_mp", key, self._select_mp_region)
        self.lbl_mp_hk_status.setText("등록됨" if not err else f"오류: {err}")

    def set_hotkey_manager(self, hk) -> None:
        self._hk = hk
        # 저장된 단축키가 있으면 자동 등록
        if self.edit_hp_hotkey.text().strip():
            self._apply_hp_hotkey()
        if self.edit_mp_hotkey.text().strip():
            self._apply_mp_hotkey()

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
        self.config.set("recovery", "hotkeys", {
            "hp": self.edit_hp_hotkey.text().strip(),
            "mp": self.edit_mp_hotkey.text().strip(),
        })
        self.config.set("coordinate", "hp", {
            "x": self.spin_hp_x.value(),
            "y": self.spin_hp_y.value(),
            "width": self.spin_hp_w.value(),
        })
        self.config.set("coordinate", "mp", {
            "x": self.spin_mp_x.value(),
            "y": self.spin_mp_y.value(),
            "width": self.spin_mp_w.value(),
        })
        self.config.set("recovery", "pet_food", {
            "enabled":      self.chk_pet_food.isChecked(),
            "pet_count":    self.spin_pet_count.value(),
            "key":          self.edit_pet_key.text().strip(),
            "interval_min": self.spin_pet_interval.value(),
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

        hk = self.config.get("recovery", "hotkeys") or {}
        self.edit_hp_hotkey.setText(hk.get("hp", ""))
        self.edit_mp_hotkey.setText(hk.get("mp", ""))

        hp_coord = self.config.get("coordinate", "hp") or {}
        self.spin_hp_x.setValue(hp_coord.get("x", 0))
        self.spin_hp_y.setValue(hp_coord.get("y", 0))
        self.spin_hp_w.setValue(hp_coord.get("width", 0))

        mp_coord = self.config.get("coordinate", "mp") or {}
        self.spin_mp_x.setValue(mp_coord.get("x", 0))
        self.spin_mp_y.setValue(mp_coord.get("y", 0))
        self.spin_mp_w.setValue(mp_coord.get("width", 0))

