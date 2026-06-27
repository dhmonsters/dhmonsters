# 투명도형 퍼즐 분석 콘솔의 PyQt6 화면 골격을 구성한다.
from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
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
FolderOpener = Callable[[Path], None]
RecordingStopHandler = Callable[[], bool]
WatchStartHandler = Callable[[], object]
SolverStopHandler = Callable[[], bool]
LiveStatusHandler = Callable[[], object]
CaptureCheckHandler = Callable[[], str | Path | None]
TRACE_TIMELINE_LIMIT = 5


class PuzzleConsoleWindow(QMainWindow):
    def __init__(
        self,
        *,
        replay_runner: ReplayRunner | None = None,
        path_picker: PathPicker | None = None,
        folder_opener: FolderOpener | None = None,
        recording_stop_handler: RecordingStopHandler | None = None,
        watch_start_handler: WatchStartHandler | None = None,
        solver_stop_handler: SolverStopHandler | None = None,
        live_status_handler: LiveStatusHandler | None = None,
        capture_check_handler: CaptureCheckHandler | None = None,
        default_test_path: str | Path | None = None,
    ) -> None:
        super().__init__()
        self._replay_runner = replay_runner
        self._path_picker = path_picker or self._pick_path
        self._folder_opener = folder_opener or _open_folder
        self._recording_stop_handler = recording_stop_handler
        self._watch_start_handler = watch_start_handler
        self._solver_stop_handler = solver_stop_handler
        self._live_status_handler = live_status_handler
        self._capture_check_handler = capture_check_handler
        self._default_test_path = str(default_test_path) if default_test_path is not None else ""
        self.last_report_path: Path | None = None
        self.last_session_dir: Path | None = None
        self.trace_timeline: list[str] = []
        self.current_frame_sources: dict[int, str] = {}
        self.current_frame_candidates: dict[int, list[dict[object, object]]] = {}
        self.current_frame_evidence: dict[int, list[dict[object, object]]] = {}
        self.current_frame_identity: dict[int, dict[object, object]] = {}
        self.current_frame_guarded: dict[int, dict[object, object]] = {}
        self.current_cctv_source_path: str | None = None
        self.selected_frame_index: int | None = None
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
        self._live_status_timer: QTimer | None = None
        if self._live_status_handler is not None:
            self._live_status_timer = QTimer(self)
            self._live_status_timer.setInterval(500)
            self._live_status_timer.timeout.connect(self._poll_live_status)
            self._live_status_timer.start()

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
        self.run_default_test_button = _command_button("기본 테스트", "runDefaultPuzzleTestButton")
        self.start_watch_button = _command_button("솔버 ON F1", "startWatchButton", primary=True)
        self.stop_solver_button = _command_button("솔버 정지 F2", "stopSolverButton")
        self.roi_settings_button = _command_button("ROI 설정", "roiSettingsButton")
        self.capture_check_button = _command_button("캡처 점검", "captureCheckButton")
        self.open_recording_folder_button = _command_button("녹화 폴더", "openRecordingFolderButton")
        self.stop_recording_button = _command_button("녹화 종료 F3", "stopRecordingButton")

        self.open_image_sequence_button.clicked.connect(
            lambda _checked=False: self.run_replay_input("image_sequence")
        )
        self.open_video_button.clicked.connect(lambda _checked=False: self.run_replay_input("video"))
        self.open_replay_button.clicked.connect(lambda _checked=False: self.run_replay_input("jsonl_replay"))
        self.run_default_test_button.clicked.connect(lambda _checked=False: self.run_default_test_input())
        self.start_watch_button.clicked.connect(lambda _checked=False: self.start_watch_input())
        self.stop_solver_button.clicked.connect(lambda _checked=False: self.stop_solver_input())
        self.roi_settings_button.clicked.connect(lambda _checked=False: self.append_log("고정 ROI 사용 중"))
        self.capture_check_button.clicked.connect(lambda _checked=False: self.capture_check_input())
        self.open_recording_folder_button.clicked.connect(lambda _checked=False: self.open_last_recording_folder())
        self.stop_recording_button.clicked.connect(lambda _checked=False: self.stop_recording_input())

        for button in (
            self.open_image_sequence_button,
            self.open_video_button,
            self.open_replay_button,
            self.run_default_test_button,
            self.start_watch_button,
            self.stop_solver_button,
            self.roi_settings_button,
            self.capture_check_button,
            self.open_recording_folder_button,
            self.stop_recording_button,
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
        self.cctv_evidence_summary_label = QLabel("evidence 0")
        self.cctv_evidence_summary_label.setObjectName("puzzleCctvEvidenceSummary")
        self.cctv_evidence_summary_label.setWordWrap(True)
        self.cctv_identity_summary_label = QLabel("identity -")
        self.cctv_identity_summary_label.setObjectName("puzzleCctvIdentitySummary")
        self.cctv_identity_summary_label.setWordWrap(True)
        self.cctv_guarded_summary_label = QLabel("guarded -")
        self.cctv_guarded_summary_label.setObjectName("puzzleCctvGuardedSummary")
        self.cctv_guarded_summary_label.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(self.cctv_frame_label, 1)
        layout.addWidget(self.cctv_status_label, 0)
        layout.addWidget(self.cctv_candidate_summary_label, 0)
        layout.addWidget(self.cctv_evidence_summary_label, 0)
        layout.addWidget(self.cctv_identity_summary_label, 0)
        layout.addWidget(self.cctv_guarded_summary_label, 0)
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
        self.timeline_frames_label = QLabel("frames 0")
        self.timeline_frames_label.setObjectName("puzzleTimelineFrames")
        self.timeline_frames_label.setWordWrap(True)
        self.timeline_detail = QLabel("-")
        self.timeline_detail.setObjectName("puzzleTimelineDetail")
        self.timeline_detail.setWordWrap(True)
        self.timeline_prev_button = _command_button("<", "timelinePrevFrameButton")
        self.timeline_next_button = _command_button(">", "timelineNextFrameButton")
        self.timeline_prev_button.clicked.connect(lambda _checked=False: self.select_previous_timeline_frame())
        self.timeline_next_button.clicked.connect(lambda _checked=False: self.select_next_timeline_frame())
        layout.addWidget(title)
        layout.addWidget(self.timeline_status)
        layout.addWidget(self.timeline_prev_button)
        layout.addWidget(self.timeline_next_button)
        layout.addWidget(self.timeline_frames_label)
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
            self._apply_evidence(frame_index, payload)
            return

        if event_type == "IDENTITY_STATE":
            self._apply_identity_metrics(payload)
            self._apply_identity(frame_index, payload)
            return

        if event_type in {"LIVE_FAMILY", "SELECTOR_SHADOW"}:
            self._apply_guarded(frame_index, payload)

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

    def select_timeline_frame(self, frame_index: int) -> bool:
        if not self._has_frame_state(frame_index):
            self.append_log(f"frame 없음: {frame_index}")
            return False

        self.selected_frame_index = frame_index
        self.timeline_status.setText(f"frame {frame_index}")

        source = self.current_frame_sources.get(frame_index)
        if source is not None:
            self.cctv_status_label.setText(f"frame {frame_index}: {source}")
            self._load_cctv_frame_preview(source)

        candidates = self.current_frame_candidates.get(frame_index)
        if candidates is not None:
            self._set_metric("후보", str(len(candidates)))
            self.cctv_candidate_summary_label.setText(
                _candidate_summary(frame_index, {"count": len(candidates), "candidates": candidates})
            )

        evidence = self.current_frame_evidence.get(frame_index)
        if evidence is not None:
            self.cctv_evidence_summary_label.setText(
                _evidence_summary(frame_index, {"count": len(evidence), "evidence": evidence})
            )

        identity = self.current_frame_identity.get(frame_index)
        if identity is not None:
            self.cctv_identity_summary_label.setText(_identity_summary(frame_index, identity))
            self._apply_identity_metrics(identity)

        guarded = self.current_frame_guarded.get(frame_index)
        if guarded is not None:
            self.cctv_guarded_summary_label.setText(_guarded_summary(frame_index, guarded))

        self._refresh_timeline_frames_summary()
        return True

    def select_next_timeline_frame(self) -> bool:
        return self._select_adjacent_timeline_frame(1)

    def select_previous_timeline_frame(self) -> bool:
        return self._select_adjacent_timeline_frame(-1)

    def _select_adjacent_timeline_frame(self, direction: int) -> bool:
        frames = self._available_timeline_frames()
        if not frames:
            self.append_log("frame 없음")
            return False

        if self.selected_frame_index is None:
            return self.select_timeline_frame(frames[0] if direction > 0 else frames[-1])

        if direction > 0:
            next_frames = [frame for frame in frames if frame > self.selected_frame_index]
            if not next_frames:
                return False
            return self.select_timeline_frame(next_frames[0])

        previous_frames = [frame for frame in frames if frame < self.selected_frame_index]
        if not previous_frames:
            return False
        return self.select_timeline_frame(previous_frames[-1])

    def _available_timeline_frames(self) -> list[int]:
        return sorted(
            set(self.current_frame_sources)
            | set(self.current_frame_candidates)
            | set(self.current_frame_evidence)
            | set(self.current_frame_identity)
            | set(self.current_frame_guarded)
        )

    def _refresh_timeline_frames_summary(self) -> None:
        self.timeline_frames_label.setText(
            _timeline_frames_summary(self._available_timeline_frames(), self.selected_frame_index)
        )

    def _has_frame_state(self, frame_index: int) -> bool:
        return (
            frame_index in self.current_frame_sources
            or frame_index in self.current_frame_candidates
            or frame_index in self.current_frame_evidence
            or frame_index in self.current_frame_identity
            or frame_index in self.current_frame_guarded
        )

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
        self._refresh_timeline_frames_summary()

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
        self._refresh_timeline_frames_summary()

    def _apply_evidence(self, frame_index: object, payload: dict[object, object]) -> None:
        if not isinstance(frame_index, int):
            return
        evidence = _evidence_list(payload)
        self.current_frame_evidence[frame_index] = evidence
        self.cctv_evidence_summary_label.setText(_evidence_summary(frame_index, payload))
        self._refresh_timeline_frames_summary()

    def _apply_identity(self, frame_index: object, payload: dict[object, object]) -> None:
        if not isinstance(frame_index, int):
            return
        self.current_frame_identity[frame_index] = dict(payload)
        self.cctv_identity_summary_label.setText(_identity_summary(frame_index, payload))
        self._refresh_timeline_frames_summary()

    def _apply_guarded(self, frame_index: object, payload: dict[object, object]) -> None:
        if not isinstance(frame_index, int):
            return
        self.current_frame_guarded[frame_index] = dict(payload)
        self.cctv_guarded_summary_label.setText(_guarded_summary(frame_index, payload))
        self._refresh_timeline_frames_summary()

    def _apply_identity_metrics(self, payload: dict[object, object]) -> None:
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
        self._run_replay_path(path, input_kind)

    def run_default_test_input(self) -> None:
        if not self._default_test_path:
            self.append_log("기본 테스트 경로 없음")
            return
        self._run_replay_path(self._default_test_path, "image_sequence")

    def open_last_recording_folder(self) -> bool:
        if self.last_session_dir is None:
            self.append_log("recording folder 없음")
            return False
        if not self.last_session_dir.exists():
            self.append_log(f"recording folder 없음: {self.last_session_dir}")
            return False
        self._folder_opener(self.last_session_dir)
        self.append_log(f"recording folder 열기: {self.last_session_dir}")
        return True

    def stop_recording_input(self) -> bool:
        if self._recording_stop_handler is None:
            self.append_log("recording stop 대기: active recording 없음")
            return False
        stopped = bool(self._recording_stop_handler())
        if stopped:
            self.append_log("recording stop")
        else:
            self.append_log("recording stop skipped")
        return stopped

    def start_watch_input(self) -> bool:
        if self._watch_start_handler is None:
            self.append_log("solver on 대기: live handler 없음")
            return False
        try:
            result = self._watch_start_handler()
        except Exception as exc:
            self.set_identity_state("SOLVER_FAILED")
            self.append_log(f"solver on 실패: {exc}")
            return False
        session_dir = _watch_result_session_dir(result)
        preview_path = _watch_result_preview_path(result)
        if session_dir is not None:
            self.last_session_dir = session_dir
            self.cctv_status_label.setText(f"recording: {self.last_session_dir}")
            self.set_identity_state("RECORDING")
            self.append_log(f"recording start: {self.last_session_dir}")
            if preview_path is not None:
                self._load_cctv_frame_preview(str(preview_path))
            return True
        self.set_identity_state("SOLVER_ON")
        self.cctv_status_label.setText("solver on: waiting puzzle")
        self.append_log("solver on: waiting puzzle")
        return True

    def stop_solver_input(self) -> bool:
        if self._solver_stop_handler is None:
            self.append_log("solver stop 대기: handler 없음")
            return False
        stopped = bool(self._solver_stop_handler())
        if stopped:
            self.set_identity_state("SOLVER_STOPPED")
            self.append_log("solver stop")
        else:
            self.append_log("solver stop skipped")
        return stopped

    def _poll_live_status(self) -> None:
        if self._live_status_handler is None:
            return
        try:
            result = self._live_status_handler()
        except Exception as exc:
            self.append_log(f"live status 실패: {exc}")
            return
        session_dir = _watch_result_session_dir(result)
        preview_path = _watch_result_preview_path(result)
        if session_dir is None:
            return
        is_new_recording = self.last_session_dir != session_dir or self.state_label.text() != "RECORDING"
        if is_new_recording:
            self.last_session_dir = session_dir
            self.cctv_status_label.setText(f"recording: {self.last_session_dir}")
            self.set_identity_state("RECORDING")
            self.append_log(f"recording start: {self.last_session_dir}")
        if preview_path is not None and str(preview_path) != self.current_cctv_source_path:
            self._load_cctv_frame_preview(str(preview_path))

    def capture_check_input(self) -> bool:
        if self._capture_check_handler is None:
            self.append_log("capture check 대기: handler 없음")
            return False
        try:
            report_path = self._capture_check_handler()
        except Exception as exc:
            self.set_identity_state("CAPTURE_FAILED")
            self.append_log(f"capture check 실패: {exc}")
            return False
        if report_path is not None:
            self.last_report_path = Path(report_path)
            self.cctv_status_label.setText(f"capture check: {self.last_report_path}")
        self.set_identity_state("CAPTURE_OK")
        self.append_log(f"capture check: {self.last_report_path or '-'}")
        return True

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_F1:
            self.start_watch_input()
            return
        if event.key() == Qt.Key.Key_F2:
            self.stop_solver_input()
            return
        if event.key() == Qt.Key.Key_F3:
            self.stop_recording_input()
            return
        super().keyPressEvent(event)

    def _run_replay_path(self, path: str, input_kind: str) -> None:
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
        self.last_report_path = Path(report_path)
        self.last_session_dir = self.last_report_path.parent
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


def _open_folder(path: Path) -> None:
    if hasattr(os, "startfile"):
        os.startfile(str(path))
        return
    if sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
        return
    subprocess.Popen(["xdg-open", str(path)])


def _watch_result_session_dir(result: object) -> Path | None:
    if result is None:
        return None
    if isinstance(result, Path):
        return result
    if isinstance(result, str):
        return Path(result)
    session_dir = getattr(result, "session_dir", None)
    if session_dir is None:
        return None
    return Path(session_dir)


def _watch_result_preview_path(result: object) -> Path | None:
    if result is None:
        return None
    preview_path = getattr(result, "preview_path", None)
    if preview_path is None:
        return None
    return Path(preview_path)


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


def _identity_summary(frame_index: int, payload: dict[object, object]) -> str:
    state = str(payload.get("state") or "-")
    parts = [f"frame {frame_index}", state]
    confidence = payload.get("confidence")
    if isinstance(confidence, (int, float)):
        parts.append(f"conf {float(confidence):.2f}")
    candidate_id = payload.get("candidate_id")
    if candidate_id:
        parts.append(f"candidate {candidate_id}")
    point = payload.get("point")
    if isinstance(point, list):
        parts.append(f"point {_compact_point(point)}")
    return " | ".join(parts)


def _compact_point(point: list[object]) -> str:
    values: list[str] = []
    for value in point[:2]:
        if isinstance(value, (int, float)):
            values.append(str(int(round(float(value)))))
        else:
            values.append(str(value))
    return ",".join(values)


def _evidence_list(payload: dict[object, object]) -> list[dict[object, object]]:
    evidence = payload.get("evidence")
    if not isinstance(evidence, list):
        return []
    return [item for item in evidence if isinstance(item, dict)]


def _evidence_summary(frame_index: int, payload: dict[object, object]) -> str:
    count = _evidence_count(payload)
    evidence = _evidence_list(payload)
    if not evidence:
        return f"frame {frame_index} evidence {count}"

    first = evidence[0]
    parts = [f"frame {frame_index}", f"evidence {count}"]
    candidate_id = first.get("candidate_id")
    if candidate_id:
        parts.append(f"candidate {candidate_id}")
    for key, label in (
        ("bg_score", "bg"),
        ("motion_divergence", "motion"),
        ("merge_likelihood", "merge"),
    ):
        value = first.get(key)
        if isinstance(value, (int, float)):
            parts.append(f"{label} {float(value):.2f}")
    return " | ".join(parts)


def _evidence_count(payload: dict[object, object]) -> int:
    count = payload.get("count")
    if isinstance(count, int):
        return count
    evidence = payload.get("evidence")
    if isinstance(evidence, list):
        return len(evidence)
    return 0


def _guarded_summary(frame_index: int, payload: dict[object, object]) -> str:
    debug = payload.get("debug")
    if isinstance(debug, dict):
        guarded = debug.get("guarded_decal_identity")
    else:
        guarded = payload.get("guarded_decal_identity")
    if not isinstance(guarded, dict):
        return f"frame {frame_index} guarded -"

    status = "accepted" if guarded.get("accepted") else str(guarded.get("reason") or "blocked")
    parts = [f"frame {frame_index}", "guarded_decal_identity", status]
    ratio = guarded.get("background_ratio")
    if isinstance(ratio, (int, float)):
        parts.append(f"bg {float(ratio):.2f}")
    frames = guarded.get("background_frames")
    if isinstance(frames, int):
        parts.append(f"bg_frames {frames}")
    max_step = guarded.get("max_step")
    if isinstance(max_step, (int, float)):
        parts.append(f"step {float(max_step):.1f}")
    return " | ".join(parts)


def _timeline_frames_summary(frames: list[int], selected_frame_index: int | None) -> str:
    if not frames:
        return "frames 0"

    if len(frames) <= 8:
        frame_text = ",".join(str(frame) for frame in frames)
    else:
        head = ",".join(str(frame) for frame in frames[:4])
        tail = ",".join(str(frame) for frame in frames[-2:])
        frame_text = f"{head},...,{tail}"

    summary = f"frames {len(frames)}: {frame_text}"
    if selected_frame_index in frames:
        summary = f"{summary} | selected {selected_frame_index}"
    return summary


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
    if event_type == "LIVE_FAMILY":
        debug = payload.get("debug")
        guarded = debug.get("guarded_decal_identity") if isinstance(debug, dict) else None
        if isinstance(guarded, dict):
            status = "accepted" if guarded.get("accepted") else str(guarded.get("reason") or "blocked")
            return f"{prefix} GUARDED {status}"
        return f"{prefix} LIVE_FAMILY"
    if event_type == "SELECTOR_SHADOW":
        family = str(payload.get("family") or "SELECTOR_SHADOW")
        return f"{prefix} {family}"
    return None
