# 투명도형 퍼즐 세션, ROI, 후보, 판단 결과의 공통 데이터 모델.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


RoiBasis = Literal["monitor", "window_client", "board_frame"]
IdentityState = Literal[
    "INIT_VISIBLE",
    "TRACK_CONFIDENT",
    "OCCLUSION_SUSPECTED",
    "IDENTITY_HOLD",
    "REACQUIRE",
    "LOST",
]


@dataclass(frozen=True)
class RoiSpec:
    name: str
    basis: RoiBasis
    x: int
    y: int
    w: int
    h: int
    x_ratio: float | None = None
    y_ratio: float | None = None
    w_ratio: float | None = None
    h_ratio: float | None = None
    dpi_scale: float = 1.0
    window_title: str = ""

    def __post_init__(self) -> None:
        if self.w <= 0 or self.h <= 0:
            raise ValueError("RoiSpec width and height must be positive")


@dataclass(frozen=True)
class PuzzleSession:
    session_id: str
    started_at: str
    source_kind: str
    detect_roi: RoiSpec
    board_roi: RoiSpec
    output_dir: Path
    trace_path: Path
    raw_video_path: Path
    board_video_path: Path
    overlay_video_path: Path


@dataclass(frozen=True)
class FramePacket:
    session_id: str
    frame_index: int
    timestamp_ms: int
    source_frame: Any
    board_frame: Any
    source_kind: str
    roi_snapshot: dict[str, object]
    source_path: str | None = None


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    frame_index: int
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    score: float
    source: str
    class_name: str = ""


@dataclass(frozen=True)
class CandidateEvidence:
    candidate_id: str
    bg_score: float = 0.0
    motion_divergence: float = 0.0
    rigid_violation: float = 0.0
    phase_similarity: float = 0.0
    texture_bg_score: float = 0.0
    color_residual: float = 0.0
    merge_likelihood: float = 0.0
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class IdentityDecision:
    state: IdentityState
    point: tuple[float, float] | None
    candidate_id: str | None
    confidence: float
    reason: str
    hold_frames: int
    debug: dict[str, object]
