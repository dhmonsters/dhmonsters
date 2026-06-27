# 투명도형 퍼즐 분석 콘솔의 주요 패널과 실행 진입점이 생성되는지 검증한다.
import importlib
import json
import os
import sys
import types


class _Signal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)

    def emit(self) -> None:
        for callback in list(self.callbacks):
            callback()


class _Widget:
    def __init__(self, *args, **kwargs) -> None:
        self._object_name = ""
        self._children = []
        self._text = args[0] if args else ""
        self.clicked = _Signal()

    def setObjectName(self, name: str) -> None:
        self._object_name = name

    def objectName(self) -> str:
        return self._object_name

    def setWindowTitle(self, title: str) -> None:
        self._window_title = title

    def windowTitle(self) -> str:
        return getattr(self, "_window_title", "")

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def resize(self, *args) -> None:
        self._size = args

    def setMinimumSize(self, *args) -> None:
        self._minimum_size = args

    def setStyleSheet(self, value: str) -> None:
        self._style_sheet = value

    def styleSheet(self) -> str:
        return getattr(self, "_style_sheet", "")

    def setCentralWidget(self, widget) -> None:
        self.central_widget = widget
        self._children.append(widget)

    def setReadOnly(self, value: bool) -> None:
        self._read_only = value

    def setWordWrap(self, value: bool) -> None:
        self._word_wrap = value

    def setAlignment(self, value) -> None:
        self._alignment = value

    def setMinimumHeight(self, value: int) -> None:
        self._minimum_height = value

    def setFixedHeight(self, value: int) -> None:
        self._fixed_height = value

    def setCheckable(self, value: bool) -> None:
        self._checkable = value

    def setChecked(self, value: bool) -> None:
        self._checked = value

    def isChecked(self) -> bool:
        return bool(getattr(self, "_checked", False))

    def setPixmap(self, pixmap) -> None:
        self._pixmap = pixmap

    def pixmap(self):
        return getattr(self, "_pixmap", None)

    def setScaledContents(self, value: bool) -> None:
        self._scaled_contents = value

    def append(self, text: str) -> None:
        self._text = f"{self._text}\n{text}" if self._text else text

    def toPlainText(self) -> str:
        return self._text


class _Layout:
    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.items = []

    def setContentsMargins(self, *args) -> None:
        self.margins = args

    def setSpacing(self, value: int) -> None:
        self.spacing = value

    def addWidget(self, widget, *args) -> None:
        self.items.append(widget)
        if self.parent is not None and hasattr(self.parent, "_children"):
            self.parent._children.append(widget)

    def addLayout(self, layout, *args) -> None:
        self.items.append(layout)

    def addStretch(self, *args) -> None:
        self.items.append("stretch")

    def addSpacing(self, *args) -> None:
        self.items.append("spacing")


class _Splitter(_Widget):
    def addWidget(self, widget) -> None:
        self._children.append(widget)

    def setStretchFactor(self, *args) -> None:
        pass


class _Application:
    _instance = None

    def __init__(self, args=None) -> None:
        _Application._instance = self
        self.args = args or []
        self._style = ""
        self._style_sheet = ""

    @classmethod
    def instance(cls):
        return cls._instance

    def setStyle(self, value: str) -> None:
        self._style = value

    def setStyleSheet(self, value: str) -> None:
        self._style_sheet = value

    def exec(self) -> int:
        return 0


class _Timer:
    def __init__(self, _parent=None) -> None:
        self.timeout = _Signal()
        self.interval = 0
        self.started = False

    def setInterval(self, interval: int) -> None:
        self.interval = interval

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


class _Pixmap:
    def __init__(self, path: str = "") -> None:
        self.path = path

    def loadFromData(self, data: bytes) -> bool:
        if not data:
            self.path = ""
            return False
        self.path = f"bytes:{len(data)}:{data[:16].hex()}"
        return True

    def isNull(self) -> bool:
        return not bool(self.path)


