# 투명도형 퍼즐 후보 판단 근거 계산기가 baseline, 병합, 색상 보조 신호를 만든다는 점을 검증한다.
import numpy as np

from core.puzzle.evidence import EvidenceJudges
from core.puzzle.models import Candidate, FramePacket


def _candidate(
    candidate_id: str,
    center: tuple[float, float],
    size: tuple[float, float] = (10.0, 10.0),
) -> Candidate:
    width, height = size
    cx, cy = center
    return Candidate(
        candidate_id=candidate_id,
        frame_index=5,
        bbox=(cx - width / 2.0, cy - height / 2.0, cx + width / 2.0, cy + height / 2.0),
        center=center,
        score=0.8,
        source="raw",
    )


def _packet(board_frame: np.ndarray) -> FramePacket:
    return FramePacket(
        session_id="20260626_180000_001",
        frame_index=5,
        timestamp_ms=165,
        source_frame=board_frame,
        board_frame=board_frame,
        source_kind="test",
        roi_snapshot={"board": {"x": 0, "y": 0, "w": board_frame.shape[1], "h": board_frame.shape[0]}},
    )


def test_evidence_judges_return_zero_baseline_for_each_candidate():
    candidates = [_candidate("a", (10.0, 10.0)), _candidate("b", (40.0, 40.0))]
    packet = _packet(np.zeros((60, 80), dtype=np.uint8))

    evidence = EvidenceJudges().score(candidates, packet)

    assert set(evidence) == {"a", "b"}
    assert evidence["a"].candidate_id == "a"
    assert evidence["a"].bg_score == 0.0
    assert evidence["a"].motion_divergence == 0.0
    assert evidence["a"].rigid_violation == 0.0
    assert evidence["a"].phase_similarity == 0.0
    assert evidence["a"].texture_bg_score == 0.0
    assert evidence["a"].color_residual == 0.0
    assert evidence["a"].merge_likelihood == 0.0


def test_merge_likelihood_increases_for_large_close_candidates():
    close_large = _candidate("close_large", (30.0, 30.0), size=(20.0, 20.0))
    close_peer = _candidate("close_peer", (35.0, 35.0), size=(18.0, 18.0))
    far_small = _candidate("far_small", (90.0, 90.0), size=(6.0, 6.0))
    packet = _packet(np.zeros((120, 120), dtype=np.uint8))

    evidence = EvidenceJudges().score([close_large, close_peer, far_small], packet)

    assert evidence["close_large"].merge_likelihood > evidence["far_small"].merge_likelihood
    assert evidence["close_large"].merge_likelihood > 0.0
    assert evidence["far_small"].merge_likelihood == 0.0


def test_color_residual_uses_color_frames_but_ignores_grayscale_frames():
    color_frame = np.zeros((30, 30, 3), dtype=np.uint8)
    color_frame[5:15, 5:15, 0] = 255
    gray_frame = np.full((30, 30), 128, dtype=np.uint8)
    candidate = _candidate("color", (10.0, 10.0), size=(10.0, 10.0))

    color_evidence = EvidenceJudges().score([candidate], _packet(color_frame))
    gray_evidence = EvidenceJudges().score([candidate], _packet(gray_frame))

    assert color_evidence["color"].color_residual > 0.0
    assert gray_evidence["color"].color_residual == 0.0


def test_extension_hooks_fill_only_their_named_evidence_fields():
    candidate = _candidate("hooked", (10.0, 10.0))
    packet = _packet(np.zeros((30, 30), dtype=np.uint8))
    judges = EvidenceJudges(
        hooks={
            "bg_score": lambda candidate, packet: 0.7,
            "rigid_violation": lambda candidate, packet: 0.25,
        }
    )

    evidence = judges.score([candidate], packet)["hooked"]

    assert evidence.bg_score == 0.7
    assert evidence.rigid_violation == 0.25
    assert evidence.phase_similarity == 0.0
    assert evidence.texture_bg_score == 0.0
    assert evidence.notes == ("hook:bg_score", "hook:rigid_violation")
