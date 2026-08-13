# 빨코2 좌표와 입력 시간을 독립적인 접이식 영역에서 편집하는 전용 카드 위젯
from __future__ import annotations

import math

from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.config_adapter import (
    REDNOSE2_TIMING_DEFAULTS,
    REDNOSE2_TIMING_VERSION,
    REDNOSE2_X_DEFAULTS,
    rednose2_x_validation_error,
)
from core_ui.theme import SPACING


_REDNOSE2_NAMES = {"빨코2", "rednose2", "rednose2v5"}


class Rednose2CoordinateWidget(QFrame):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self.inputs: dict[str, QSpinBox] = {}
        self.timing_inputs: dict[str, QDoubleSpinBox] = {}
        self.setObjectName("rednose2CoordinateCard")
        self._build_ui()
        self._load()
        self.set_hunt_ground(
            str(self._config.get("hunt_grounds", "active", default="") or "")
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"]
        )
        layout.setSpacing(SPACING["sm"])

        self.coordinate_toggle = self._toggle_button("빨코2 좌표 설정", "coordinateToggle")
        layout.addWidget(self.coordinate_toggle)
        self.coordinate_content = QWidget()
        self.coordinate_content.setObjectName("coordinateContent")
        self.coordinate_content.setHidden(True)
        layout.addWidget(self.coordinate_content)
        self._build_coordinate_content()
        self.coordinate_toggle.toggled.connect(
            lambda checked: self._set_section_visible(
                self.coordinate_toggle,
                self.coordinate_content,
                "빨코2 좌표 설정",
                checked,
            )
        )

        self.timing_toggle = self._toggle_button("빨코2 공격 설정", "timingToggle")
        layout.addWidget(self.timing_toggle)
        self.timing_content = QWidget()
        self.timing_content.setObjectName("timingContent")
        self.timing_content.setHidden(True)
        layout.addWidget(self.timing_content)
        self._build_timing_content()
        self.timing_toggle.toggled.connect(
            lambda checked: self._set_section_visible(
                self.timing_toggle,
                self.timing_content,
                "빨코2 공격 설정",
                checked,
            )
        )

    @staticmethod
    def _toggle_button(title: str, object_name: str) -> QPushButton:
        button = QPushButton(f"▶ {title}")
        button.setObjectName(object_name)
        button.setCheckable(True)
        button.setChecked(False)
        return button

    @staticmethod
    def _set_section_visible(
        button: QPushButton,
        content: QWidget,
        title: str,
        checked: bool,
    ) -> None:
        content.setVisible(checked)
        button.setText(f"{'▼' if checked else '▶'} {title}")

    def _build_coordinate_content(self) -> None:
        layout = QVBoxLayout(self.coordinate_content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])
        groups = (
            ("2층 사냥 범위", (("floor2_left_x", "왼쪽 X"), ("floor2_right_x", "오른쪽 X"))),
            ("회수 우측 끝", (("floor2_right_safe_x", "정지 X"),)),
            ("7번 계단", (("stair7_x", "목표 X"), ("stair7_x_min", "허용 최소 X"), ("stair7_x_max", "허용 최대 X"))),
            ("24번 발판", (("platform24_approach_x", "접근 X"), ("platform24_x", "도착 X"))),
            ("14/15번·16번", (("platform1415_16_approach_x", "공통 접근 X"), ("platform1415_x_min", "허용 최소 X"), ("platform1415_x_max", "허용 최대 X"))),
            ("27번 발판", (("platform27_approach_x", "접근 X"),)),
            ("16번 실패 시 27번 우회", (("platform27_bypass_approach_x", "접근 X"), ("platform27_bypass_x_min", "허용 최소 X"), ("platform27_bypass_x_max", "허용 최대 X"))),
        )
        for group_title, fields in groups:
            layout.addWidget(QLabel(group_title))
            grid = QGridLayout()
            grid.setHorizontalSpacing(SPACING["sm"])
            grid.setVerticalSpacing(SPACING["xs"])
            for row, (key, label) in enumerate(fields):
                grid.addWidget(QLabel(label), row, 0)
                spin = QSpinBox()
                spin.setRange(0, 171)
                self.inputs[key] = spin
                grid.addWidget(spin, row, 1)
            layout.addLayout(grid)

        controls = QHBoxLayout()
        save_button = QPushButton("저장")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self.save_values)
        controls.addWidget(save_button)
        restore_button = QPushButton("빨코2 기본값 복원")
        restore_button.setObjectName("secondaryButton")
        restore_button.clicked.connect(self.restore_defaults)
        controls.addWidget(restore_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.status = QLabel()
        self.status.setObjectName("presetStatus")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def _build_timing_content(self) -> None:
        layout = QVBoxLayout(self.timing_content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING["sm"])
        fields = (
            ("teleport_hold_sec", "일반 텔포 홀드"),
            ("attack_hold_sec", "공격키 총 홀드"),
            ("floor2_hunt_teleport_interval_sec", "일반 사냥 완료 후 간격"),
            ("stair7_right_teleport_hold_sec", "7번 계단 우측 텔포 홀드"),
            ("floor2_right_edge_teleport_interval_sec", "7번 이후 우측 끝 완료 후 간격"),
        )
        grid = QGridLayout()
        grid.setHorizontalSpacing(SPACING["sm"])
        grid.setVerticalSpacing(SPACING["xs"])
        for row, (key, label) in enumerate(fields):
            grid.addWidget(QLabel(label), row, 0)
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 10.0)
            spin.setDecimals(2)
            spin.setSingleStep(0.01)
            spin.setSuffix(" 초")
            self.timing_inputs[key] = spin
            grid.addWidget(spin, row, 1)
        layout.addLayout(grid)

        controls = QHBoxLayout()
        save_button = QPushButton("공격 설정 저장")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self.save_timing_values)
        controls.addWidget(save_button)
        restore_button = QPushButton("공격 기본값 복원")
        restore_button.setObjectName("secondaryButton")
        restore_button.clicked.connect(self.restore_timing_defaults)
        controls.addWidget(restore_button)
        controls.addStretch()
        layout.addLayout(controls)

        self.timing_status = QLabel()
        self.timing_status.setObjectName("presetStatus")
        self.timing_status.setWordWrap(True)
        layout.addWidget(self.timing_status)

    def set_hunt_ground(self, name: str) -> None:
        normalized = str(name or "").strip().lower().replace(" ", "")
        self.setHidden(normalized not in _REDNOSE2_NAMES)

    def _current_values(self) -> dict[str, int]:
        return {key: spin.value() for key, spin in self.inputs.items()}

    def _load(self) -> None:
        saved = self._config.get("rednose2_v5", default={}) or {}
        saved = saved if isinstance(saved, dict) else {}
        for key, default in REDNOSE2_X_DEFAULTS.items():
            value = saved.get(key, default)
            valid = isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 171
            self.inputs[key].setValue(value if valid else default)

        versioned = saved.get("timing_version") == REDNOSE2_TIMING_VERSION
        for key, default in REDNOSE2_TIMING_DEFAULTS.items():
            value = saved.get(key, default) if versioned else default
            valid = (
                isinstance(value, (int, float))
                and not isinstance(value, bool)
                and math.isfinite(float(value))
                and 0.0 <= float(value) <= 10.0
            )
            self.timing_inputs[key].setValue(float(value) if valid else default)

    def restore_defaults(self) -> None:
        for key, value in REDNOSE2_X_DEFAULTS.items():
            self.inputs[key].setValue(value)
        self.status.setText("기본값을 불러왔습니다. 저장을 눌러야 반영됩니다.")

    def restore_timing_defaults(self) -> None:
        for key, value in REDNOSE2_TIMING_DEFAULTS.items():
            self.timing_inputs[key].setValue(value)
        self.timing_status.setText("공격 기본값을 불러왔습니다. 저장을 눌러야 반영됩니다.")

    def save_values(self) -> None:
        values = self._current_values()
        error = rednose2_x_validation_error(values)
        if error:
            self.status.setText(error)
            return
        current = self._config.get("rednose2_v5", default={}) or {}
        merged = dict(current) if isinstance(current, dict) else {}
        merged.update(values)
        self._config.set("rednose2_v5", merged)
        self._config.save()
        self.status.setText("저장 완료 · 다음 F1 시작부터 적용됩니다.")

    def save_timing_values(self) -> None:
        values = {key: round(spin.value(), 2) for key, spin in self.timing_inputs.items()}
        current = self._config.get("rednose2_v5", default={}) or {}
        merged = dict(current) if isinstance(current, dict) else {}
        merged.update(values)
        merged["timing_version"] = REDNOSE2_TIMING_VERSION
        self._config.set("rednose2_v5", merged)
        self._config.save()
        self.timing_status.setText("공격 설정 저장 완료 · 다음 F1 시작부터 적용됩니다.")
