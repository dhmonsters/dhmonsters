# 빨코2 이동·회수 X 좌표를 편집하고 안전하게 저장하는 전용 카드 위젯
from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from core.config_adapter import REDNOSE2_X_DEFAULTS, rednose2_x_validation_error
from core_ui.theme import SPACING


class Rednose2CoordinateWidget(QFrame):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config = config
        self.inputs: dict[str, QSpinBox] = {}
        self.setObjectName("rednose2CoordinateCard")
        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"]
        )
        layout.setSpacing(SPACING["sm"])

        title = QLabel("빨코2 좌표 설정")
        title.setObjectName("presetTitle")
        layout.addWidget(title)

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

    def _current_values(self) -> dict[str, int]:
        return {key: spin.value() for key, spin in self.inputs.items()}

    def _load(self) -> None:
        saved = self._config.get("rednose2_v5", default={}) or {}
        for key, default in REDNOSE2_X_DEFAULTS.items():
            value = saved.get(key, default) if isinstance(saved, dict) else default
            self.inputs[key].setValue(value if isinstance(value, int) else default)

    def restore_defaults(self) -> None:
        for key, value in REDNOSE2_X_DEFAULTS.items():
            self.inputs[key].setValue(value)
        self.status.setText("기본값을 불러왔습니다. 저장을 눌러야 반영됩니다.")

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
