# 투명도형 퍼즐 분석 콘솔의 핵심 모델과 처리 모듈을 묶는 패키지.
from core.puzzle.candidates import CandidateProvider, candidate_from_row
from core.puzzle.frame_source import (
    ImageSequenceFrameSource,
    JsonlReplayFrameSource,
    VideoFrameSource,
)
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
from core.puzzle.session import SessionManager
from core.puzzle.trace import TraceLogger

__all__ = [
    "Candidate",
    "CandidateEvidence",
    "CandidateProvider",
    "DetectionEvent",
    "DetectionGate",
    "FramePacket",
    "ImageSequenceFrameSource",
    "IdentityDecision",
    "JsonlReplayFrameSource",
    "PuzzleSession",
    "RoiSpec",
    "SessionRecorder",
    "SessionManager",
    "TraceLogger",
    "VideoFrameSource",
    "candidate_from_row",
]
