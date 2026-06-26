# 투명도형 퍼즐 분석 콘솔의 주요 패널과 실행 진입점이 생성되는지 검증한다.
import importlib
import json
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

    def setPixmap(self, pixmap) -> None:
        self._pixmap = pixmap

    def pixmap(self):
        return getattr(self, "_pixmap", None)

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


class _Pixmap:
    def __init__(self, path: str = "") -> None:
        self.path = path

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
    qtwidgets.QSplitter = _Splitter
    qtwidgets.QTextEdit = _Widget
    qtwidgets.QVBoxLayout = _Layout
    qtwidgets.QWidget = _Widget

    class _Orientation:
        Horizontal = "horizontal"
        Vertical = "vertical"

    class _AlignmentFlag:
        AlignCenter = "center"

    qtcore = types.ModuleType("PyQt6.QtCore")
    qtcore.Qt = types.SimpleNamespace(Orientation=_Orientation, AlignmentFlag=_AlignmentFlag)

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
    assert window.input_panel.objectName() == "puzzleInputPanel"
    assert window.analysis_panel.objectName() == "puzzleAnalysisPanel"
    assert window.timeline_panel.objectName() == "puzzleTimelinePanel"
    assert window.event_log.objectName() == "puzzleEventLog"
    assert "투명도형" in window.windowTitle()


def test_puzzle_console_window_exposes_expected_commands(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.open_image_sequence_button.objectName() == "openImageSequenceButton"
    assert window.open_video_button.objectName() == "openVideoButton"
    assert window.open_replay_button.objectName() == "openReplayButton"
    assert window.start_watch_button.objectName() == "startWatchButton"
    assert window.roi_settings_button.objectName() == "roiSettingsButton"
    assert window.open_recording_folder_button.objectName() == "openRecordingFolderButton"


def test_puzzle_entrypoint_builds_parser_and_window(monkeypatch):
    _install_fake_qt(monkeypatch)
    puzzle = importlib.import_module("puzzle")

    parser = puzzle.build_arg_parser()
    args = parser.parse_args([])
    window = puzzle.create_window(args)

    assert args.headless is False
    assert window.objectName() == "puzzleConsoleWindow"


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


def test_puzzle_console_shows_fixed_roi_values(monkeypatch):
    _install_fake_qt(monkeypatch)
    module = importlib.import_module("ui.puzzle_console")

    window = module.PuzzleConsoleWindow()

    assert window.detect_roi_label.objectName() == "puzzleDetectRoiLabel"
    assert window.board_roi_label.objectName() == "puzzleBoardRoiLabel"
    assert "0.440,0.217,0.116,0.095" in window.detect_roi_label.text()
    assert "0.286,0.183,0.428,0.575" in window.board_roi_label.text()


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
