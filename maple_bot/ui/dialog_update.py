# 자동 업데이트 팝업 및 다운로드 진행률 다이얼로그
from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QProgressBar, QTextEdit,
)

import core.updater as updater


class _DownloadSignals(QObject):
    progress = pyqtSignal(int, int)   # (downloaded, total)
    finished = pyqtSignal()
    error    = pyqtSignal(str)


class UpdateDialog(QDialog):
    """새 버전 알림 → 다운로드 진행률 → 적용 재시작 흐름을 하나의 다이얼로그로 처리."""

    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self._info = update_info
        self._installer_path = None
        self._signals  = _DownloadSignals()

        self.setWindowTitle("MapleBot 업데이트")
        self.setMinimumWidth(420)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._build_ui()
        self._connect_signals()

    # ── UI 구성 ──────────────────────────────────────────────
    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        # 버전 안내
        version_lbl = QLabel(
            f"<b>새 버전 {self._info['version']} 이 출시되었습니다.</b><br>"
            f"현재 버전: {updater.get_current_version()}"
        )
        lay.addWidget(version_lbl)

        # 업데이트 노트
        notes = self._info.get("notes", "").strip()
        if notes:
            note_box = QTextEdit()
            note_box.setReadOnly(True)
            note_box.setPlainText(notes)
            note_box.setMaximumHeight(100)
            lay.addWidget(note_box)

        # 안내 문구
        self._status_lbl = QLabel("업데이트를 설치하면 설정과 라이선스는 그대로 유지됩니다.")
        self._status_lbl.setWordWrap(True)
        lay.addWidget(self._status_lbl)

        # 진행률 바 (숨김 상태로 시작)
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.hide()
        lay.addWidget(self._progress)

        # 버튼
        btn_row = QHBoxLayout()
        self._btn_update = QPushButton("지금 업데이트")
        self._btn_later  = QPushButton("나중에")
        btn_row.addWidget(self._btn_update)
        btn_row.addWidget(self._btn_later)
        lay.addLayout(btn_row)

        self._btn_update.clicked.connect(self._start_download)
        self._btn_later.clicked.connect(self.reject)

    def _connect_signals(self):
        self._signals.progress.connect(self._on_progress)
        self._signals.finished.connect(self._on_finished)
        self._signals.error.connect(self._on_error)

    # ── 다운로드 ─────────────────────────────────────────────
    def _start_download(self):
        dl_url = self._info.get("download_url")
        if not dl_url:
            self._status_lbl.setText("❌ 다운로드 URL이 없습니다. 수동으로 업데이트해주세요.")
            return

        self._btn_update.setEnabled(False)
        self._btn_later.setEnabled(False)
        self._progress.show()
        self._status_lbl.setText("다운로드 중...")

        threading.Thread(target=self._download_thread, args=(dl_url,), daemon=True).start()

    def _download_thread(self, url: str):
        try:
            path = updater.download_update(
                url,
                progress_cb=lambda d, t: self._signals.progress.emit(d, t),
            )
            self._installer_path = path
            self._signals.finished.emit()
        except Exception as exc:
            self._signals.error.emit(str(exc))

    # ── 콜백 ─────────────────────────────────────────────────
    def _on_progress(self, downloaded: int, total: int):
        if total > 0:
            self._progress.setValue(int(downloaded / total * 100))
        self._status_lbl.setText(
            f"다운로드 중... {downloaded // 1024 // 1024} MB"
            + (f" / {total // 1024 // 1024} MB" if total else "")
        )

    def _on_finished(self):
        self._progress.setValue(100)
        self._status_lbl.setText("다운로드 완료. 설치 프로그램이 실행됩니다. 안내에 따라 설치해주세요.")
        # 잠깐 보여준 후 적용
        QTimer.singleShot(800, self._apply)

    def _apply(self):
        if self._installer_path:
            updater.apply_update(self._installer_path)  # 인스톨러 실행 후 앱 종료

    def _on_error(self, msg: str):
        self._status_lbl.setText(f"❌ 오류: {msg}")
        self._btn_update.setEnabled(True)
        self._btn_later.setEnabled(True)
        self._progress.hide()
