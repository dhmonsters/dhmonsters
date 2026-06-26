# 투명도형 퍼즐 후보 어댑터가 raw/live 검출 행을 Candidate로 바꾸는 동작을 검증한다.
import numpy as np

from core.puzzle.candidates import CandidateProvider, candidate_from_row
from core.puzzle.models import FramePacket


def _packet(frame_index: int = 7) -> FramePacket:
    frame = np.zeros((20, 30, 3), dtype=np.uint8)
    return FramePacket(
        session_id="20260626_180000_001",
        frame_index=frame_index,
        timestamp_ms=frame_index * 33,
        source_frame=frame,
        board_frame=frame.copy(),
        source_kind="test",
        roi_snapshot={"board": {"x": 0, "y": 0, "w": 30, "h": 20}},
    )


def test_candidate_from_row_preserves_board_frame_coordinates():
    candidate = candidate_from_row(
        (40.0, 50.0, 0.82, 20.0, 10.0),
        frame_index=7,
        source="raw",
        row_index=2,
        class_name="triangle",
    )

    assert candidate.candidate_id == "f7_raw_2"
    assert candidate.frame_index == 7
    assert candidate.center == (40.0, 50.0)
    assert candidate.bbox == (30.0, 45.0, 50.0, 55.0)
    assert candidate.score == 0.82
    assert candidate.source == "raw"
    assert candidate.class_name == "triangle"


def test_candidate_provider_limits_candidates_and_records_drop_reasons():
    rows = [
        (10.0, 11.0, 0.9, 4.0, 6.0),
        (12.0, 13.0, 0.2, 4.0, 6.0),
        (14.0, 15.0, 0.8, 4.0, 6.0),
    ]
    provider = CandidateProvider(
        row_provider=lambda packet: rows,
        source="live_family",
        min_score=0.5,
        max_candidates=1,
    )

    candidates = provider.detect(_packet(frame_index=9))

    assert [candidate.candidate_id for candidate in candidates] == ["f9_live_family_0"]
    assert candidates[0].bbox == (8.0, 8.0, 12.0, 14.0)
    assert provider.last_debug["input_count"] == 3
    assert provider.last_debug["kept_count"] == 1
    assert provider.last_debug["dropped"] == [
        {"row_index": 1, "reason": "below_min_score", "score": 0.2},
        {"row_index": 2, "reason": "max_candidates", "score": 0.8},
    ]


def test_candidate_provider_accepts_mapping_rows():
    provider = CandidateProvider(
        row_provider=lambda packet: [
            {"cx": 5, "cy": 6, "score": 0.75, "w": 4, "h": 2, "class_name": "hook"}
        ],
        source="replay",
    )

    candidates = provider.detect(_packet(frame_index=3))

    assert len(candidates) == 1
    assert candidates[0].candidate_id == "f3_replay_0"
    assert candidates[0].bbox == (3.0, 5.0, 7.0, 7.0)
    assert candidates[0].class_name == "hook"
