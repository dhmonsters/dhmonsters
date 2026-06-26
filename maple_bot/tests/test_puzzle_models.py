# 투명도형 퍼즐 데이터 모델의 기본 계약을 검증한다.
from pathlib import Path

import numpy as np

from core.puzzle.models import (
    Candidate,
    CandidateEvidence,
    FramePacket,
    IdentityDecision,
    PuzzleSession,
    RoiSpec,
)


def test_candidate_preserves_board_frame_coordinates():
    candidate = Candidate(
        candidate_id="f12_raw_0",
        frame_index=12,
        bbox=(10.5, 20.0, 70.5, 90.0),
        center=(40.5, 55.0),
        score=0.82,
        source="raw",
        class_name="triangle",
    )

    assert candidate.bbox == (10.5, 20.0, 70.5, 90.0)
    assert candidate.center == (40.5, 55.0)
    assert candidate.source == "raw"


def test_model_objects_keep_session_metadata_and_defaults(tmp_path):
    detect_roi = RoiSpec("detect", "window_client", 100, 50, 300, 120)
    board_roi = RoiSpec("board", "window_client", 550, 200, 820, 620)
    session = PuzzleSession(
        session_id="20260626_163000_001",
        started_at="2026-06-26T16:30:00",
        source_kind="image_sequence",
        detect_roi=detect_roi,
        board_roi=board_roi,
        output_dir=tmp_path,
        trace_path=tmp_path / "trace.jsonl",
        raw_video_path=tmp_path / "raw_cctv.mp4",
        board_video_path=tmp_path / "board_crop.mp4",
        overlay_video_path=tmp_path / "overlay.mp4",
    )

    source = np.zeros((1080, 1920, 3), dtype=np.uint8)
    board = np.zeros((620, 820, 3), dtype=np.uint8)
    packet = FramePacket(
        session_id=session.session_id,
        frame_index=3,
        timestamp_ms=99,
        source_frame=source,
        board_frame=board,
        source_kind=session.source_kind,
        roi_snapshot={"basis": board_roi.basis},
    )
    evidence = CandidateEvidence(candidate_id="f3_yolo_0")
    decision = IdentityDecision(
        state="TRACK_CONFIDENT",
        point=(120.0, 130.0),
        candidate_id="f3_yolo_0",
        confidence=0.7,
        reason="primary_healthy",
        hold_frames=0,
        debug={"source": "test"},
    )

    assert session.trace_path == Path(tmp_path / "trace.jsonl")
    assert packet.board_frame.shape == (620, 820, 3)
    assert evidence.bg_score == 0.0
    assert evidence.notes == ()
    assert decision.state == "TRACK_CONFIDENT"

