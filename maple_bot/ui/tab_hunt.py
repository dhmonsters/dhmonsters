# 사냥 탭 - 키 반복 패턴 에디터 (좌표 이동은 좌표 탭에서 설정)
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QListWidget, QPushButton, QLabel, QComboBox,
    QDoubleSpinBox, QSpinBox, QLineEdit,
    QScrollArea, QAbstractItemView,
)
from PyQt6.QtCore import Qt

from core.pattern import (
    KeyPattern, KeyStep, KEY_OPTIONS, ACTION_HOLD, ACTION_TAP, ACTION_COMBO,
)


class TabHunt(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._key_pattern = KeyPattern(name="기본 패턴")
        self._bot = None
        self._edit_index: int = -1   # -1: 추가 모드, >=0: 수정 중인 스텝 인덱스

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_key_header())
        layout.addWidget(self._build_key_list())
        layout.addWidget(self._build_key_add())

        self.load_from_config()

    def set_bot(self, bot) -> None:
        self._bot = bot

    # ══════════════════════════════════════════════════════════════════
    # 키 반복 패턴 에디터
    # ══════════════════════════════════════════════════════════════════
    def _build_key_header(self):
        group = QGroupBox("패턴 관리")
        vlay = QVBoxLayout(group)
        vlay.setSpacing(6)

        # ── 행1: 편집 중인 패턴 이름 + 딜레이 + 저장 ────────────────
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("패턴 이름"))
        self.key_name = QLineEdit("기본 패턴")
        self.key_name.setMaximumWidth(160)
        row1.addWidget(self.key_name)

        row1.addWidget(QLabel("스텝 간 딜레이"))
        self.key_between_min = QDoubleSpinBox()
        self.key_between_min.setRange(0.0, 10.0)
        self.key_between_min.setSingleStep(0.05)
        self.key_between_min.setValue(0.05)
        self.key_between_min.setFixedWidth(65)
        self.key_between_max = QDoubleSpinBox()
        self.key_between_max.setRange(0.0, 10.0)
        self.key_between_max.setSingleStep(0.05)
        self.key_between_max.setValue(0.20)
        self.key_between_max.setFixedWidth(65)
        row1.addWidget(self.key_between_min)
        row1.addWidget(QLabel("~"))
        row1.addWidget(self.key_between_max)
        row1.addWidget(QLabel("초"))

        btn_save = QPushButton("저장 (기본)")
        btn_save.setToolTip("이 패턴을 기본 패턴으로 저장합니다.")
        btn_save.clicked.connect(self._key_save)
        btn_preset = QPushButton("프리셋으로 저장")
        btn_preset.setToolTip("이름으로 저장합니다. 구역별 패턴 선택에서 불러올 수 있습니다.")
        btn_preset.clicked.connect(self._key_save_preset)
        row1.addWidget(btn_save)
        row1.addWidget(btn_preset)
        row1.addStretch()
        vlay.addLayout(row1)

        # ── 행2: 저장된 프리셋 목록 불러오기 ────────────────────────
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("저장된 패턴"))
        self.cmb_preset = QComboBox()
        self.cmb_preset.setMinimumWidth(150)
        row2.addWidget(self.cmb_preset)
        btn_load_preset = QPushButton("불러오기")
        btn_load_preset.setFixedWidth(70)
        btn_load_preset.clicked.connect(self._key_load_preset)
        btn_del_preset = QPushButton("삭제")
        btn_del_preset.setFixedWidth(50)
        btn_del_preset.clicked.connect(self._key_del_preset)
        row2.addWidget(btn_load_preset)
        row2.addWidget(btn_del_preset)
        row2.addStretch()
        vlay.addLayout(row2)

        self._refresh_preset_combo()
        return group

    def _build_key_list(self):
        group = QGroupBox("스텝 목록")
        layout = QVBoxLayout(group)

        self.key_list = QListWidget()
        self.key_list.setMinimumHeight(140)
        self.key_list.itemDoubleClicked.connect(self._on_step_double_click)
        layout.addWidget(self.key_list)

        btn_row = QHBoxLayout()
        btn_up   = QPushButton("▲ 위로")
        btn_down = QPushButton("▼ 아래로")
        btn_del  = QPushButton("삭제")
        btn_up.clicked.connect(self._key_move_up)
        btn_down.clicked.connect(self._key_move_down)
        btn_del.clicked.connect(self._key_delete)
        for b in [btn_up, btn_down, btn_del]:
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return group

    def _build_key_add(self):
        group = QGroupBox("스텝 추가")
        layout = QVBoxLayout(group)

        # ── 행 1: 키 / 동작 ──────────────────────────────────────────
        row1 = QHBoxLayout()

        self._lbl_single_key = QLabel("키")
        row1.addWidget(self._lbl_single_key)
        self.key_combo_key = QComboBox()
        self.key_combo_key.addItems(KEY_OPTIONS)
        self.key_combo_key.setFixedWidth(110)
        row1.addWidget(self.key_combo_key)

        row1.addWidget(QLabel("동작"))
        self.key_combo_action = QComboBox()
        self.key_combo_action.addItems(["누름 (hold)", "탭 (tap)", "연속기 (combo)"])
        self.key_combo_action.setFixedWidth(130)
        self.key_combo_action.currentIndexChanged.connect(self._on_key_action_changed)
        row1.addWidget(self.key_combo_action)
        row1.addStretch()
        layout.addLayout(row1)

        # ── 연속기 편집 위젯 (평소엔 숨김) ───────────────────────────
        self._combo_keys: list[str] = []
        self._combo_holds: list[list[float]] = []   # [[base, var], ...]
        self._combo_editor = self._build_combo_editor()
        layout.addWidget(self._combo_editor)

        # ── 행 2: 시간 / 반복 ────────────────────────────────────────
        row2 = QHBoxLayout()
        self._lbl_gap = QLabel("간격")
        row2.addWidget(self._lbl_gap)
        self.key_spin_min = QDoubleSpinBox()
        self.key_spin_min.setRange(0.01, 60.0)
        self.key_spin_min.setSingleStep(0.1)
        self.key_spin_min.setValue(0.5)
        self.key_spin_min.setFixedWidth(70)
        self.key_spin_max = QDoubleSpinBox()
        self.key_spin_max.setRange(0.01, 60.0)
        self.key_spin_max.setSingleStep(0.1)
        self.key_spin_max.setValue(1.5)
        self.key_spin_max.setFixedWidth(70)
        row2.addWidget(self.key_spin_min)
        row2.addWidget(QLabel("~"))
        row2.addWidget(self.key_spin_max)
        row2.addWidget(QLabel("초"))

        row2.addSpacing(16)
        row2.addWidget(QLabel("반복"))
        self.key_spin_rep_min = QSpinBox()
        self.key_spin_rep_min.setRange(1, 99)
        self.key_spin_rep_min.setValue(1)
        self.key_spin_rep_min.setFixedWidth(55)
        self.key_spin_rep_max = QSpinBox()
        self.key_spin_rep_max.setRange(1, 99)
        self.key_spin_rep_max.setValue(1)
        self.key_spin_rep_max.setFixedWidth(55)
        row2.addWidget(self.key_spin_rep_min)
        row2.addWidget(QLabel("~"))
        row2.addWidget(self.key_spin_rep_max)
        row2.addWidget(QLabel("회"))
        row2.addStretch()
        layout.addLayout(row2)

        # ── 행 3: 탭/연속기 홀드 시간 (HOLD 동작 선택 시 숨김) ──────
        self._hold_row_widget = QWidget()
        row3 = QHBoxLayout(self._hold_row_widget)
        row3.setContentsMargins(0, 0, 0, 0)
        row3.addWidget(QLabel("홀드"))
        self.key_spin_hold_base = QDoubleSpinBox()
        self.key_spin_hold_base.setRange(0.02, 2.0)
        self.key_spin_hold_base.setSingleStep(0.01)
        self.key_spin_hold_base.setValue(0.06)
        self.key_spin_hold_base.setFixedWidth(70)
        self.key_spin_hold_var = QDoubleSpinBox()
        self.key_spin_hold_var.setRange(0.0, 1.0)
        self.key_spin_hold_var.setSingleStep(0.01)
        self.key_spin_hold_var.setValue(0.01)
        self.key_spin_hold_var.setFixedWidth(60)
        row3.addWidget(self.key_spin_hold_base)
        row3.addWidget(QLabel("±"))
        row3.addWidget(self.key_spin_hold_var)
        row3.addWidget(QLabel("초  (탭/연속기 키 누름 유지 시간)"))
        row3.addStretch()
        layout.addWidget(self._hold_row_widget)

        btn_row_add = QHBoxLayout()
        self.btn_add = QPushButton("+ 스텝 추가")
        self.btn_add.clicked.connect(self._key_add_step)
        self.btn_edit_cancel = QPushButton("취소")
        self.btn_edit_cancel.setFixedWidth(60)
        self.btn_edit_cancel.setVisible(False)
        self.btn_edit_cancel.clicked.connect(self._key_edit_cancel)
        btn_row_add.addWidget(self.btn_add)
        btn_row_add.addWidget(self.btn_edit_cancel)
        btn_row_add.addStretch()
        layout.addLayout(btn_row_add)
        return group

    def _build_combo_editor(self) -> QWidget:
        """연속기 키 목록 편집 위젯 (키별 홀드 시간 개별 설정)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        pick_row = QHBoxLayout()
        pick_row.addWidget(QLabel("키"))
        self._combo_pick = QComboBox()
        self._combo_pick.addItems(KEY_OPTIONS)
        self._combo_pick.setFixedWidth(100)
        pick_row.addWidget(self._combo_pick)

        pick_row.addWidget(QLabel("홀드"))
        self._combo_hold_base = QDoubleSpinBox()
        self._combo_hold_base.setRange(0.02, 2.0)
        self._combo_hold_base.setSingleStep(0.05)
        self._combo_hold_base.setValue(0.06)
        self._combo_hold_base.setFixedWidth(65)
        self._combo_hold_var = QDoubleSpinBox()
        self._combo_hold_var.setRange(0.0, 1.0)
        self._combo_hold_var.setSingleStep(0.01)
        self._combo_hold_var.setValue(0.01)
        self._combo_hold_var.setFixedWidth(55)
        pick_row.addWidget(self._combo_hold_base)
        pick_row.addWidget(QLabel("±"))
        pick_row.addWidget(self._combo_hold_var)
        pick_row.addWidget(QLabel("초"))

        btn_plus = QPushButton("＋")
        btn_minus = QPushButton("－")
        btn_plus.setFixedWidth(32)
        btn_minus.setFixedWidth(32)
        btn_plus.clicked.connect(self._combo_add_key)
        btn_minus.clicked.connect(self._combo_del_key)
        pick_row.addWidget(btn_plus)
        pick_row.addWidget(btn_minus)
        pick_row.addStretch()
        layout.addLayout(pick_row)

        self._combo_list = QListWidget()
        self._combo_list.setMaximumHeight(60)
        layout.addWidget(self._combo_list)

        widget.setVisible(False)
        return widget

    def _on_key_action_changed(self, idx: int) -> None:
        is_hold  = (idx == 0)
        is_combo = (idx == 2)
        self._lbl_single_key.setVisible(not is_combo)
        self.key_combo_key.setVisible(not is_combo)
        self._combo_editor.setVisible(is_combo)
        # HOLD: 누름 시간 = min~max 자체가 홀드 시간이므로 별도 홀드 행 불필요
        self._hold_row_widget.setVisible(not is_hold)
        self._lbl_gap.setText("누름 시간" if is_hold else "간격")

    def _combo_add_key(self) -> None:
        key = self._combo_pick.currentText()
        base = self._combo_hold_base.value()
        var  = self._combo_hold_var.value()
        self._combo_keys.append(key)
        self._combo_holds.append([base, var])
        self._combo_list.clear()
        self._combo_list.addItem(self._combo_label())

    def _combo_del_key(self) -> None:
        if self._combo_keys:
            self._combo_keys.pop()
            self._combo_holds.pop()
        self._combo_list.clear()
        if self._combo_keys:
            self._combo_list.addItem(self._combo_label())

    def _combo_label(self) -> str:
        """연속기 키 목록을 '키(홀드ms±varMs) → ...' 형식으로 표시."""
        parts = []
        for k, (b, v) in zip(self._combo_keys, self._combo_holds):
            parts.append(f"{k}({int(b*1000)}±{int(v*1000)}ms)")
        return " → ".join(parts)

    # ── 키 반복 조작 ──────────────────────────────────────────────────
    def _key_add_step(self) -> None:
        step = self._build_step_from_form()
        if step is None:
            return

        if self._edit_index >= 0:
            # 수정 모드: 기존 스텝 교체
            self._key_pattern.steps[self._edit_index] = step
            self._key_edit_cancel()   # 모드 초기화 + 리스트 갱신
        else:
            # 추가 모드
            self._key_pattern.steps.append(step)
            self.key_list.addItem(step.label())

    def _build_step_from_form(self) -> "KeyStep | None":
        """폼 현재 값으로 KeyStep 생성. 유효하지 않으면 None 반환."""
        idx    = self.key_combo_action.currentIndex()
        action = [ACTION_HOLD, ACTION_TAP, ACTION_COMBO][idx]
        hold_base = self.key_spin_hold_base.value()
        hold_var  = self.key_spin_hold_var.value()

        if action == ACTION_COMBO:
            if not self._combo_keys:
                return None
            step = KeyStep(
                key=self._combo_keys[0],
                action=ACTION_COMBO,
                min_sec=self.key_spin_min.value(),
                max_sec=self.key_spin_max.value(),
                repeat_min=self.key_spin_rep_min.value(),
                repeat_max=self.key_spin_rep_max.value(),
                combo_keys=list(self._combo_keys),
                tap_hold_base=hold_base,
                tap_hold_var=hold_var,
                combo_holds=[list(h) for h in self._combo_holds],
            )
            self._combo_keys.clear()
            self._combo_holds.clear()
            self._combo_list.clear()
        else:
            step = KeyStep(
                key=self.key_combo_key.currentText(),
                action=action,
                min_sec=self.key_spin_min.value(),
                max_sec=self.key_spin_max.value(),
                repeat_min=self.key_spin_rep_min.value(),
                repeat_max=self.key_spin_rep_max.value(),
                tap_hold_base=hold_base,
                tap_hold_var=hold_var,
            )
        return step

    def _on_step_double_click(self, item) -> None:
        """스텝 더블클릭 시 해당 값을 폼에 로드."""
        row = self.key_list.row(item)
        if 0 <= row < len(self._key_pattern.steps):
            self._load_step_to_form(self._key_pattern.steps[row], row)

    def _load_step_to_form(self, step: KeyStep, index: int) -> None:
        """스텝 데이터를 폼에 채우고 수정 모드로 전환."""
        self._edit_index = index
        self.btn_add.setText("✏ 수정 완료")
        self.btn_edit_cancel.setVisible(True)
        self.key_list.setCurrentRow(index)

        # 공통 값
        self.key_spin_min.setValue(step.min_sec)
        self.key_spin_max.setValue(step.max_sec)
        self.key_spin_rep_min.setValue(step.repeat_min)
        self.key_spin_rep_max.setValue(step.repeat_max)
        self.key_spin_hold_base.setValue(step.tap_hold_base)
        self.key_spin_hold_var.setValue(step.tap_hold_var)

        if step.action == ACTION_HOLD:
            self.key_combo_action.setCurrentIndex(0)
            self._set_key_combo(step.key)
        elif step.action == ACTION_TAP:
            self.key_combo_action.setCurrentIndex(1)
            self._set_key_combo(step.key)
        elif step.action == ACTION_COMBO:
            self.key_combo_action.setCurrentIndex(2)
            self._combo_keys  = list(step.combo_keys)
            self._combo_holds = [list(h) for h in step.combo_holds]
            self._combo_list.clear()
            if self._combo_keys:
                self._combo_list.addItem(self._combo_label())

    def _set_key_combo(self, key: str) -> None:
        """키 드롭다운을 key 값으로 설정. 없으면 무시."""
        from core.pattern import KEY_OPTIONS
        if key in KEY_OPTIONS:
            self.key_combo_key.setCurrentIndex(KEY_OPTIONS.index(key))

    def _key_edit_cancel(self) -> None:
        """수정 모드 취소 → 추가 모드로 복귀."""
        self._edit_index = -1
        self.btn_add.setText("+ 스텝 추가")
        self.btn_edit_cancel.setVisible(False)
        self._key_refresh()

    def _key_delete(self) -> None:
        row = self.key_list.currentRow()
        if row < 0:
            return
        self.key_list.takeItem(row)
        del self._key_pattern.steps[row]

    def _key_move_up(self) -> None:
        row = self.key_list.currentRow()
        if row <= 0:
            return
        s = self._key_pattern.steps
        s[row - 1], s[row] = s[row], s[row - 1]
        self._key_refresh()
        self.key_list.setCurrentRow(row - 1)

    def _key_move_down(self) -> None:
        row = self.key_list.currentRow()
        if row < 0 or row >= len(self._key_pattern.steps) - 1:
            return
        s = self._key_pattern.steps
        s[row], s[row + 1] = s[row + 1], s[row]
        self._key_refresh()
        self.key_list.setCurrentRow(row + 1)

    def _key_refresh(self) -> None:
        self.key_list.clear()
        for step in self._key_pattern.steps:
            self.key_list.addItem(step.label())

    def _key_save(self) -> None:
        self._key_pattern.name = self.key_name.text() or "기본 패턴"
        self._key_pattern.between_min = self.key_between_min.value()
        self._key_pattern.between_max = self.key_between_max.value()
        self.save_to_config()
        if self._bot:
            self._bot.reload_pattern()

    def _key_save_preset(self) -> None:
        """현재 패턴을 key_patterns.presets[이름]으로 저장한다."""
        self._key_pattern.name = self.key_name.text() or "기본 패턴"
        self._key_pattern.between_min = self.key_between_min.value()
        self._key_pattern.between_max = self.key_between_max.value()
        presets = self.config.get("key_patterns", "presets") or {}
        presets[self._key_pattern.name] = self._key_pattern.to_dict()
        self.config.set("key_patterns", "presets", presets)
        self.config.save()
        self._refresh_preset_combo(self._key_pattern.name)

    def _refresh_preset_combo(self, select_name: str = "") -> None:
        """저장된 프리셋 목록을 콤보박스에 채운다."""
        self.cmb_preset.clear()
        presets = self.config.get("key_patterns", "presets") or {}
        for name in sorted(presets.keys()):
            self.cmb_preset.addItem(name)
        if select_name:
            idx = self.cmb_preset.findText(select_name)
            if idx >= 0:
                self.cmb_preset.setCurrentIndex(idx)

    def _key_load_preset(self) -> None:
        """선택한 프리셋을 에디터에 로드한다."""
        name = self.cmb_preset.currentText()
        if not name:
            return
        presets = self.config.get("key_patterns", "presets") or {}
        raw = presets.get(name)
        if not raw:
            return
        try:
            self._key_pattern = KeyPattern.from_dict(raw)
            self.key_name.setText(self._key_pattern.name)
            self.key_between_min.setValue(self._key_pattern.between_min)
            self.key_between_max.setValue(self._key_pattern.between_max)
            self._key_refresh()
        except Exception:
            pass

    def _key_del_preset(self) -> None:
        """선택한 프리셋을 삭제한다."""
        name = self.cmb_preset.currentText()
        if not name:
            return
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "삭제 확인", f"'{name}' 패턴을 삭제할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        presets = self.config.get("key_patterns", "presets") or {}
        presets.pop(name, None)
        self.config.set("key_patterns", "presets", presets)
        self.config.save()
        self._refresh_preset_combo()

    def _key_load(self) -> None:
        self.load_from_config()

    # ── config 연동 ───────────────────────────────────────────────────
    def save_to_config(self) -> None:
        self.config.set("key_patterns", "active", self._key_pattern.to_dict())
        self.config.save()

    def load_from_config(self) -> None:
        raw_key = self.config.get("key_patterns", "active")
        if raw_key:
            try:
                self._key_pattern = KeyPattern.from_dict(raw_key)
                self.key_name.setText(self._key_pattern.name)
                self.key_between_min.setValue(self._key_pattern.between_min)
                self.key_between_max.setValue(self._key_pattern.between_max)
                self._key_refresh()
            except Exception:
                pass
        self._refresh_preset_combo()
