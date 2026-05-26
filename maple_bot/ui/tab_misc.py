# 기타 탭 - 키 입력 기록기, 단축키 현황, 거짓말탐지기 해제 로그
from __future__ import annotations
import glob
import queue
import re
import threading
import time
from collections import defaultdict
from datetime import datetime

import win32api
import win32con
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QListWidget, QLabel, QCheckBox,
    QDialog, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

# 감시할 키 목록 (이름 → VK코드)
_WATCH_KEYS: dict[str, int] = {
    "left":   win32con.VK_LEFT,
    "right":  win32con.VK_RIGHT,
    "up":     win32con.VK_UP,
    "down":   win32con.VK_DOWN,
    "ctrl":   win32con.VK_CONTROL,
    "alt":    win32con.VK_MENU,
    "shift":  win32con.VK_SHIFT,
    "space":  win32con.VK_SPACE,
    "end":    win32con.VK_END,
    "home":   win32con.VK_HOME,
    "pgup":   win32con.VK_PRIOR,
    "pgdn":   win32con.VK_NEXT,
    "enter":  win32con.VK_RETURN,
    **{f"f{n}": win32con.VK_F1 + n - 1 for n in range(1, 13)},
    **{c: ord(c.upper()) for c in "abcdefghijklmnopqrstuvwxyz"},
    **{str(n): ord(str(n)) for n in range(10)},
}

POLL_MS = 5   # 폴링 간격 (ms)

# 단축키 내부 이름 → 표시 이름
_HOTKEY_LABELS: dict[str, str] = {
    "bot_start":     "봇 시작",
    "bot_stop":      "봇 정지",
    "lie_solve":     "거탐 해제",
    "lie_region":    "거탐 영역 설정",
    "coord_minimap": "미니맵 영역 설정",
    "coord_zone":    "사냥 구역 설정",
    "recovery_hp":   "HP 바 영역 설정",
    "recovery_mp":   "MP 바 영역 설정",
}


class _LieDetectorMonitor:
    """백그라운드에서 거짓말탐지기 템플릿을 주기적으로 감시하고 감지 시 콜백을 호출한다."""

    CHECK_INTERVAL = 1.0   # 화면 검사 주기 (초)
    COOLDOWN       = 10.0  # 같은 탐지기 중복 기록 방지 (초)

    def __init__(self, on_detected):
        self._on_detected = on_detected   # 감지 시 호출할 콜백 (msg: str)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_detected = 0.0

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="LieDetectorMonitor"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        from core.screen_reader import ScreenReader
        screen = ScreenReader()

        while not self._stop.is_set():
            try:
                patterns = sorted(glob.glob("templates/lie_detector_*.png"))
                if patterns:
                    screenshot = screen.capture()
                    for tpl_path in patterns:
                        score = screen.find_template_score(screenshot, tpl_path)
                        if score >= 0.65:
                            now = time.time()
                            if now - self._last_detected >= self.COOLDOWN:
                                self._last_detected = now
                                ts = datetime.now().strftime("%H:%M:%S")
                                self._on_detected(
                                    f"[{ts}] ⚠ 거짓말탐지기 감지! (점수 {score:.2f})"
                                )
                            break
            except Exception:
                pass
            self._stop.wait(self.CHECK_INTERVAL)


class _KeyRecorder:
    """백그라운드 스레드에서 GetAsyncKeyState로 키 입력을 기록한다."""

    def __init__(self, result_queue: queue.Queue):
        self._q = result_queue
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="KeyRecorder"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        pressed: dict[str, float] = {}   # key → press timestamp
        prev: dict[str, bool] = {k: False for k in _WATCH_KEYS}
        last_event_time: float = 0.0

        while not self._stop.is_set():
            now = time.time()
            for name, vk in _WATCH_KEYS.items():
                is_down = bool(win32api.GetAsyncKeyState(vk) & 0x8000)
                was_down = prev[name]

                if is_down and not was_down:
                    # 키 누름
                    pressed[name] = now

                elif not is_down and was_down:
                    # 키 뗌 → 기록
                    hold = now - pressed.pop(name, now)
                    gap = (now - last_event_time) if last_event_time else 0.0
                    self._q.put((name, hold, gap))
                    last_event_time = now

                prev[name] = is_down
            time.sleep(POLL_MS / 1000)


