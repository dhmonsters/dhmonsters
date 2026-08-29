# 사냥터 프리셋의 저장 범위를 안내하고 저장·불러오기를 제공하는 카드 위젯
from __future__ import annotations

import os
import re

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

from core.hunt_ground_presets import load_preset, save_active_preset
from core_ui.theme import SPACING


class HuntGroundPresetWidget(QFrame):
    preset_loaded = pyqtSignal(str)

    def __init__(self, config, name_field=None, parent=None):
        super().__init__(parent)
        self._config = config
        self._name_field = None
        self.setObjectName("huntGroundPresetCard")
        self._build_ui()
        self.refresh()
        if name_field is not None:
            self.bind_name_field(name_field)

    def bind_name_field(self, field) -> None:
        """현재 사냥터 입력란을 저장 프로필 이름과 연결한다."""
        self._name_field = field
        field.widget.editingFinished.connect(self._load_from_name_field)

    def _load_from_name_field(self) -> None:
        """입력한 사냥터 이름에 저장된 설정이 있으면 불러온다."""
        if self._name_field is None:
            return
        name = str(self._name_field.widget.text()).strip()
        if not name:
            return

        presets = self._config.get("hunt_grounds", "presets", default={}) or {}
        if name not in presets:
            self.refresh()
            return

        try:
            load_preset(self._config, name)
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        self._activate_template_folder()
        self._refresh_bound_fields()
        self.refresh()
        self.status.setText(f"'{name}' 저장 설정을 불러왔습니다.")
        self.preset_loaded.emit(name)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"]
        )
        layout.setSpacing(SPACING["sm"])

        title = QLabel("사냥터 프리셋")
        title.setObjectName("presetTitle")
        layout.addWidget(title)

        description = QLabel(
            "현재 사냥터의 미니맵·사냥영역·인식 이미지·이동 맵핑·맵이탈 설정을 함께 저장합니다."
        )
        description.setObjectName("presetDescription")
        description.setWordWrap(True)
        layout.addWidget(description)

        controls = QHBoxLayout()
        controls.setSpacing(SPACING["sm"])
        self.preset_combo = QComboBox()
        self.preset_combo.setObjectName("presetSelector")
        self.preset_combo.setMinimumWidth(190)
        controls.addWidget(self.preset_combo, 1)

        self.load_button = QPushButton("설정 불러오기")
        self.load_button.setObjectName("secondaryButton")
        self.load_button.clicked.connect(self._load)
        controls.addWidget(self.load_button)

        self.save_button = QPushButton("현재 맵 설정 저장")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self._save)
        controls.addWidget(self.save_button)
        layout.addLayout(controls)

        self.status = QLabel("사냥터 이름을 입력한 뒤 현재 설정을 저장해 주세요.")
        self.status.setObjectName("presetStatus")
        layout.addWidget(self.status)

        template_title = QLabel("현재 사냥터 몬스터 템플릿")
        template_title.setObjectName("presetTitle")
        layout.addWidget(template_title)
        template_help = QLabel(
            "게임 화면에서 몬스터의 작은 영역을 여러 번 드래그해 캡처합니다. "
            "현재 사냥터의 이미지 폴더만 검색에 사용됩니다."
        )
        template_help.setObjectName("presetDescription")
        template_help.setWordWrap(True)
        layout.addWidget(template_help)

        template_controls = QHBoxLayout()
        self.template_capture_button = QPushButton("몬스터 이미지 캡처")
        self.template_capture_button.setObjectName("primaryButton")
        self.template_capture_button.clicked.connect(self._capture_monster_template)
        template_controls.addWidget(self.template_capture_button)
        self.template_delete_button = QPushButton("선택 삭제")
        self.template_delete_button.setObjectName("secondaryButton")
        self.template_delete_button.clicked.connect(self._delete_monster_template)
        template_controls.addWidget(self.template_delete_button)
        template_controls.addStretch()
        layout.addLayout(template_controls)

        self.template_list = QListWidget()
        self.template_list.setMaximumHeight(110)
        layout.addWidget(self.template_list)
        self.template_status = QLabel("등록된 몬스터 템플릿이 없습니다.")
        self.template_status.setObjectName("presetStatus")
        layout.addWidget(self.template_status)

    def refresh(self) -> None:
        active = str(self._config.get("hunt_grounds", "active", default="") or "")
        presets = self._config.get("hunt_grounds", "presets", default={}) or {}
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItems(sorted(str(name) for name in presets))
        index = self.preset_combo.findText(active)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)
        self.preset_combo.blockSignals(False)
        self.load_button.setEnabled(self.preset_combo.count() > 0)
        self._refresh_template_list()

    def _template_folder(self) -> str:
        """현재 사냥터 전용 몬스터 템플릿 폴더를 반환한다."""
        name = str(self._config.get("hunt_grounds", "active", default="") or "").strip()
        presets = self._config.get("hunt_grounds", "presets", default={}) or {}
        saved = presets.get(name, {}) if isinstance(presets, dict) else {}
        saved_attack = saved.get("attack", {}) if isinstance(saved, dict) else {}
        configured = str(saved_attack.get("monster_folder", "") or "").strip()
        if configured:
            return configured
        safe = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", name or "default")
        return os.path.join("templates", "hunt_monsters", safe)

    def _refresh_template_list(self) -> None:
        if not hasattr(self, "template_list"):
            return
        folder = self._template_folder()
        paths = []
        if os.path.isdir(folder):
            paths = sorted(
                os.path.join(folder, name)
                for name in os.listdir(folder)
                if name.lower().endswith((".png", ".jpg", ".jpeg"))
            )
        self.template_list.clear()
        for path in paths:
            self.template_list.addItem(os.path.basename(path))
        self.template_status.setText(
            f"등록된 템플릿 {len(paths)}개 · {folder}"
            if paths else "등록된 몬스터 템플릿이 없습니다."
        )

    def _activate_template_folder(self) -> None:
        """현재 사냥터의 템플릿 폴더만 런타임 검색 대상으로 연결한다."""
        self._config.set("attack", "monster_template", "")
        self._config.set("attack", "monster_folder", self._template_folder())
        self._config.save()

    def _capture_monster_template(self) -> None:
        name = str(self._config.get("hunt_grounds", "active", default="") or "").strip()
        if not name:
            QMessageBox.warning(self, "몬스터 템플릿", "현재 사냥터 이름을 먼저 입력해 주세요.")
            return
        try:
            import mss
            import numpy as np
            import cv2
            from core_ui.shot_selector import ScreenshotRegionSelector

            with mss.mss() as sct:
                monitor = sct.monitors[1]
                raw = np.array(sct.grab(monitor))[:, :, :3]
                origin = (int(monitor["left"]), int(monitor["top"]))
            selector = ScreenshotRegionSelector(raw, src_origin=origin)

            def save_crop(x, y, w, h):
                folder = self._template_folder()
                os.makedirs(folder, exist_ok=True)
                rx, ry = int(x - origin[0]), int(y - origin[1])
                crop = raw[max(0, ry):max(0, ry) + int(h),
                           max(0, rx):max(0, rx) + int(w)]
                if crop.size == 0:
                    self.template_status.setText("캡처 영역이 비어 있습니다.")
                    return
                existing = [
                    name for name in os.listdir(folder)
                    if name.lower().endswith(".png") and name.startswith("monster_")
                ]
                index = len(existing) + 1
                path = os.path.join(folder, f"monster_{index:03d}.png")
                while os.path.exists(path):
                    index += 1
                    path = os.path.join(folder, f"monster_{index:03d}.png")
                try:
                    ok, encoded = cv2.imencode(".png", crop)
                    if not ok:
                        raise RuntimeError("이미지 변환에 실패했습니다.")
                    encoded.tofile(path)
                    write_ok = True
                except Exception as exc:
                    QMessageBox.warning(self, "몬스터 템플릿 저장 오류", str(exc))
                    return
                if not write_ok:
                    QMessageBox.warning(self, "몬스터 템플릿 저장 오류", "이미지 저장에 실패했습니다.")
                    return
                    raise RuntimeError("이미지 저장에 실패했습니다.")
                self._config.set("attack", "monster_template", "")
                self._config.set("attack", "monster_folder", folder)
                self._config.save()
                self._refresh_template_list()
                self.template_status.setText(
                    f"템플릿 저장 완료: {os.path.basename(path)} · 현재 설정에 반영됨"
                )

            selector.region_selected.connect(save_crop)
            selector.exec()
        except Exception as exc:
            QMessageBox.warning(self, "몬스터 템플릿 캡처 오류", str(exc))

    def _delete_monster_template(self) -> None:
        item = self.template_list.currentItem()
        if item is None:
            return
        folder = self._template_folder()
        path = os.path.join(folder, item.text())
        try:
            if os.path.isfile(path):
                os.remove(path)
            self._refresh_template_list()
        except OSError as exc:
            QMessageBox.warning(self, "몬스터 템플릿 삭제 오류", str(exc))

    def _save(self) -> None:
        if self._name_field is not None:
            name = str(self._name_field.widget.text() or "").strip()
        else:
            name = str(self._config.get("hunt_grounds", "active", default="") or "").strip()
        if name:
            self._config.set("hunt_grounds", "active", name)
        presets = self._config.get("hunt_grounds", "presets", default={}) or {}
        if name and name in presets:
            answer = QMessageBox.question(
                self,
                "기존 설정 덮어쓰기",
                f"'{name}'에 저장된 설정을 현재 값으로 바꿀까요?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            save_active_preset(self._config, mapping_completed=True, name=name)
        except ValueError as exc:
            self.status.setText(str(exc))
            QMessageBox.warning(self, "사냥터 프리셋", str(exc))
            return
        self.refresh()
        self.status.setText(f"'{name}' 설정과 맵핑 완료 상태를 저장했습니다.")

    def save_current(self) -> None:
        """현재 사냥터 프리셋 저장을 호출한다."""
        self._save()

    def _load(self) -> None:
        name = self.preset_combo.currentText().strip()
        try:
            load_preset(self._config, name)
        except ValueError as exc:
            self.status.setText(str(exc))
            QMessageBox.warning(self, "사냥터 프리셋", str(exc))
            return
        self._activate_template_folder()
        self._refresh_bound_fields()
        if self._name_field is not None:
            self._name_field.widget.setText(name)
        self.refresh()
        self.status.setText(f"'{name}' 설정을 불러왔습니다.")
        self.preset_loaded.emit(name)

    def _refresh_bound_fields(self) -> None:
        for row in self.window().findChildren(QWidget):
            field = getattr(row, "_field", None)
            widget = getattr(field, "widget", None)
            loader = getattr(field, "_load", None)
            if widget is None or not callable(loader):
                continue
            widget.blockSignals(True)
            try:
                loader()
            finally:
                widget.blockSignals(False)
