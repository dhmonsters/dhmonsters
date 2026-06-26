# 투명도형 퍼즐 분석 콘솔의 주요 패널과 실행 진입점이 생성되는지 검증한다.
import importlib
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

    pyqt = types.ModuleType("PyQt6")
    pyqt.QtWidgets = qtwidgets
    pyqt.QtCore = qtcore
    monkeypatch.setitem(sys.modules, "PyQt6", pyqt)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
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
