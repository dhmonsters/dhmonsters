# 라이선스 키 입력 다이얼로그
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class LicenseDialog(QDialog):
    """첫 실행 또는 라이선스 없을 때 표시되는 키 입력 창."""

    def __init__(self, hwid: str, parent=None):
        super().__init__(parent)
        self._hwid = hwid
        self.setWindowTitle("MapleBot — 라이선스 인증")
        self.setFixedSize(420, 240)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint
        )
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 안내 문구
        lbl_title = QLabel("MapleBot 라이선스 활성화")
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        lbl_title.setFont(font)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_info = QLabel(
            "구매 후 발급받은 라이선스 키를 입력하세요.\n"
            "인터넷 연결이 필요합니다."
        )
        lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        # HWID 표시 (고객 지원 시 사용)
        hwid_row = QHBoxLayout()
        hwid_row.addWidget(QLabel("PC 고유 ID."))
        lbl_hwid = QLabel(self._hwid)
        lbl_hwid.setStyleSheet("font-family: monospace; color: #555;")
        hwid_row.addWidget(lbl_hwid)
        hwid_row.addStretch()
        layout.addLayout(hwid_row)

        # 키 입력
        self.edit_key = QLineEdit()
        self.edit_key.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.edit_key.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit_key.setFixedHeight(36)
        self.edit_key.returnPressed.connect(self._on_activate)
        layout.addWidget(self.edit_key)

        # 버튼
        btn_row = QHBoxLayout()
        self.btn_activate = QPushButton("활성화")
        self.btn_activate.setFixedHeight(34)
        self.btn_activate.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        self.btn_activate.clicked.connect(self._on_activate)
        btn_cancel = QPushButton("취소")
        btn_cancel.setFixedHeight(34)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_activate)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

    def _on_activate(self) -> None:
        key = self.edit_key.text().strip()
        if not key:
            QMessageBox.warning(self, "입력 오류", "라이선스 키를 입력하세요.")
            return

        self.btn_activate.setEnabled(False)
        self.btn_activate.setText("인증 중...")

        try:
            from core import license_manager
            license_manager.activate(key, self._hwid)
            QMessageBox.information(self, "완료", "라이선스 활성화가 완료되었습니다.")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "활성화 실패", str(exc))
        finally:
            self.btn_activate.setEnabled(True)
            self.btn_activate.setText("활성화")
