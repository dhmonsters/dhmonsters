# 투명도형 퍼즐 분석 콘솔의 PyQt6 화면 골격을 구성한다.
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.puzzle.defaults import fixed_board_roi_text, fixed_detect_roi_text
from core_ui.theme import SPACING, build_qss


ReplayRunner = Callable[[str, str], str | Path]
PathPicker = Callable[[str], str | Path | None]
TRACE_TIMELINE_LIMIT = 5


class PuzzleConsoleWindow(QMainWindow):
    def __init__(
        self,
        *,
        replay_runner: ReplayRunner | None = None,
        path_picker: PathPicker | None = None,
    ) -> None:
        super().__init__()
        self._replay_runner = replay_runner
        self._path_picker = path_picker or self._pick_path
        self.trace_timeline: list[str] = []
        self.current_frame_sources: dict[int, str] = {}
        self.current_frame_candidates: dict[int, list[dict[object, object]]] = {}
        self.current_cctv_source_path: str | None = None
        self.setObjectName("puzzleConsoleWindow")
        self.setWindowTitle("투명도형 퍼즐 분석 콘솔")
        self.resize(1280, 820)
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(build_qss())

        root = QWidget()
        root.setObjectName("puzzleConsoleRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_header(), 0)
        root_layout.addWidget(self._build_main_area(), 1)
        root_layout.addWidget(self._build_timeline_panel(), 0)
        root_layout.addWidget(self._build_event_log(), 0)
        self.setCentralWidget(root)

    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("topnav")
        header.setFixedHeight(56)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(SPACING["md"], SPACING["xs"], SPACING["md"], SPACING["xs"])
        layout.setSpacing(SPACING["sm"])

        title = QLabel("투명도형 퍼즐")
        title.setObjectName("logo")
        self.session_label = QLabel("session: idle")
        self.session_label.setObjectName("puzzleSessionLabel")
        self.state_label = QLabel("WAITING")
        self.state_label.setObjectName("statusChip")

        layout.addWidget(title)
        layout.addSpacing(SPACING["sm"])
        layout.addWidget(self.session_label)
        layout.addStretch(1)
        layout.addWidget(self.state_label)
        return header

    def _build_main_area(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("puzzleMainSplitter")
        self.input_panel = self._build_input_panel()
        self.cctv_view = self._build_cctv_view()
        self.analysis_panel = self._build_analysis_panel()
        splitter.addWidget(self.input_panel)
        splitter.addWidget(self.cctv_view)
        splitter.addWidget(self.analysis_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        return splitter

    def _build_input_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("puzzleInputPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"])
        layout.setSpacing(SPACING["xs"])

        title = QLabel("입력")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        self.open_image_sequence_button = _command_button("이미지 시퀀스", "openImageSequenceButton")
        self.open_video_button = _command_button("영상", "openVideoButton")
        self.open_replay_button = _command_button("JSONL replay", "openReplayButton")
        self.start_watch_button = _command_button("화면 감시", "startWatchButton", primary=True)
        self.roi_settings_button = _command_button("ROI 설정", "roiSettingsButton")
        self.open_recording_folder_button = _command_button("녹화 폴더", "openRecordingFolderButton")

        self.open_image_sequence_button.clicked.connect(
            lambda _checked=False: self.run_replay_input("image_sequence")
        )
        self.open_video_button.clicked.connect(lambda _checked=False: self.run_replay_input("video"))
        self.open_replay_button.clicked.connect(lambda _checked=False: self.run_replay_input("jsonl_replay"))
        self.start_watch_button.clicked.connect(lambda _checked=False: self.append_log("화면 감시는 다음 단계에서 연결"))
        self.roi_settings_button.clicked.connect(lambda _checked=False: self.append_log("고정 ROI 사용 중"))
        self.open_recording_folder_button.clicked.connect(
            lambda _checked=False: self.append_log("녹화 폴더 열기는 다음 단계에서 연결")
        )

        for button in (
            self.open_image_sequence_button,
            self.open_video_button,
            self.open_replay_button,
            self.start_watch_button,
            self.roi_settings_button,
            self.open_recording_folder_button,
        ):
            layout.addWidget(button)

        layout.addStretch(1)
        return panel

    def _build_cctv_view(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("puzzleCctvView")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"])
        layout.setSpacing(SPACING["xs"])

        title = QLabel("CCTV")
        title.setObjectName("cardTitle")
        self.cctv_frame_label = QLabel("preview 없음")
        self.cctv_frame_label.setObjectName("puzzleCctvFramePreview")
        self.cctv_frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cctv_frame_label.setMinimumHeight(360)
        self.cctv_status_label = QLabel("입력 대기")
        self.cctv_status_label.setObjectName("puzzleCctvStatus")
        self.cctv_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cctv_candidate_summary_label = QLabel("candidates 0")
        self.cctv_candidate_summary_label.setObjectName("puzzleCctvCandidateSummary")
        self.cctv_candidate_summary_label.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(self.cctv_frame_label, 1)
        layout.addWidget(self.cctv_status_label, 0)
        layout.addWidget(self.cctv_candidate_summary_label, 0)
        return frame

    def _build_analysis_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("puzzleAnalysisPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(SPACING["md"], SPACING["md"], SPACING["md"], SPACING["md"])
        layout.setSpacing(SPACING["xs"])

        title = QLabel("분석")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(SPACING["xs"])
        rows = [
            ("상태", "WAITING"),
            ("후보", "0"),
            ("confidence", "0.00"),
            ("hold", "0"),
            ("reason", "-"),
        ]
        self.metric_labels: dict[str, QLabel] = {}
        for row, (name, value) in enumerate(rows):
            label = QLabel(name)
            label.setObjectName("subtle")
            metric = QLabel(value)
            metric.setObjectName(f"puzzleMetric{name}")
            self.metric_labels[name] = metric
            grid.addWidget(label, row, 0)
            grid.addWidget(metric, row, 1)
        layout.addLayout(grid)

        roi_title = QLabel("ROI")
        roi_title.setObjectName("cardTitle")
        self.detect_roi_label = QLabel(fixed_detect_roi_text())
        self.detect_roi_label.setObjectName("puzzleDetectRoiLabel")
        self.board_roi_label = QLabel(fixed_board_roi_text())
        self.board_roi_label.setObjectName("puzzleBoardRoiLabel")
        self.detect_roi_label.setWordWrap(True)
        self.board_roi_label.setWordWrap(True)
        layout.addWidget(roi_title)
        layout.addWidget(self.detect_roi_label)
        layout.addWidget(self.board_roi_label)
        layout.addStretch(1)
        return panel

    def _build_timeline_panel(self) -> QFrame:
        self.timeline_panel = QFrame()
        self.timeline_panel.setObjectName("puzzleTimelinePanel")
        layout = QHBoxLayout(self.timeline_panel)
        layout.setContentsMargins(SPACING["md"], SPACING["xs"], SPACING["md"], SPACING["xs"])
        layout.setSpacing(SPACING["xs"])
        title = QLabel("타임라인")
        title.setObjectName("cardTitle")
        self.timeline_status = QLabel("frame 0")
        self.timeline_status.setObjectName("puzzleTimelineStatus")
        self.timeline_detail = QLabel("-")
        self.timeline_detail.setObjectName("puzzleTimelineDetail")
        self.timeline_detail.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(self.timeline_status)
        layout.addWidget(self.timeline_detail, 1)
        layout.addStretch(1)
        return self.timeline_panel

    def _build_event_log(self) -> QTextEdit:
        self.event_log = QTextEdit()
        self.event_log.setObjectName("puzzleEventLog")
        self.event_log.setReadOnly(True)
        self.event_log.setMinimumHeight(120)
        self.event_log.append("[system] puzzle console ready")
        return self.event_log

    def set_session_id(self, session_id: str | None) -> None:
        self.session_label.setText(f"session: {session_id or 'idle'}")

    def set_identity_state(self, state: str) -> None:
        self.state_label.setText(state)
        for key in ("상태", "state"):
            if key in self.metric_labels:
                self.metric_labels[key].setText(state)

    def apply_trace_event(self, event: dict[str, object]) -> None:
        event_type = str(event.get("type") or "")
        frame_index = event.get("frame_index")
        session_id = event.get("session_id")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        if isinstance(session_id, str) and session_id:
            self.set_session_id(session_id)
        if isinstance(frame_index, int):
            self.timeline_status.setText(f"frame {frame_index}")
        self._append_trace_timeline(event_type, frame_index, payload)

        if event_type == "FRAME_REPLAYED":
            self._apply_frame_replayed(frame_index, payload)
            return

        if event_type == "CANDIDATES":
            self._set_metric("후보", str(_candidate_count(payload)))
            self._apply_candidates(frame_index, payload)
            return

        if event_type == "EVIDENCE":
            return

        if event_type == "IDENTITY_STATE":
            state = str(payload.get("state") or "")
            if state:
                self.set_identity_state(state)
            confidence = payload.get("confidence")
            if isinstance(confidence, (int, float)):
                self._set_metric("confidence", f"{float(confidence):.2f}")
            hold_frames = payload.get("hold_frames")
            if isinstance(hold_frames, int):
                self._set_metric("hold", str(hold_frames))
            reason = str(payload.get("reason") or "-")
            self._set_metric("reason", reason)

    def load_trace_summary(self, trace_path: str | Path) -> int:
        path = Path(trace_path)
        if not path.exists():
            self.append_log(f"trace 없음: {path}")
            return 0

        applied = 0
        with path.open("r", encoding="utf-8") as fp:
            for line in fp:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    self.append_log(f"trace 줄 무시: {exc}")
                    continue
                if not isinstance(event, dict):
                    continue
                self.apply_trace_event(event)
                applied += 1
        self.append_log(f"trace 반영: {applied} events")
        return applied

    def _append_trace_timeline(
        self,
        event_type: str,
        frame_index: object,
        payload: dict[object, object],
    ) -> None:
        item = _timeline_item(event_type, frame_index, payload)
        if item is None:
            return
        self.trace_timeline.append(item)
        self.trace_timeline = self.trace_timeline[-TRACE_TIMELINE_LIMIT:]
        self.timeline_detail.setText(" | ".join(self.trace_timeline))

    def _apply_frame_replayed(self, frame_index: object, payload: dict[object, object]) -> None:
        if not isinstance(frame_index, int):
            return
        source = str(payload.get("source_frame_path") or payload.get("source_kind") or "-")
        self.current_frame_sources[frame_index] = source
        self.cctv_status_label.setText(f"frame {frame_index}: {source}")
        self._load_cctv_frame_preview(source)

    def _load_cctv_frame_preview(self, source: str) -> None:
        path = Path(source)
        if not path.is_file():
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return
        self.current_cctv_source_path = str(path)
        self.cctv_frame_label.setPixmap(pixmap)
        self.cctv_frame_label.setText(path.name)

    def _apply_candidates(self, frame_index: object, payload: dict[object, object]) -> None:
        if not isinstance(frame_index, int):
            return
        candidates = _candidate_list(payload)
        self.current_frame_candidates[frame_index] = candidates
        self.cctv_candidate_summary_label.setText(_candidate_summary(frame_index, payload))

    def _set_metric(self, name: str, value: str) -> None:
        label = self.metric_labels.get(name)
        if label is not None:
            label.setText(value)

    def append_log(self, message: str) -> None:
        self.event_log.append(f"[ui] {message}")

    def run_replay_input(self, input_kind: str) -> None:
        selected = self._path_picker(input_kind)
        if not selected:
            self.append_log(f"{input_kind} 선택 취소")
            return
        path = str(selected)
        self.set_identity_state("REPLAYING")
        self.cctv_status_label.setText(f"replay: {path}")
        self.append_log(f"{input_kind} replay 시작: {path}")
        if self._replay_runner is None:
            self.append_log("replay runner 미연결")
            return
        try:
            report_path = self._replay_runner(path, input_kind)
        except Exception as exc:
            self.set_identity_state("REPLAY_FAILED")
            self.cctv_status_label.setText(f"replay failed: {exc}")
            self.append_log(f"replay 실패: {exc}")
            return
        self.set_identity_state("REPLAY_DONE")
        self.cctv_status_label.setText(f"report: {report_path}")
        self.append_log(f"replay 완료: {report_path}")
        self.load_trace_summary(Path(report_path).parent / "trace.jsonl")

    def _pick_path(self, input_kind: str) -> str | None:
        from PyQt6.QtWidgets import QFileDialog

        if input_kind == "image_sequence":
            path = QFileDialog.getExistingDirectory(self, "이미지 시퀀스 폴더 선택")
            return path or None
        if input_kind == "video":
            path, _selected_filter = QFileDialog.getOpenFileName(
                self,
                "영상 파일 선택",
                "",
                "Videos (*.mp4 *.avi *.mov *.mkv)",
            )
            return path or None
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "JSONL replay 선택",
            "",
            "JSONL (*.jsonl)",
        )
        return path or None


def _command_button(text: str, object_name: str, *, primary: bool = False) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("primary" if primary else object_name)
    if primary:
        button.setObjectName(object_name)
        button.setStyleSheet("font-weight: 700;")
    return button


def _candidate_count(payload: dict[object, object]) -> int:
    count = payload.get("count")
    if isinstance(count, int):
        return count
    candidates = payload.get("candidates")
    if isinstance(candidates, list):
        return len(candidates)
    return 0


def _candidate_list(payload: dict[object, object]) -> list[dict[object, object]]:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list):
        return []
    return [item for item in candidates if isinstance(item, dict)]


def _candidate_summary(frame_index: int, payload: dict[object, object]) -> str:
    count = _candidate_count(payload)
    candidates = _candidate_list(payload)
    if not candidates:
        return f"frame {frame_index} candidates {count}"
    bbox = candidates[0].get("bbox")
    if not isinstance(bbox, list):
        return f"frame {frame_index} candidates {count}"
    return f"frame {frame_index} candidates {count} | bbox {_compact_bbox(bbox)}"


def _compact_bbox(bbox: list[object]) -> str:
    values: list[str] = []
    for value in bbox[:4]:
        if isinstance(value, (int, float)):
            values.append(str(int(round(float(value)))))
        else:
            values.append(str(value))
    return ",".join(values)


def _evidence_count(payload: dict[object, object]) -> int:
    count = payload.get("count")
    if isinstance(count, int):
        return count
    evidence = payload.get("evidence")
    if isinstance(evidence, list):
        return len(evidence)
    return 0


def _timeline_item(
    event_type: str,
    frame_index: object,
    payload: dict[object, object],
) -> str | None:
    if not isinstance(frame_index, int):
        return None
    prefix = f"f{frame_index}"
    if event_type == "CANDIDATES":
        return f"{prefix} CANDIDATES {_candidate_count(payload)}"
    if event_type == "EVIDENCE":
        return f"{prefix} EVIDENCE {_evidence_count(payload)}"
    if event_type == "IDENTITY_STATE":
        state = str(payload.get("state") or "IDENTITY_STATE")
        return f"{prefix} {state}"
    return None