def _install_fake_qt(monkeypatch) -> None:
    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    qtwidgets.QApplication = _Application
    qtwidgets.QFrame = _Widget
    qtwidgets.QGridLayout = _Layout
    qtwidgets.QHBoxLayout = _Layout
    qtwidgets.QLabel = _Widget
    qtwidgets.QMainWindow = _Widget
    qtwidgets.QPushButton = _Widget
    qtwidgets.QCheckBox = _Widget
    qtwidgets.QSplitter = _Splitter
    qtwidgets.QTextEdit = _Widget
    qtwidgets.QVBoxLayout = _Layout
    qtwidgets.QWidget = _Widget

    class _Orientation:
        Horizontal = "horizontal"
        Vertical = "vertical"

    class _AlignmentFlag:
        AlignCenter = "center"

    class _Key:
        Key_F1 = "f1"
        Key_F2 = "f2"
        Key_F3 = "f3"

    qtcore = types.ModuleType("PyQt6.QtCore")
    qtcore.Qt = types.SimpleNamespace(Orientation=_Orientation, AlignmentFlag=_AlignmentFlag, Key=_Key)
    qtcore.QTimer = _Timer

    qtgui = types.ModuleType("PyQt6.QtGui")
    qtgui.QPixmap = _Pixmap

    pyqt = types.ModuleType("PyQt6")
    pyqt.QtWidgets = qtwidgets
    pyqt.QtCore = qtcore
    pyqt.QtGui = qtgui
    monkeypatch.setitem(sys.modules, "PyQt6", pyqt)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6.QtGui", qtgui)
    sys.modules.pop("ui.puzzle_console", None)
    sys.modules.pop("puzzle", None)


