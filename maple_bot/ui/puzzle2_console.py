# 받은 SOT 코어의 실제 게임 추적 결과와 마우스 상태를 보여주는 화면이다.
from __future__ import annotations

from typing import Any

import cv2
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.puzzle2.runtime import SotLiveRuntime


class Puzzle2Window(QMainWindow):
    def __init__(
        self,
        *,
        runtime: SotLiveRuntime,
        preview_enabled: bool = True,
    ) -> None:
        super().__init__()
        self.runtime = runtime
        self.preview_enabled = bool(preview_enabled)
        self._last_log_key = ""
        self.setWindowTitle("Puzzle2 SOT 라이브 검증")
        self.resize(1180, 760)
        self.setMinimumSize(960, 640)
        self.setStyleSheet(_STYLE)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_header())
        root_layout.addWidget(self._build_body(), 1)
        self.setCentralWidget(root)

        self.runtime.set_mouse_enabled(False)
        self._set_mouse_ui(False)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._refresh)
        self.timer.start()

    def _build_header(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("header")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 10, 16, 10)
        title = QLabel("PUZZLE2 · V6497 SOT")
        title.setObjectName("title")
        self.run_state_label = QLabel("IDLE")
        self.run_state_label.setObjectName("runState")
        self.mouse_state_label = QLabel("MOUSE OFF")
        self.mouse_state_label.setObjectName("mouseOffState")
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(self.run_state_label)
        layout.addWidget(self.mouse_state_label)
        return bar

    def _build_body(self) -> QWidget:
        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(self._build_cctv(), 3)
        layout.addWidget(self._build_controls(), 1)
        return body

    def _build_cctv(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        title = QLabel("CCTV · 퍼즐 ROI")
        title.setObjectName("sectionTitle")
        self.preview_label = QLabel("게임창 대기")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(640, 430)
        self.preview_label.setObjectName("preview")
        self.preview_label.setScaledContents(False)
        self.target_summary_label = QLabel("표적 없음")
        self.target_summary_label.setObjectName("targetSummary")
        self.target_summary_label.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(self.preview_label, 1)
        layout.addWidget(self.target_summary_label)
        return panel

    def _build_controls(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)

        title = QLabel("제어")
        title.setObjectName("sectionTitle")
        self.solver_start_button = _button("솔버 시작", "primary")
        self.solver_stop_button = _button("솔버 종료 F12", "warning")
        self.mouse_on_button = _button("마우스 ON", "danger")
        self.mouse_off_button = _button("마우스 OFF", "safe")
        self.solver_start_button.clicked.connect(self._start_solver)
        self.solver_stop_button.clicked.connect(self._stop_solver)
        self.mouse_on_button.clicked.connect(lambda: self._toggle_mouse(True))
        self.mouse_off_button.clicked.connect(lambda: self._toggle_mouse(False))

        layout.addWidget(title)
        layout.addWidget(self.solver_start_button)
        layout.addWidget(self.solver_stop_button)
        layout.addSpacing(6)
        layout.addWidget(self.mouse_on_button)
        layout.addWidget(self.mouse_off_button)

        state_title = QLabel("추적 상태")
        state_title.setObjectName("sectionTitle")
        self.state_grid = QGridLayout()
        self.state_values: dict[str, QLabel] = {}
        labels = (
            ("상태", "tracking"),
            ("도형", "shape"),
            ("출력", "source"),
            ("신뢰도", "confidence"),
            ("후보", "hypotheses"),
            ("겹침", "overlap"),
            ("신분 잠금", "lock"),
            ("완료", "completed"),
            ("입력", "input_backend"),
            ("커서 보정", "cursor_offset"),
            ("판단", "reason"),
        )
        for row_index, (name, key) in enumerate(labels):
            name_label = QLabel(name)
            name_label.setObjectName("key")
            value_label = QLabel("-")
            value_label.setObjectName("value")
            value_label.setWordWrap(True)
            self.state_grid.addWidget(name_label, row_index, 0)
            self.state_grid.addWidget(value_label, row_index, 1)
            self.state_values[key] = value_label

        layout.addSpacing(8)
        layout.addWidget(state_title)
        layout.addLayout(self.state_grid)
        log_title = QLabel("로그")
        log_title.setObjectName("sectionTitle")
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("log")
        layout.addWidget(log_title)
        layout.addWidget(self.log_view, 1)
        return panel

    def _start_solver(self) -> None:
        if self.runtime.start():
            self._append_log("솔버 시작. 퍼즐 감지를 기다립니다.")
        else:
            self._append_log("솔버가 이미 실행 중입니다.")

    def _stop_solver(self) -> None:
        self.runtime.request_stop()
        self._append_log("솔버 종료 요청.")

    def _toggle_mouse(self, enabled: bool) -> None:
        self.runtime.set_mouse_enabled(enabled)
        self._set_mouse_ui(enabled)
        self._append_log("마우스 출력 ON." if enabled else "마우스 출력 OFF.")

    def _set_mouse_ui(self, enabled: bool) -> None:
        self.mouse_on_button.setEnabled(not enabled)
        self.mouse_off_button.setEnabled(enabled)
        self.mouse_state_label.setText("MOUSE ON" if enabled else "MOUSE OFF")
        self.mouse_state_label.setObjectName("mouseOnState" if enabled else "mouseOffState")
        self.mouse_state_label.style().unpolish(self.mouse_state_label)
        self.mouse_state_label.style().polish(self.mouse_state_label)

    def _refresh(self) -> None:
        snapshot = self.runtime.snapshot()
        self._refresh_state(snapshot)
        if self.preview_enabled:
            self._refresh_preview(snapshot)

    def _refresh_state(self, snapshot: dict[str, Any]) -> None:
        status = snapshot.get("status") or {}
        row = snapshot.get("row") or {}
        running = bool(snapshot.get("running"))
        self.run_state_label.setText("RUNNING" if running else str(status.get("tracking", "IDLE")))
        self.state_values["tracking"].setText(str(status.get("tracking", row.get("state", "-"))))
        self.state_values["shape"].setText(str(status.get("shape", "-")))
        self.state_values["source"].setText(str(row.get("output_source", "-")))
        confidence = row.get("confidence")
        self.state_values["confidence"].setText("-" if confidence is None else f"{float(confidence):.3f}")
        self.state_values["hypotheses"].setText(str(row.get("hypothesis_count", "-")))
        self.state_values["overlap"].setText(str(row.get("overlap_hold", "-")))
        self.state_values["lock"].setText("ON" if row.get("identity_lock_active") else "OFF")
        self.state_values["completed"].setText(str(snapshot.get("completed_puzzles", 0)))
        self.state_values["input_backend"].setText(str(status.get("input_backend", "대기")))
        self.state_values["cursor_offset"].setText(str(status.get("cursor_offset", "0.0,0.0")))
        reason = row.get("owner_guard_reason") or row.get("owner_guard_action") or "-"
        self.state_values["reason"].setText(str(reason))
        if row:
            self.target_summary_label.setText(
                f"frame {row.get('frame', '-')} · target "
                f"({float(row.get('center_x', 0)):.1f}, {float(row.get('center_y', 0)):.1f}) · "
                f"{row.get('state', '-')}"
            )
        session = snapshot.get("session_dir") or ""
        log_key = f"{status.get('tracking')}|{status.get('result')}|{snapshot.get('error')}"
        if log_key != self._last_log_key:
            self._last_log_key = log_key
            message = str(snapshot.get("error") or status.get("result") or status.get("tracking") or "")
            if message and message != "-":
                self._append_log(message)
            if session:
                self._append_log(f"로그 위치 {session}")

    def _refresh_preview(self, snapshot: dict[str, Any]) -> None:
        try:
            frame, _rect = self.runtime.capture_client()
        except Exception as exc:
            self.preview_label.setText(str(exc))
            return
        x, y, width, height = self.runtime.QUEST_ROI
        roi = frame[y : y + height, x : x + width].copy()
        if roi.shape[:2] != (height, width):
            self.preview_label.setText("퍼즐 ROI가 게임창 밖입니다")
            return
        row = snapshot.get("row") or {}
        _draw_candidates(roi, row, roi_origin=(x, y))
        rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        image = QImage(
            rgb.data,
            rgb.shape[1],
            rgb.shape[0],
            rgb.strides[0],
            QImage.Format.Format_RGB888,
        ).copy()
        pixmap = QPixmap.fromImage(image)
        self.preview_label.setPixmap(
            pixmap.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _append_log(self, message: str) -> None:
        if message:
            self.log_view.append(str(message))

    def closeEvent(self, event) -> None:
        self.runtime.request_stop()
        self.runtime.set_mouse_enabled(False)
        self.runtime.close_preview()
        super().closeEvent(event)


def _draw_candidates(frame, row: dict[str, Any], *, roi_origin: tuple[int, int]) -> None:
    ox, oy = roi_origin
    colors = ((80, 180, 255), (170, 170, 170), (120, 120, 120))
    for index, color in zip(range(1, 4), colors):
        px = row.get(f"h{index}_x")
        py = row.get(f"h{index}_y")
        if px in (None, "") or py in (None, ""):
            continue
        point = (int(round(float(px) - ox)), int(round(float(py) - oy)))
        cv2.circle(frame, point, 12, color, 2, cv2.LINE_AA)
        cv2.putText(frame, f"H{index}", (point[0] + 8, point[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1, cv2.LINE_AA)

    tx = row.get("center_x")
    ty = row.get("center_y")
    if tx in (None, "") or ty in (None, ""):
        return
    target = (int(round(float(tx) - ox)), int(round(float(ty) - oy)))
    cv2.circle(frame, target, 18, (40, 255, 90), 3, cv2.LINE_AA)
    cv2.line(frame, (target[0] - 24, target[1]), (target[0] + 24, target[1]), (40, 255, 90), 2)
    cv2.line(frame, (target[0], target[1] - 24), (target[0], target[1] + 24), (40, 255, 90), 2)


def _button(text: str, role: str) -> QPushButton:
    button = QPushButton(text)
    button.setProperty("role", role)
    button.setMinimumHeight(42)
    return button


_STYLE = """
QMainWindow, QWidget { background:#15181c; color:#eef2f6; font-size:13px; }
#header { background:#1d2127; border-bottom:1px solid #303640; }
#title { font-size:16px; font-weight:800; }
#runState, #mouseOffState, #mouseOnState { padding:7px 11px; border-radius:4px; font-weight:800; }
#runState { background:#29313a; color:#b8c6d4; }
#mouseOffState { background:#37404a; color:#d5dde5; }
#mouseOnState { background:#b83232; color:white; }
#panel { background:#1b1f24; border:1px solid #303640; border-radius:6px; }
#sectionTitle { font-size:14px; font-weight:800; margin:4px 0; }
#preview { background:#090b0d; border:1px solid #343b45; }
#targetSummary { color:#b9c4cf; padding:6px; }
#key { color:#8f9baa; }
#value { color:#f0f4f8; font-weight:650; }
#log { background:#101317; border:1px solid #303640; color:#cdd6df; }
QPushButton { background:#2b3037; border:1px solid #3b434d; border-radius:5px; font-weight:750; }
QPushButton:hover { background:#343b44; }
QPushButton:disabled { color:#707984; background:#20242a; }
QPushButton[role="primary"] { background:#16864a; border-color:#1b9b58; }
QPushButton[role="warning"] { background:#b56d13; border-color:#cf7c14; }
QPushButton[role="danger"] { background:#a92f35; border-color:#c53a42; }
QPushButton[role="safe"] { background:#35606f; border-color:#44788a; }
"""
