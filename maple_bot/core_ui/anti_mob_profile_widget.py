# 초급 수련장 방지몹 고정 프로필 선택을 관리하는 위젯
from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget


class AntiMobProfileWidget(QWidget):
    """방지몹 해제에 사용할 고정 프로필을 선택한다."""

    PROFILE_ID = "beginner_training"

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._cfg = config
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("방지몹 해제 프로필"))

        self._profile = QComboBox()
        self._profile.addItem("초급 수련장", self.PROFILE_ID)
        self._profile.currentIndexChanged.connect(self._save_profile)
        layout.addWidget(self._profile)

        layout.addWidget(QLabel("초급 수련장 고정 템플릿을 사용합니다."))

    def refresh(self) -> None:
        profile_id = str(self._cfg.get("anti_mob", "profile", default="") or "")
        index = self._profile.findData(profile_id)
        if index < 0:
            index = self._profile.findData(self.PROFILE_ID)
            self._cfg.set("anti_mob", "profile", self.PROFILE_ID)
            self._cfg.save()

        self._profile.blockSignals(True)
        self._profile.setCurrentIndex(index)
        self._profile.blockSignals(False)

    def _save_profile(self, index: int) -> None:
        profile_id = self._profile.itemData(index)
        if not profile_id:
            return
        self._cfg.set("anti_mob", "profile", str(profile_id))
        self._cfg.save()