class TabMisc(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self._record_queue: queue.Queue = queue.Queue()
        self._recorder = _KeyRecorder(self._record_queue)
        self._recording = False
        self._hk = None

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_hotkey_status_group())
        layout.addWidget(self._build_recorder_group())
        layout.addStretch()

        # 50ms마다 큐에서 결과를 읽어 리스트에 추가
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._flush_queue)
        self._timer.start()

    # ── 단축키 현황 주입 ──────────────────────────────────────────────
    def set_hotkey_manager(self, hk) -> None:
        self._hk = hk
        self._refresh_hotkeys()

    # ── UI ───────────────────────────────────────────────────────────
    def _build_hotkey_status_group(self) -> QGroupBox:
        group = QGroupBox("단축키 현황")
        layout = QVBoxLayout(group)

        self._hk_table = QTableWidget(0, 2)
        self._hk_table.setHorizontalHeaderLabels(["기능", "키"])
        self._hk_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._hk_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._hk_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._hk_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._hk_table.setMaximumHeight(170)
        layout.addWidget(self._hk_table)

        btn_refresh = QPushButton("🔄 새로고침")
        btn_refresh.setFixedHeight(28)
        btn_refresh.clicked.connect(self._refresh_hotkeys)
        layout.addWidget(btn_refresh)

        return group

    def _refresh_hotkeys(self) -> None:
        """HotkeyManager에서 현재 등록된 단축키를 읽어 테이블에 표시한다."""
        self._hk_table.setRowCount(0)
        if self._hk is None:
            return
        hotkeys = self._hk.get_hotkeys()
        for name, key in hotkeys.items():
            label = _HOTKEY_LABELS.get(name, name)
            row = self._hk_table.rowCount()
            self._hk_table.insertRow(row)
            self._hk_table.setItem(row, 0, QTableWidgetItem(label))
            key_item = QTableWidgetItem(f"[{key.upper()}]")
            key_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._hk_table.setItem(row, 1, key_item)

    def _build_recorder_group(self) -> QGroupBox:
        group = QGroupBox("키 입력 기록기")
        layout = QVBoxLayout(group)

        # 안내
        lbl = QLabel(
            "기록 시작 후 게임에서 평소처럼 사냥하세요.\n"
            "어떤 키를 얼마나 눌렀는지 실시간으로 기록됩니다."
        )
        lbl.setWordWrap(True)
        layout.addWidget(lbl)

        # 버튼 행
        btn_row = QHBoxLayout()
        self.btn_record = QPushButton("⏺ 기록 시작")
        self.btn_record.setFixedHeight(34)
        self.btn_record.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        self.btn_record.clicked.connect(self._toggle_record)

        btn_clear = QPushButton("🗑 지우기")
        btn_clear.setFixedHeight(34)
        btn_clear.clicked.connect(self._clear)

        btn_analyze = QPushButton("📊 분석")
        btn_analyze.setFixedHeight(34)
        btn_analyze.setFixedWidth(80)
        btn_analyze.clicked.connect(self._analyze_log)

        self.lbl_count = QLabel("0건")
        self.lbl_count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        btn_row.addWidget(self.btn_record)
        btn_row.addWidget(btn_clear)
        btn_row.addWidget(btn_analyze)
        btn_row.addStretch()
        btn_row.addWidget(self.lbl_count)
        layout.addLayout(btn_row)

        # 기록 목록
        self.log_list = QListWidget()
        self.log_list.setMinimumHeight(300)
        font = QFont("Consolas", 9)
        self.log_list.setFont(font)
        layout.addWidget(self.log_list)

        # 방향키 숨기기 옵션
        self.chk_hide_direction = QCheckBox("방향키 숨기기 (left/right/up/down)")
        layout.addWidget(self.chk_hide_direction)

        return group

    # ── 제어 ─────────────────────────────────────────────────────────
    def _toggle_record(self) -> None:
        if not self._recording:
            self._recorder.start()
            self._recording = True
            self.btn_record.setText("⏹ 기록 중지")
            self.btn_record.setStyleSheet(
                "background-color: #f44336; color: white; font-weight: bold;"
            )
        else:
            self._recorder.stop()
            self._recording = False
            self.btn_record.setText("⏺ 기록 시작")
            self.btn_record.setStyleSheet(
                "background-color: #4CAF50; color: white; font-weight: bold;"
            )

    def _clear(self) -> None:
        self.log_list.clear()
        self.lbl_count.setText("0건")

    def _flush_queue(self) -> None:
        """큐에서 기록 결과를 읽어 리스트에 추가한다."""
        direction_keys = {"left", "right", "up", "down"}
        hide_dir = self.chk_hide_direction.isChecked()
        changed = False

        while not self._record_queue.empty():
            try:
                name, hold, gap = self._record_queue.get_nowait()
            except queue.Empty:
                break

            if hide_dir and name in direction_keys:
                continue

            gap_str = f"간격 {gap * 1000:.0f}ms" if gap > 0 else "처음"
            line = f"[{name:<8}]  홀드 {hold * 1000:.0f}ms   {gap_str}"
            self.log_list.addItem(line)
            changed = True

        if changed:
            count = self.log_list.count()
            self.lbl_count.setText(f"{count}건")
            self.log_list.scrollToBottom()

    # ── 로그 분석 ─────────────────────────────────────────────────────
    def _analyze_log(self) -> None:
        count = self.log_list.count()
        if count == 0:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self, "분석", "기록된 데이터가 없습니다.")
            return

        # ── 파싱 ─────────────────────────────────────────────────────
        pat = re.compile(r'\[(\w+)\s*\]\s+홀드\s+(\d+)ms\s+(?:간격\s+(\d+)ms|처음)')
        key_holds: dict[str, list[int]] = defaultdict(list)
        sequence: list[tuple[str, int, int]] = []   # (key, hold_ms, gap_ms)

        for i in range(count):
            m = pat.match(self.log_list.item(i).text())
            if not m:
                continue
            key  = m.group(1)
            hold = int(m.group(2))
            gap  = int(m.group(3)) if m.group(3) else 0
            key_holds[key].append(hold)
            sequence.append((key, hold, gap))

        if not key_holds:
            return

        lines: list[str] = [f"📊 로그 분석 결과  (총 {len(sequence)}건)\n{'─'*44}"]

        # ── 키별 통계 ─────────────────────────────────────────────────
        lines.append("\n■ 키별 홀드 시간")
        for key in sorted(key_holds):
            holds = key_holds[key]
            avg_h = sum(holds) / len(holds)
            min_h, max_h = min(holds), max(holds)
            var_h = (max_h - min_h) / 2
            lines.append(
                f"  [{key}]  평균 {int(avg_h)}ms  범위 {min_h}~{max_h}ms\n"
                f"         → 홀드 기준 {avg_h/1000:.2f}초  변동폭 {var_h/1000:.2f}초"
            )

        # ── 연속기 패턴 감지 ──────────────────────────────────────────
        # 연속으로 다른 키가 나오는 쌍 집계
        pair_counts: dict[tuple, int] = defaultdict(int)
        pair_gaps: dict[tuple, list[int]] = defaultdict(list)
        for i in range(len(sequence) - 1):
            a, b = sequence[i][0], sequence[i + 1][0]
            if a != b:
                pair = (a, b)
                pair_counts[pair] += 1
                pair_gaps[pair].append(sequence[i + 1][2])

        if pair_counts:
            top_pair = max(pair_counts, key=pair_counts.__getitem__)
            top_cnt  = pair_counts[top_pair]

            if top_cnt >= 3:
                a, b = top_pair
                a_holds = key_holds.get(a, [])
                b_holds = key_holds.get(b, [])
                gaps    = pair_gaps[top_pair]

                a_base = sum(a_holds) / len(a_holds) / 1000 if a_holds else 0.06
                a_var  = (max(a_holds) - min(a_holds)) / 2 / 1000 if a_holds else 0.01
                b_base = sum(b_holds) / len(b_holds) / 1000 if b_holds else 0.06
                b_var  = (max(b_holds) - min(b_holds)) / 2 / 1000 if b_holds else 0.01
                g_min  = round(min(gaps) / 1000, 2) if gaps else 0.2
                g_max  = round(max(gaps) / 1000, 2) if gaps else 0.8

                lines.append(f"\n■ 연속기 패턴 감지: {a} → {b}  ({top_cnt}회)")
                lines.append(
                    f"  → [연속기] {a}({int(a_base*1000)}±{int(a_var*1000)}ms)"
                    f" → {b}({int(b_base*1000)}±{int(b_var*1000)}ms)\n"
                    f"     간격 {g_min}~{g_max}초"
                )

        # ── 전체 간격 통계 ────────────────────────────────────────────
        all_gaps = [g for _, _, g in sequence if g > 0]
        if all_gaps:
            avg_g = sum(all_gaps) / len(all_gaps)
            lines.append(
                f"\n■ 전체 키 간격\n"
                f"  평균 {int(avg_g)}ms  범위 {min(all_gaps)}~{max(all_gaps)}ms\n"
                f"  → 간격 {min(all_gaps)/1000:.2f}~{max(all_gaps)/1000:.2f}초"
            )

        # ── 다이얼로그 표시 ───────────────────────────────────────────
        dlg = QDialog(self)
        dlg.setWindowTitle("로그 분석")
        dlg.resize(440, 400)
        v = QVBoxLayout(dlg)
        txt = QTextEdit()
        txt.setReadOnly(True)
        txt.setFontFamily("Consolas")
        txt.setFontPointSize(9)
        txt.setPlainText("\n".join(lines))
        v.addWidget(txt)
        btn_ok = QPushButton("닫기")
        btn_ok.clicked.connect(dlg.accept)
        v.addWidget(btn_ok)
        dlg.exec()


    # ── config 연동 (없음) ───────────────────────────────────────────
    def save_to_config(self):
        pass

    def load_from_config(self):
        pass
