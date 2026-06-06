# Planet 투명도형 v2 자체 구현 창 — 서버 인증 없이 로컬 M1+M2 모델로 바로 실행
"""
Planet_solver_v1.0.5.exe 와 동일한 UI/기능을 로컬 ncnn 모델로 재현.
서버 인증 / 라이선스 불필요 — models/transparent/ 가중치만 있으면 동작.
"""
from __future__ import annotations

import os
import threading
import time
import winsound
from datetime import datetime, timedelta

import numpy as np
import cv2
import mss
import win32api
import ctypes

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QCheckBox, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont

# ── 내부 시그널 브릿지 ─────────────────────────────────────────────────
class _Emitter(QObject):
    status   = pyqtSignal(str)   # "running" | "stopped" | "오류: ..."
    success  = pyqtSignal(int)   # 누적 성공 횟수


# ── 솔버 스레드 ────────────────────────────────────────────────────────
class _SolverThread(threading.Thread):
    """M1 detect → SetCursorPos → M2 classify 루프."""

    SHAPE = {0: "cls0", 1: "cls1", 2: "cls2", 3: "cls3"}

    def __init__(self, config, emitter: _Emitter, sound_fn):
        super().__init__(daemon=True)
        self._cfg      = config
        self._emit     = emitter
        self._sound_fn = sound_fn
        self._stop_ev  = threading.Event()
        self._m1 = self._m2 = None
        self.success_count = 0

    def stop(self):
        self._stop_ev.set()

    # ── 초기화 ──────────────────────────────────────────────────────────
    def _load_models(self) -> bool:
        here      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        models_dir = os.path.join(here, "models", "transparent")
        try:
            from core.minigame.transparent_yolo import load_default, load_m2
            self._m1 = load_default(models_dir)
            self._m2 = load_m2(models_dir)
            return True
        except Exception as e:
            self._emit.status.emit(f"❌ 모델 로드 실패: {e}")
            return False

    def _get_board_region(self):
        ts_cfg  = self._cfg.get("settings1", "transparent_shape") or {}
        roi_cfg = ts_cfg.get("board_roi")
        if not roi_cfg:
            self._emit.status.emit("❌ board_roi 미설정 — 설정1 탭에서 게임판 영역을 먼저 설정하세요")
            return None, None
        with mss.mss() as sct:
            mon = sct.monitors[1]
        bx = mon["left"] + int(roi_cfg["x_ratio"] * mon["width"])
        by = mon["top"]  + int(roi_cfg["y_ratio"] * mon["height"])
        bw = max(1, int(roi_cfg["w_ratio"] * mon["width"]))
        bh = max(1, int(roi_cfg["h_ratio"] * mon["height"]))
        region = {"left": bx, "top": by, "width": bw, "height": bh}
        return region, (bx, by)

    # ── 메인 루프 ────────────────────────────────────────────────────────
    def run(self):
        if not self._load_models():
            return

        region, origin = self._get_board_region()
        if region is None:
            return

        board_left, board_top = origin
        self._emit.status.emit("running")

        lost       = 0
        moved      = 0
        LOST_DONE  = 8
        MIN_TRACK  = 5
        first_detect = True
        last_click = 0.0   # 클릭 쓰로틀

        # SendInput용 상수
        INPUT_MOUSE       = 0
        MOUSEEVENTF_MOVE  = 0x0001
        MOUSEEVENTF_LEFTDOWN = 0x0002
        MOUSEEVENTF_LEFTUP   = 0x0004
        MOUSEEVENTF_ABSOLUTE = 0x8000

        class _MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                        ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                        ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

        class _INPUT_UNION(ctypes.Union):
            _fields_ = [("mi", _MOUSEINPUT)]

        class _INPUT(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUT_UNION)]

        def _do_click(ax: int, ay: int) -> None:
            """SendInput으로 절대 좌표 좌클릭."""
            sm_cx = ctypes.windll.user32.GetSystemMetrics(0)
            sm_cy = ctypes.windll.user32.GetSystemMetrics(1)
            nx = int(ax * 65535 / sm_cx)
            ny = int(ay * 65535 / sm_cy)
            inputs = (_INPUT * 2)()
            for i, flag in enumerate([MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP]):
                inputs[i].type = INPUT_MOUSE
                inputs[i]._input.mi = _MOUSEINPUT(
                    dx=nx, dy=ny,
                    dwFlags=MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | flag,
                )
            ctypes.windll.user32.SendInput(2, inputs, ctypes.sizeof(_INPUT))

        with mss.mss() as sct:
            while not self._stop_ev.is_set():
                try:
                    raw   = np.array(sct.grab(region))
                    board = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
                    boxes = self._m1.detect(board, score_thr=0.4)
                    if len(boxes):
                        best = boxes[boxes[:, 4].argmax()]
                        cx = int((best[0] + best[2]) / 2)
                        cy = int((best[1] + best[3]) / 2)
                        abs_x = board_left + cx
                        abs_y = board_top  + cy
                        # 첫 감지 시 소리 알람 + M2 분류
                        if first_detect:
                            first_detect = False
                            self._sound_fn()
                            try:
                                cls_id = self._m2.classify_crop(board, score_thr=0.0)
                                _ = self.SHAPE.get(cls_id, "?")
                            except Exception:
                                pass
                        # 클릭 (0.25s 쓰로틀)
                        now = time.time()
                        if now - last_click >= 0.25:
                            _do_click(abs_x, abs_y)
                            last_click = now
                        moved += 1
                        lost   = 0
                    else:
                        lost += 1
                        if lost >= LOST_DONE and moved >= MIN_TRACK:
                            self.success_count += 1
                            self._emit.success.emit(self.success_count)
                            moved = 0
                            lost  = 0
                            first_detect = True
                except Exception:
                    pass
                time.sleep(0.033)

        self._emit.status.emit("stopped")