def test_puzzle_console_window_exposes_main_regions(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.objectName() == "puzzleConsoleWindow"
    assert window.cctv_view.objectName() == "puzzleCctvView"
    assert window.control_panel.objectName() == "puzzleControlPanel"
    assert window.event_log.objectName() == "puzzleEventLog"
    assert window.telegram_alert_checkbox.objectName() == "telegramAlertCheckbox"
    assert window.gpu_enabled_checkbox.objectName() == "gpuEnabledCheckbox"
    assert window.puzzle_detect_alert_checkbox.objectName() == "puzzleDetectAlertCheckbox"
    assert "투명도형" in window.windowTitle()


def test_puzzle_console_window_exposes_expected_commands(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.start_watch_button.objectName() == "startWatchButton"
    assert window.stop_solver_button.objectName() == "stopSolverButton"
    assert window.stop_recording_button.objectName() == "stopRecordingButton"
    assert window.solver_start_badge.objectName() == "solverStartBadge"
    assert window.solver_stop_badge.objectName() == "solverStopBadge"
    assert window.recording_stop_badge.objectName() == "recordingStopBadge"
    assert "F3" in window.stop_recording_button.text()


def test_puzzle_console_preview_keeps_pixmap_visible(monkeypatch, tmp_path):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")
    preview_path = tmp_path / "live_watch_preview.png"
    preview_path.write_bytes(b"fake image")

    window = module.PuzzleConsoleWindow()

    window._load_cctv_frame_preview(str(preview_path))

    assert window.cctv_frame_label.pixmap().path.startswith("bytes:")
    assert window.cctv_frame_label.text() == ""


def test_puzzle_console_preview_reloads_when_same_path_changes(monkeypatch, tmp_path):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")
    preview_path = tmp_path / "live_watch_preview.png"
    preview_path.write_bytes(b"first frame")

    window = module.PuzzleConsoleWindow()

    window._load_cctv_frame_preview(str(preview_path))
    first_pixmap_path = window.cctv_frame_label.pixmap().path
    preview_path.write_bytes(b"second frame")
    os.utime(preview_path, (2_000_000_000, 2_000_000_000))
    window._load_cctv_frame_preview(str(preview_path))

    assert window.current_cctv_source_path == str(preview_path)
    assert window.cctv_frame_label.pixmap().path != first_pixmap_path
    assert window.cctv_frame_label.text() == ""


def test_puzzle_console_stop_recording_button_calls_handler(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")
    calls = []

    window = module.PuzzleConsoleWindow(recording_stop_handler=lambda: calls.append("stop") or True)

    window.stop_recording_button.clicked.emit()

    assert calls == ["stop"]
    assert "recording stop" in window.event_log.toPlainText()


def test_puzzle_console_f3_calls_recording_stop_handler(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")
    calls = []

    class _Event:
        def key(self):
            return module.Qt.Key.Key_F3

    window = module.PuzzleConsoleWindow(recording_stop_handler=lambda: calls.append("stop") or True)

    window.keyPressEvent(_Event())

    assert calls == ["stop"]


def test_puzzle_console_start_watch_button_calls_live_recording_handler(monkeypatch, tmp_path):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")
    calls = []
    session_dir = tmp_path / "session"
    session_dir.mkdir()

    def start_watch():
        calls.append("start")
        return session_dir

    window = module.PuzzleConsoleWindow(watch_start_handler=start_watch)

    window.start_watch_button.clicked.emit()

    assert calls == ["start"]
    assert window.state_label.text() == "RECORDING"
    assert window.last_session_dir == session_dir
    assert "recording start" in window.event_log.toPlainText()


def test_puzzle_console_capture_check_button_calls_handler(monkeypatch, tmp_path):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")
    calls = []
    report_path = tmp_path / "capture_check.md"
    report_path.write_text("# capture\n", encoding="utf-8")

    def capture_check():
        calls.append("check")
        return report_path

    window = module.PuzzleConsoleWindow(capture_check_handler=capture_check)

    window.capture_check_button.clicked.emit()

    assert calls == ["check"]
    assert window.state_label.text() == "CAPTURE_OK"
    assert window.last_report_path == report_path
    assert "capture check" in window.event_log.toPlainText()


def test_puzzle_entrypoint_builds_parser_and_window(monkeypatch):
    _install_fake_qt(monkeypatch)
    puzzle = importlib.import_module("puzzle")

    parser = puzzle.build_arg_parser()
    args = parser.parse_args([])
    window = puzzle.create_window(args)

    assert args.headless is False
    assert window.objectName() == "puzzleConsoleWindow"


def test_puzzle_live_record_command_invokes_runtime(monkeypatch, tmp_path):
    _install_fake_qt(monkeypatch)
    puzzle = importlib.import_module("puzzle")
    calls = []

    def fake_run_live_recording(*, output_root=None, max_frames=None):
        calls.append((output_root, max_frames))
        report_path = tmp_path / "report.md"
        report_path.write_text("# report\n", encoding="utf-8")
        return report_path

    monkeypatch.setattr(puzzle, "run_live_recording", fake_run_live_recording)

    code = puzzle.run_gui([
        "--live-record",
        "--output-root",
        str(tmp_path),
        "--live-max-frames",
        "2",
    ])

    assert code == 0
    assert calls == [(str(tmp_path), 2)]


def test_puzzle_live_capture_check_command_returns_success(monkeypatch, tmp_path):
    _install_fake_qt(monkeypatch)
    puzzle = importlib.import_module("puzzle")
    calls = []

    class _Result:
        ok = True
        report_path = tmp_path / "capture_check.md"
        error = ""

    def fake_capture_check(*, output_root=None):
        calls.append(output_root)
        _Result.report_path.write_text("# ok\n", encoding="utf-8")
        return _Result()

    monkeypatch.setattr(puzzle, "run_live_capture_check", fake_capture_check)

    code = puzzle.run_gui([
        "--live-capture-check",
        "--output-root",
        str(tmp_path),
    ])

    assert code == 0
    assert calls == [str(tmp_path)]


def test_puzzle_live_capture_check_command_returns_failure(monkeypatch, tmp_path):
    _install_fake_qt(monkeypatch)
    puzzle = importlib.import_module("puzzle")

    class _Sink:
        def write(self, _text):
            return None

        def flush(self):
            return None

    class _Result:
        ok = False
        report_path = tmp_path / "capture_check.md"
        error = "screen capture failed"

    def fake_capture_check(*, output_root=None):
        _Result.report_path.write_text("# failed\n", encoding="utf-8")
        return _Result()

    monkeypatch.setattr(puzzle, "run_live_capture_check", fake_capture_check)
    monkeypatch.setattr(sys, "stderr", _Sink())

    code = puzzle.run_gui(["--live-capture-check"])

    assert code == 2


def test_puzzle_console_connects_image_sequence_button_to_replay_runner(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")
    calls = []

    def pick_path(kind):
        assert kind == "image_sequence"
        return "C:/frames"

    def run_replay(path, kind):
        calls.append((path, kind))
        return "C:/out/report.md"

    window = module.PuzzleConsoleWindow(replay_runner=run_replay, path_picker=pick_path)

    window.open_image_sequence_button.clicked.emit()

    assert calls == [("C:/frames", "image_sequence")]
    assert window.state_label.text() == "REPLAY_DONE"
    assert "report.md" in window.cctv_status_label.text()
    assert "report.md" in window.event_log.toPlainText()


def test_puzzle_console_default_test_button_runs_default_replay(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")
    calls = []

    def run_replay(path, kind):
        calls.append((path, kind))
        return "C:/out/report.md"

    window = module.PuzzleConsoleWindow(
        replay_runner=run_replay,
        default_test_path="C:/frames/default",
    )

    window.run_default_test_button.clicked.emit()

    assert calls == [("C:/frames/default", "image_sequence")]
    assert window.state_label.text() == "REPLAY_DONE"
    assert "report.md" in window.cctv_status_label.text()


def test_puzzle_console_shows_fixed_roi_values(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.detect_roi_label.objectName() == "puzzleDetectRoiLabel"
    assert window.board_roi_label.objectName() == "puzzleBoardRoiLabel"
    assert "0.320,0.265,0.358,0.463" in window.detect_roi_label.text()
    assert "0.318,0.188,0.362,0.587" in window.board_roi_label.text()


def test_puzzle_console_applies_trace_events_to_analysis_metrics(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    window.apply_trace_event(
        {
            "type": "SESSION_START",
            "session_id": "20260626_213000_001",
            "frame_index": None,
            "payload": {},
        }
    )
    window.apply_trace_event(
        {
            "type": "CANDIDATES",
            "session_id": "20260626_213000_001",
            "frame_index": 7,
            "payload": {"count": 12},
        }
    )
    window.apply_trace_event(
        {
            "type": "IDENTITY_STATE",
            "session_id": "20260626_213000_001",
            "frame_index": 7,
            "payload": {
                "state": "IDENTITY_HOLD",
                "confidence": 0.251,
                "hold_frames": 3,
                "reason": "hold_ambiguous_candidate",
            },
        }
    )

    assert window.session_label.text() == "session: 20260626_213000_001"
    assert window.state_label.text() == "IDENTITY_HOLD"
    assert window.metric_labels["후보"].text() == "12"
    assert window.metric_labels["상태"].text() == "IDENTITY_HOLD"
    assert window.metric_labels["confidence"].text() == "0.25"
    assert window.metric_labels["hold"].text() == "3"
    assert window.metric_labels["reason"].text() == "hold_ambiguous_candidate"
    assert window.timeline_status.text() == "frame 7"


def test_puzzle_console_loads_trace_summary_after_replay(monkeypatch, tmp_path):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    report_path = session_dir / "report.md"
    trace_path = session_dir / "trace.jsonl"
    report_path.write_text("# report\n", encoding="utf-8")
    trace_events = [
        {"type": "SESSION_START", "session_id": "20260626_214000_001", "frame_index": None, "payload": {}},
        {"type": "CANDIDATES", "session_id": "20260626_214000_001", "frame_index": 2, "payload": {"count": 9}},
        {
            "type": "IDENTITY_STATE",
            "session_id": "20260626_214000_001",
            "frame_index": 2,
            "payload": {
                "state": "TRACK_CONFIDENT",
                "confidence": 0.873,
                "hold_frames": 0,
                "reason": "candidate_continuity",
            },
        },
        {"type": "SESSION_END", "session_id": "20260626_214000_001", "frame_index": None, "payload": {"frames": 3}},
    ]
    trace_path.write_text(
        "".join(f"{json.dumps(event, ensure_ascii=False)}\n" for event in trace_events),
        encoding="utf-8",
    )

    def pick_path(kind):
        assert kind == "image_sequence"
        return "C:/frames"

    def run_replay(path, kind):
        assert (path, kind) == ("C:/frames", "image_sequence")
        return report_path

    window = module.PuzzleConsoleWindow(replay_runner=run_replay, path_picker=pick_path)

    window.open_image_sequence_button.clicked.emit()

    assert window.session_label.text() == "session: 20260626_214000_001"
    assert window.state_label.text() == "TRACK_CONFIDENT"
    assert window.metric_labels["후보"].text() == "9"
    assert window.metric_labels["confidence"].text() == "0.87"
    assert window.metric_labels["hold"].text() == "0"
    assert window.metric_labels["reason"].text() == "candidate_continuity"
    assert "trace 반영: 4 events" in window.event_log.toPlainText()


def test_puzzle_console_opens_last_recording_folder_after_replay(monkeypatch, tmp_path):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    report_path = session_dir / "report.md"
    trace_path = session_dir / "trace.jsonl"
    report_path.write_text("# report\n", encoding="utf-8")
    trace_path.write_text("", encoding="utf-8")
    opened = []

    def pick_path(kind):
        assert kind == "image_sequence"
        return "C:/frames"

    def run_replay(path, kind):
        assert (path, kind) == ("C:/frames", "image_sequence")
        return report_path

    def open_folder(path):
        opened.append(path)

    window = module.PuzzleConsoleWindow(
        replay_runner=run_replay,
        path_picker=pick_path,
        folder_opener=open_folder,
    )

    window.open_image_sequence_button.clicked.emit()
    window.open_recording_folder_button.clicked.emit()

    assert opened == [session_dir]
    assert "session" in window.event_log.toPlainText()


def test_puzzle_console_recording_folder_button_waits_for_replay(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")
    opened = []

    window = module.PuzzleConsoleWindow(folder_opener=lambda path: opened.append(path))

    window.open_recording_folder_button.clicked.emit()

    assert opened == []
    assert "folder" in window.event_log.toPlainText().lower()


def test_puzzle_console_renders_recent_trace_timeline(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.timeline_detail.objectName() == "puzzleTimelineDetail"
    for frame_index in range(6):
        window.apply_trace_event(
            {
                "type": "CANDIDATES",
                "session_id": "20260626_214000_001",
                "frame_index": frame_index,
                "payload": {"count": frame_index + 1},
            }
        )
    window.apply_trace_event(
        {
            "type": "EVIDENCE",
            "session_id": "20260626_214000_001",
            "frame_index": 6,
            "payload": {"count": 2},
        }
    )
    window.apply_trace_event(
        {
            "type": "IDENTITY_STATE",
            "session_id": "20260626_214000_001",
            "frame_index": 6,
            "payload": {"state": "IDENTITY_HOLD", "confidence": 0.2, "hold_frames": 4, "reason": "merge"},
        }
    )

    detail = window.timeline_detail.text()
    assert "f0 CANDIDATES" not in detail
    assert "f2 CANDIDATES" not in detail
    assert "f3 CANDIDATES 4" in detail
    assert "f6 EVIDENCE 2" in detail
    assert "f6 IDENTITY_HOLD" in detail


def test_puzzle_console_applies_frame_replayed_to_cctv_status(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    window.apply_trace_event(
        {
            "type": "FRAME_REPLAYED",
            "session_id": "20260626_215000_001",
            "frame_index": 12,
            "payload": {
                "source_kind": "image_sequence",
                "source_frame_path": "C:/frames/012.png",
            },
        }
    )

    assert window.timeline_status.text() == "frame 12"
    assert window.current_frame_sources[12] == "C:/frames/012.png"
    assert "frame 12" in window.cctv_status_label.text()
    assert "C:/frames/012.png" in window.cctv_status_label.text()


def test_puzzle_console_exposes_cctv_frame_preview(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.cctv_frame_label.objectName() == "puzzleCctvFramePreview"


def test_puzzle_console_loads_existing_frame_preview(monkeypatch, tmp_path):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")
    frame_path = tmp_path / "frame_012.png"
    frame_path.write_bytes(b"fake image")

    window = module.PuzzleConsoleWindow()

    window.apply_trace_event(
        {
            "type": "FRAME_REPLAYED",
            "session_id": "20260626_220000_001",
            "frame_index": 12,
            "payload": {
                "source_kind": "image_sequence",
                "source_frame_path": str(frame_path),
            },
        }
    )

    assert window.current_cctv_source_path == str(frame_path)
    assert window.cctv_frame_label.pixmap().path == str(frame_path)


def test_puzzle_console_exposes_cctv_candidate_summary(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.cctv_candidate_summary_label.objectName() == "puzzleCctvCandidateSummary"


def test_puzzle_console_applies_candidates_to_cctv_summary(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    window.apply_trace_event(
        {
            "type": "CANDIDATES",
            "session_id": "20260626_221000_001",
            "frame_index": 12,
            "payload": {
                "count": 2,
                "candidates": [
                    {
                        "candidate_id": "c12_a",
                        "bbox": [10.0, 20.0, 30.0, 40.0],
                        "center": [25.0, 40.0],
                    },
                    {
                        "candidate_id": "c12_b",
                        "bbox": [50.0, 60.0, 20.0, 20.0],
                        "center": [60.0, 70.0],
                    },
                ],
            },
        }
    )

    assert len(window.current_frame_candidates[12]) == 2
    assert window.current_frame_candidates[12][0]["candidate_id"] == "c12_a"
    assert "frame 12" in window.cctv_candidate_summary_label.text()
    assert "candidates 2" in window.cctv_candidate_summary_label.text()
    assert "bbox 10,20,30,40" in window.cctv_candidate_summary_label.text()


def test_puzzle_console_exposes_cctv_identity_summary(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.cctv_identity_summary_label.objectName() == "puzzleCctvIdentitySummary"


def test_puzzle_console_exposes_guarded_decal_summary(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.cctv_guarded_summary_label.objectName() == "puzzleCctvGuardedSummary"


def test_puzzle_console_applies_live_family_guarded_summary(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()
    window.apply_trace_event(
        {
            "type": "LIVE_FAMILY",
            "session_id": "20260627_010000_001",
            "frame_index": 12,
            "payload": {
                "debug": {
                    "guarded_decal_identity": {
                        "accepted": True,
                        "background_ratio": 0.0,
                        "background_frames": 2,
                        "max_step": 10.0,
                        "reason": "accepted",
                    }
                }
            },
        }
    )

    assert window.current_frame_guarded[12]["debug"]["guarded_decal_identity"]["accepted"] is True
    assert "guarded_decal_identity" in window.cctv_guarded_summary_label.text()
    assert "accepted" in window.cctv_guarded_summary_label.text()
    assert "bg 0.00" in window.cctv_guarded_summary_label.text()


def test_puzzle_console_applies_identity_to_cctv_summary(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    window.apply_trace_event(
        {
            "type": "IDENTITY_STATE",
            "session_id": "20260626_222000_001",
            "frame_index": 12,
            "payload": {
                "state": "TRACK_CONFIDENT",
                "confidence": 0.824,
                "candidate_id": "c12_a",
                "point": [25.0, 40.0],
                "hold_frames": 0,
                "reason": "candidate_continuity",
            },
        }
    )

    assert window.current_frame_identity[12]["state"] == "TRACK_CONFIDENT"
    assert window.current_frame_identity[12]["candidate_id"] == "c12_a"
    assert "frame 12" in window.cctv_identity_summary_label.text()
    assert "TRACK_CONFIDENT" in window.cctv_identity_summary_label.text()
    assert "conf 0.82" in window.cctv_identity_summary_label.text()
    assert "candidate c12_a" in window.cctv_identity_summary_label.text()
    assert "point 25,40" in window.cctv_identity_summary_label.text()


def test_puzzle_console_exposes_cctv_evidence_summary(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.cctv_evidence_summary_label.objectName() == "puzzleCctvEvidenceSummary"


def test_puzzle_console_applies_evidence_to_cctv_summary(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    window.apply_trace_event(
        {
            "type": "EVIDENCE",
            "session_id": "20260626_223000_001",
            "frame_index": 12,
            "payload": {
                "count": 2,
                "evidence": [
                    {
                        "candidate_id": "c12_a",
                        "bg_score": 0.123,
                        "motion_divergence": 0.345,
                        "merge_likelihood": 0.567,
                    },
                    {
                        "candidate_id": "c12_b",
                        "bg_score": 0.9,
                    },
                ],
            },
        }
    )

    assert len(window.current_frame_evidence[12]) == 2
    assert window.current_frame_evidence[12][0]["candidate_id"] == "c12_a"
    assert "frame 12" in window.cctv_evidence_summary_label.text()
    assert "evidence 2" in window.cctv_evidence_summary_label.text()
    assert "candidate c12_a" in window.cctv_evidence_summary_label.text()
    assert "bg 0.12" in window.cctv_evidence_summary_label.text()
    assert "motion 0.34" in window.cctv_evidence_summary_label.text()
    assert "merge 0.57" in window.cctv_evidence_summary_label.text()


def test_puzzle_console_selects_saved_timeline_frame(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()
    window.apply_trace_event(
        {
            "type": "FRAME_REPLAYED",
            "session_id": "20260626_224000_001",
            "frame_index": 5,
            "payload": {"source_kind": "image_sequence", "source_frame_path": "C:/frames/005.png"},
        }
    )
    window.apply_trace_event(
        {
            "type": "CANDIDATES",
            "session_id": "20260626_224000_001",
            "frame_index": 5,
            "payload": {
                "count": 1,
                "candidates": [{"candidate_id": "c5_a", "bbox": [1, 2, 3, 4]}],
            },
        }
    )
    window.apply_trace_event(
        {
            "type": "EVIDENCE",
            "session_id": "20260626_224000_001",
            "frame_index": 5,
            "payload": {
                "count": 1,
                "evidence": [{"candidate_id": "c5_a", "bg_score": 0.11, "motion_divergence": 0.22}],
            },
        }
    )
    window.apply_trace_event(
        {
            "type": "IDENTITY_STATE",
            "session_id": "20260626_224000_001",
            "frame_index": 5,
            "payload": {
                "state": "TRACK_CONFIDENT",
                "confidence": 0.91,
                "candidate_id": "c5_a",
                "point": [8, 9],
                "hold_frames": 0,
                "reason": "candidate_continuity",
            },
        }
    )
    window.apply_trace_event(
        {
            "type": "FRAME_REPLAYED",
            "session_id": "20260626_224000_001",
            "frame_index": 6,
            "payload": {"source_kind": "image_sequence", "source_frame_path": "C:/frames/006.png"},
        }
    )

    assert window.select_timeline_frame(5) is True

    assert window.selected_frame_index == 5
    assert window.timeline_status.text() == "frame 5"
    assert "C:/frames/005.png" in window.cctv_status_label.text()
    assert "bbox 1,2,3,4" in window.cctv_candidate_summary_label.text()
    assert "bg 0.11" in window.cctv_evidence_summary_label.text()
    assert "TRACK_CONFIDENT" in window.cctv_identity_summary_label.text()
    assert window.state_label.text() == "TRACK_CONFIDENT"
    assert window.metric_labels["confidence"].text() == "0.91"


def test_puzzle_console_select_missing_timeline_frame_keeps_current(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()
    window.apply_trace_event(
        {
            "type": "FRAME_REPLAYED",
            "session_id": "20260626_224000_001",
            "frame_index": 3,
            "payload": {"source_kind": "image_sequence", "source_frame_path": "C:/frames/003.png"},
        }
    )
    assert window.select_timeline_frame(3) is True

    assert window.select_timeline_frame(99) is False

    assert window.selected_frame_index == 3
    assert window.timeline_status.text() == "frame 3"
    assert "frame 99" not in window.cctv_status_label.text()


def test_puzzle_console_exposes_timeline_navigation_buttons(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.timeline_prev_button.objectName() == "timelinePrevFrameButton"
    assert window.timeline_next_button.objectName() == "timelineNextFrameButton"


def test_puzzle_console_next_timeline_frame_moves_across_saved_frames(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()
    for frame_index in (3, 5, 8):
        window.apply_trace_event(
            {
                "type": "FRAME_REPLAYED",
                "session_id": "20260626_225000_001",
                "frame_index": frame_index,
                "payload": {
                    "source_kind": "image_sequence",
                    "source_frame_path": f"C:/frames/{frame_index:03d}.png",
                },
            }
        )

    assert window.selected_frame_index is None

    window.timeline_next_button.clicked.emit()

    assert window.selected_frame_index == 3
    assert "C:/frames/003.png" in window.cctv_status_label.text()

    assert window.select_next_timeline_frame() is True

    assert window.selected_frame_index == 5
    assert "C:/frames/005.png" in window.cctv_status_label.text()

    assert window.select_next_timeline_frame() is True
    assert window.select_next_timeline_frame() is False

    assert window.selected_frame_index == 8
    assert "C:/frames/008.png" in window.cctv_status_label.text()


def test_puzzle_console_previous_timeline_frame_moves_across_saved_frames(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()
    for frame_index in (3, 5, 8):
        window.apply_trace_event(
            {
                "type": "FRAME_REPLAYED",
                "session_id": "20260626_225000_001",
                "frame_index": frame_index,
                "payload": {
                    "source_kind": "image_sequence",
                    "source_frame_path": f"C:/frames/{frame_index:03d}.png",
                },
            }
        )

    assert window.selected_frame_index is None

    window.timeline_prev_button.clicked.emit()

    assert window.selected_frame_index == 8
    assert "C:/frames/008.png" in window.cctv_status_label.text()

    assert window.select_previous_timeline_frame() is True

    assert window.selected_frame_index == 5
    assert "C:/frames/005.png" in window.cctv_status_label.text()

    assert window.select_previous_timeline_frame() is True
    assert window.select_previous_timeline_frame() is False

    assert window.selected_frame_index == 3
    assert "C:/frames/003.png" in window.cctv_status_label.text()


def test_puzzle_console_exposes_timeline_frames_summary(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.timeline_frames_label.objectName() == "puzzleTimelineFrames"
    assert window.timeline_frames_label.text() == "frames 0"


def test_puzzle_console_updates_timeline_frames_summary_from_saved_states(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()
    window.apply_trace_event(
        {
            "type": "FRAME_REPLAYED",
            "session_id": "20260626_230000_001",
            "frame_index": 8,
            "payload": {"source_kind": "image_sequence", "source_frame_path": "C:/frames/008.png"},
        }
    )
    window.apply_trace_event(
        {
            "type": "CANDIDATES",
            "session_id": "20260626_230000_001",
            "frame_index": 3,
            "payload": {"count": 1, "candidates": [{"candidate_id": "c3_a"}]},
        }
    )
    window.apply_trace_event(
        {
            "type": "EVIDENCE",
            "session_id": "20260626_230000_001",
            "frame_index": 5,
            "payload": {"count": 1, "evidence": [{"candidate_id": "c5_a"}]},
        }
    )

    assert window.timeline_frames_label.text() == "frames 3: 3,5,8"


def test_puzzle_console_marks_selected_timeline_frame_in_summary(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()
    for frame_index in (3, 5, 8):
        window.apply_trace_event(
            {
                "type": "FRAME_REPLAYED",
                "session_id": "20260626_230000_001",
                "frame_index": frame_index,
                "payload": {
                    "source_kind": "image_sequence",
                    "source_frame_path": f"C:/frames/{frame_index:03d}.png",
                },
            }
        )

    assert window.select_timeline_frame(5) is True

    assert window.timeline_frames_label.text() == "frames 3: 3,5,8 | selected 5"
