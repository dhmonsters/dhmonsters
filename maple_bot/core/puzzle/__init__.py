# 투명도형 퍼즐 분석 콘솔의 핵심 모델과 처리 모듈을 묶는 패키지.
from core.puzzle.candidates import CandidateProvider, candidate_from_row
from core.puzzle.capture_preflight import CaptureCheckResult, run_capture_check
from core.puzzle.defaults import (
    DEFAULT_BOARD_ROI_RATIOS,
    DEFAULT_DETECT_ROI_RATIOS,
    DEFAULT_POPUP_HEADER_ROI_RATIOS,
    fixed_board_roi,
    fixed_detect_roi,
    fixed_popup_header_roi,
    fixed_puzzle_rois,
)
from core.puzzle.evidence import EvidenceJudges
from core.puzzle.frame_source import (
    ImageSequenceFrameSource,
    JsonlReplayFrameSource,
    VideoFrameSource,
)
from core.puzzle.identity import IdentityTracker
from core.puzzle.live_recording import LiveRecordingRuntime
from core.puzzle.notify import PuzzleNotifier
from core.puzzle.report import ReportBuilder
from core.puzzle.detection import DetectionEvent, DetectionGate
from core.puzzle.models import (
    Candidate,
    CandidateEvidence,
    FramePacket,
    IdentityDecision,
    PuzzleSession,
    RoiSpec,
)
from core.puzzle.recorder import SessionRecorder
from core.puzzle.recording_controller import RecordingController
from core.puzzle.session import SessionManager
from core.puzzle.trace import TraceLogger

__all__ = [
    "Candidate",
    "CandidateEvidence",
    "CandidateProvider",
    "CaptureCheckResult",
    "DEFAULT_BOARD_ROI_RATIOS",
    "DEFAULT_DETECT_ROI_RATIOS",
    "DEFAULT_POPUP_HEADER_ROI_RATIOS",
    "DetectionEvent",
    "DetectionGate",
    "EvidenceJudges",
    "FramePacket",
    "ImageSequenceFrameSource",
    "IdentityDecision",
    "IdentityTracker",
    "JsonlReplayFrameSource",
    "LiveRecordingRuntime",
    "PuzzleSession",
    "PuzzleNotifier",
    "ReportBuilder",
    "RecordingController",
    "RoiSpec",
    "SessionRecorder",
    "SessionManager",
    "TraceLogger",
    "VideoFrameSource",
    "candidate_from_row",
    "fixed_board_roi",
    "fixed_detect_roi",
    "fixed_popup_header_roi",
    "fixed_puzzle_rois",
    "run_capture_check",
]