# ── 메인 창 ────────────────────────────────────────────────────────────
class PlanetSolverWindow(QWidget):
    """Planet 투명도형 v2 스타일 창."""

    _BG   = "#1c1008"
    _TEXT = "#ffffff"
    _GREEN= "#3a9a3a"
    _RED  = "#c83030"
    _GRAY = "#888888"

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self._config  = config
        self._solver: _SolverThread | None = None
        self._emitter = _Emitter()
        self._emitter.status.connect(self._on_status)
        self._emitter.success.connect(self._on_success)
        self._start_time: float | None = None
        self._tick = QTimer()
        self._tick.timeout.connect(self._update_timer)

        self.setWindowTitle("Planet 투명도형 v2")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedWidth(340)
        self.setStyleSheet(f"background-color: {self._BG}; color: {self._TEXT};")
        self._build_ui()

    # ── UI 구성 ─────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(22, 22, 22, 22)

        # 타이틀
        lbl_title = QLabel("Planet 투명도형 v2")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setFont(QFont("맑은 고딕", 15, QFont.Weight.Bold))
        lbl_title.setStyleSheet("color: white;")
        root.addWidget(lbl_title)

        # 상태 레이블
        self.lbl_status = QLabel("대기 중")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setFont(QFont("맑은 고딕", 18, QFont.Weight.Bold))
        self.lbl_status.setStyleSheet(f"color: {self._GRAY};")
        root.addWidget(self.lbl_status)

        # 구분선
        root.addWidget(self._hr())

        # 타이머 + 성공 횟수 행
        row_stat = QHBoxLayout()
        row_stat.setSpacing(24)

        col_t = QVBoxLayout()
        lbl_t = QLabel("작동 시간")
        lbl_t.setStyleSheet(f"color: {self._GRAY}; font-size: 11px;")
        self.lbl_time = QLabel("00:00:00")
        self.lbl_time.setFont(QFont("맑은 고딕", 22, QFont.Weight.Bold))
        col_t.addWidget(lbl_t)
        col_t.addWidget(self.lbl_time)

        col_c = QVBoxLayout()
        lbl_c = QLabel("오늘 성공")
        lbl_c.setStyleSheet(f"color: {self._GRAY}; font-size: 11px;")
        self.lbl_count = QLabel("0회")
        self.lbl_count.setFont(QFont("맑은 고딕", 22, QFont.Weight.Bold))
        col_c.addWidget(lbl_c)
        col_c.addWidget(self.lbl_count)

        row_stat.addLayout(col_t)
        row_stat.addLayout(col_c)
        root.addLayout(row_stat)

        # 구분선
        root.addWidget(self._hr())

        # 옵션
        self.lbl_gpu = QLabel("CPU 모드 (ncnn fp32)")
        self.lbl_gpu.setStyleSheet(f"color: {self._GRAY}; font-size: 11px;")
        root.addWidget(self.lbl_gpu)

        self.chk_sound = QCheckBox("소리 알람 (도형찾기 감지 시)")
        self.chk_sound.setChecked(True)
        self.chk_sound.setStyleSheet("font-size: 12px;")
        root.addWidget(self.chk_sound)

        # 시작/정지 버튼
        self.btn_toggle = QPushButton("▶  시작")
        self.btn_toggle.setFixedHeight(52)
        self.btn_toggle.setFont(QFont("맑은 고딕", 14, QFont.Weight.Bold))
        self.btn_toggle.setStyleSheet(
            f"background-color: {self._GREEN}; color: white; "
            "border-radius: 8px; border: none;"
        )
        self.btn_toggle.clicked.connect(self._toggle)
        root.addWidget(self.btn_toggle)

        self.adjustSize()

    def _hr(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #444;")
        return line

    # ── 시작/정지 ────────────────────────────────────────────────────────
    def _toggle(self):
        if self._solver and self._solver.is_alive():
            self._stop()
        else:
            self._start()

    def _start(self):
        self._solver = _SolverThread(
            config   = self._config,
            emitter  = self._emitter,
            sound_fn = self._play_sound,
        )
        self._solver.start()
        self._start_time = time.time()
        self._tick.start(1000)

    def _stop(self):
        if self._solver:
            self._solver.stop()
        self._tick.stop()

    # ── 소리 ────────────────────────────────────────────────────────────
    def _play_sound(self):
        if self.chk_sound.isChecked():
            threading.Thread(
                target=lambda: [winsound.Beep(1000, 200) for _ in range(2)],
                daemon=True,
            ).start()

    # ── 타이머 ──────────────────────────────────────────────────────────
    def _update_timer(self):
        if self._start_time is None:
            return
        elapsed = int(time.time() - self._start_time)
        h, rem = divmod(elapsed, 3600)
        m, s   = divmod(rem, 60)
        self.lbl_time.setText(f"{h:02d}:{m:02d}:{s:02d}")

    # ── 시그널 핸들러 ────────────────────────────────────────────────────
    def _on_status(self, status: str):
        if status == "running":
            self.lbl_status.setText("자동 중")
            self.lbl_status.setStyleSheet("color: #50dd50; font-size: 18px; font-weight: bold;")
            self.btn_toggle.setText("■  정지")
            self.btn_toggle.setStyleSheet(
                f"background-color: {self._RED}; color: white; "
                "border-radius: 8px; border: none; font-size: 14px; font-weight: bold;"
            )
        elif status == "stopped":
            self.lbl_status.setText("대기 중")
            self.lbl_status.setStyleSheet(f"color: {self._GRAY}; font-size: 18px; font-weight: bold;")
            self.btn_toggle.setText("▶  시작")
            self.btn_toggle.setStyleSheet(
                f"background-color: {self._GREEN}; color: white; "
                "border-radius: 8px; border: none; font-size: 14px; font-weight: bold;"
            )
            self._tick.stop()
            self._start_time = None
        else:
            # 오류 메시지
            self.lbl_status.setText(status)
            self.lbl_status.setStyleSheet("color: #ff6060; font-size: 13px;")

    def _on_success(self, count: int):
        self.lbl_count.setText(f"{count}회")

    # ── 창 닫기 시 솔버 정지 ─────────────────────────────────────────────
    def closeEvent(self, event):
        self._stop()
        super().closeEvent(event)
