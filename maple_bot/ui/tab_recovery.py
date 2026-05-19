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
        layout.addWidget(self._build_potion_count_group())

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

    def _build_potion_count_group(self) -> QGroupBox:
        group = QGroupBox("포션 수량 확인 (수량 0 시 마을 귀환)")
        layout = QVBoxLayout(group)

        note = QLabel(
            "퀵슬롯의 포션 아이템 칸을 드래그로 지정하세요. "
            "아이템 그래픽 색상 픽셀이 50개 미만이면 수량 0으로 판정합니다.\n"
            "'수량 상태 확인'으로 포션 있을 때/없을 때 픽셀 수를 먼저 확인하세요. "
            "마을 귀환 주문서(위치 탭)가 활성화되어야 귀환 작동합니다."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(note)

        self.chk_potion_zero_return = QCheckBox("수량 0 시 마을 귀환 활성화")
        layout.addWidget(self.chk_potion_zero_return)

        # HP 포션 슬롯 영역
        hp_row = QHBoxLayout()
        hp_row.addWidget(QLabel("HP 포션 슬롯"))
        self.lbl_hp_count_region = QLabel("미설정")
        self.lbl_hp_count_region.setStyleSheet("color: gray; font-size: 10px;")
        hp_row.addWidget(self.lbl_hp_count_region)
        hp_row.addStretch()
        btn_hp_cnt = QPushButton("📍 드래그 설정")
        btn_hp_cnt.setFixedWidth(90)
        btn_hp_cnt.setToolTip("HP 포션이 등록된 퀵슬롯(아이템 슬롯) 영역을 드래그해서 지정하세요.")
        btn_hp_cnt.clicked.connect(self._select_hp_count_region)
        btn_hp_cnt_rst = QPushButton("✕")
        btn_hp_cnt_rst.setFixedWidth(24)
        btn_hp_cnt_rst.clicked.connect(self._reset_hp_count_region)
        hp_row.addWidget(btn_hp_cnt)
        hp_row.addWidget(btn_hp_cnt_rst)
        layout.addLayout(hp_row)

        # MP 포션 슬롯 영역
        mp_row = QHBoxLayout()
        mp_row.addWidget(QLabel("MP 포션 슬롯"))
        self.lbl_mp_count_region = QLabel("미설정")
        self.lbl_mp_count_region.setStyleSheet("color: gray; font-size: 10px;")
        mp_row.addWidget(self.lbl_mp_count_region)
        mp_row.addStretch()
        btn_mp_cnt = QPushButton("📍 드래그 설정")
        btn_mp_cnt.setFixedWidth(90)
        btn_mp_cnt.setToolTip("MP 포션이 등록된 퀵슬롯(아이템 슬롯) 영역을 드래그해서 지정하세요.")
        btn_mp_cnt.clicked.connect(self._select_mp_count_region)
        btn_mp_cnt_rst = QPushButton("✕")
        btn_mp_cnt_rst.setFixedWidth(24)
        btn_mp_cnt_rst.clicked.connect(self._reset_mp_count_region)
        mp_row.addWidget(btn_mp_cnt)
        mp_row.addWidget(btn_mp_cnt_rst)
        layout.addLayout(mp_row)

        # 테스트 버튼
        test_row = QHBoxLayout()
        btn_test_cnt = QPushButton("수량 상태 확인")
        btn_test_cnt.clicked.connect(self._test_potion_count)
        self.lbl_count_result = QLabel("HP: -  MP: -")
        test_row.addWidget(btn_test_cnt)
        test_row.addWidget(self.lbl_count_result)
        test_row.addStretch()
        layout.addLayout(test_row)

        return group

    def _select_hp_count_region(self) -> None:
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._apply_hp_count_region)
        self._selector.show()

    def _select_mp_count_region(self) -> None:
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._apply_mp_count_region)
        self._selector.show()

    def _apply_hp_count_region(self, x: int, y: int, w: int, h: int) -> None:
        self.config.set("recovery", "potion_count", "hp_region", [x, y, w, h])
        self.config.save()
        self.lbl_hp_count_region.setText(f"X={x} Y={y} W={w} H={h}")
        self.lbl_hp_count_region.setStyleSheet("color: green; font-size: 10px;")

    def _apply_mp_count_region(self, x: int, y: int, w: int, h: int) -> None:
        self.config.set("recovery", "potion_count", "mp_region", [x, y, w, h])
        self.config.save()
        self.lbl_mp_count_region.setText(f"X={x} Y={y} W={w} H={h}")
        self.lbl_mp_count_region.setStyleSheet("color: green; font-size: 10px;")

    def _reset_hp_count_region(self) -> None:
        self.config.set("recovery", "potion_count", "hp_region", None)
        self.config.save()
        self.lbl_hp_count_region.setText("미설정")
        self.lbl_hp_count_region.setStyleSheet("color: gray; font-size: 10px;")

    def _reset_mp_count_region(self) -> None:
        self.config.set("recovery", "potion_count", "mp_region", None)
        self.config.save()
        self.lbl_mp_count_region.setText("미설정")
        self.lbl_mp_count_region.setStyleSheet("color: gray; font-size: 10px;")

    def _test_potion_count(self) -> None:
        """포션 슬롯 영역을 OCR로 읽어 수량을 표시한다."""
        pc = self.config.get("recovery", "potion_count") or {}
        hp_r = pc.get("hp_region")
        mp_r = pc.get("mp_region")

        self.lbl_count_result.setText("읽는 중...")
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        def _read_count(region) -> str:
            if not region or len(region) < 4:
                return "미설정"
            x, y, w, h = int(region[0]), int(region[1]), int(region[2]), int(region[3])
            try:
                img = self._screen.capture({"left": x, "top": y, "width": w, "height": h})
                from core.ocr_detector import read_number
                n = read_number(img)
                if n is not None:
                    return f"{n}개"
                # OCR 실패 시 픽셀 수도 함께 표시
                import cv2
                hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
                mask = (hsv[:, :, 1] > 50) & (hsv[:, :, 2] > 50)
                px = int(mask.sum())
                return f"읽기 실패 (픽셀 {px}px)"
            except Exception as e:
                return f"오류: {e}"

        hp_s = _read_count(hp_r)
        mp_s = _read_count(mp_r)
        self.lbl_count_result.setText(f"HP: {hp_s}  MP: {mp_s}")

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
        # 포션 수량 확인 설정 저장 (영역은 드래그 시 즉시 저장, 여기서는 체크박스만)
        pc = self.config.get("recovery", "potion_count") or {}
        self.config.set("recovery", "potion_count", {
            "hp_region":    pc.get("hp_region"),
            "mp_region":    pc.get("mp_region"),
            "zero_return":  self.chk_potion_zero_return.isChecked(),
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

        # 포션 수량 확인
        pc = self.config.get("recovery", "potion_count") or {}
        self.chk_potion_zero_return.setChecked(bool(pc.get("zero_return", False)))
        hp_r = pc.get("hp_region")
        if hp_r and len(hp_r) == 4:
            x, y, w, h = hp_r
            self.lbl_hp_count_region.setText(f"X={x} Y={y} W={w} H={h}")
            self.lbl_hp_count_region.setStyleSheet("color: green; font-size: 10px;")
        mp_r = pc.get("mp_region")
        if mp_r and len(mp_r) == 4:
            x, y, w, h = mp_r
            self.lbl_mp_count_region.setText(f"X={x} Y={y} W={w} H={h}")
            self.lbl_mp_count_region.setStyleSheet("color: green; font-size: 10px;")

