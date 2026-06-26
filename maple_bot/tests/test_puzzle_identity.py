# 투명도형 퍼즐 신분 추적기가 보류와 복원 상태를 안정적으로 전환하는지 검증한다.
from core.puzzle.identity import IdentityTracker
from core.puzzle.models import Candidate, CandidateEvidence


def _candidate(
    candidate_id: str,
    center: tuple[float, float],
    score: float = 0.8,
) -> Candidate:
    cx, cy = center
    return Candidate(
        candidate_id=candidate_id,
        frame_index=1,
        bbox=(cx - 5.0, cy - 5.0, cx + 5.0, cy + 5.0),
        center=center,
        score=score,
        source="raw",
    )


def _evidence(
    candidate: Candidate,
    *,
    merge_likelihood: float = 0.0,
    bg_score: float = 0.0,
    motion_divergence: float = 0.0,
    rigid_violation: float = 0.0,
) -> dict[str, CandidateEvidence]:
    return {
        candidate.candidate_id: CandidateEvidence(
            candidate_id=candidate.candidate_id,
            bg_score=bg_score,
            motion_divergence=motion_divergence,
            rigid_violation=rigid_violation,
            merge_likelihood=merge_likelihood,
        )
    }


def test_white_anchor_initializes_visible_identity():
    tracker = IdentityTracker()

    decision = tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(50.0, 60.0))

    assert decision.state == "INIT_VISIBLE"
    assert decision.point == (50.0, 60.0)
    assert decision.candidate_id is None
    assert decision.confidence == 1.0
    assert decision.hold_frames == 0


def test_near_candidate_after_anchor_becomes_confident_track():
    tracker = IdentityTracker()
    tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(50.0, 60.0))
    candidate = _candidate("target", (54.0, 63.0))

    decision = tracker.update(frame_index=2, candidates=[candidate], evidence=_evidence(candidate))

    assert decision.state == "TRACK_CONFIDENT"
    assert decision.point == (54.0, 63.0)
    assert decision.candidate_id == "target"
    assert decision.hold_frames == 0
    assert decision.debug["distance"] < 10.0


def test_large_jump_or_merge_suspicion_enters_occlusion_state():
    tracker = IdentityTracker(jump_distance=20.0, merge_threshold=0.6)
    tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(50.0, 50.0))
    first = _candidate("target", (54.0, 50.0))
    tracker.update(frame_index=2, candidates=[first], evidence=_evidence(first))
    merged = _candidate("merged_blob", (60.0, 50.0))

    decision = tracker.update(
        frame_index=3,
        candidates=[merged],
        evidence=_evidence(merged, merge_likelihood=0.8),
    )

    assert decision.state == "OCCLUSION_SUSPECTED"
    assert decision.point == (54.0, 50.0)
    assert decision.candidate_id == "target"
    assert decision.hold_frames == 1
    assert decision.reason == "occlusion_suspected"


def test_ambiguous_frames_hold_previous_identity_after_occlusion():
    tracker = IdentityTracker(max_hold_frames=3, merge_threshold=0.6)
    tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(20.0, 20.0))
    target = _candidate("target", (23.0, 20.0))
    tracker.update(frame_index=2, candidates=[target], evidence=_evidence(target))
    merged = _candidate("merged", (25.0, 20.0))
    tracker.update(frame_index=3, candidates=[merged], evidence=_evidence(merged, merge_likelihood=0.9))

    decision = tracker.update(frame_index=4, candidates=[], evidence={})

    assert decision.state == "IDENTITY_HOLD"
    assert decision.point == (23.0, 20.0)
    assert decision.candidate_id == "target"
    assert decision.hold_frames == 2
    assert decision.reason == "hold_no_candidates"


def test_reacquire_then_returns_to_confident_tracking():
    tracker = IdentityTracker(reacquire_distance=30.0, merge_threshold=0.6)
    tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(40.0, 40.0))
    target = _candidate("target", (44.0, 40.0))
    tracker.update(frame_index=2, candidates=[target], evidence=_evidence(target))
    merged = _candidate("merged", (45.0, 40.0))
    tracker.update(frame_index=3, candidates=[merged], evidence=_evidence(merged, merge_likelihood=0.9))
    tracker.update(frame_index=4, candidates=[], evidence={})
    recovered = _candidate("target_recovered", (48.0, 40.0))

    reacquire = tracker.update(
        frame_index=5,
        candidates=[recovered],
        evidence=_evidence(recovered, motion_divergence=0.4, rigid_violation=0.3),
    )
    confident = tracker.update(
        frame_index=6,
        candidates=[_candidate("target_recovered_2", (52.0, 40.0))],
        evidence={},
    )

    assert reacquire.state == "REACQUIRE"
    assert reacquire.candidate_id == "target_recovered"
    assert reacquire.hold_frames == 0
    assert confident.state == "TRACK_CONFIDENT"
    assert confident.point == (52.0, 40.0)


def test_hold_limit_without_reacquire_becomes_lost():
    tracker = IdentityTracker(max_hold_frames=2, merge_threshold=0.6)
    tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(10.0, 10.0))
    target = _candidate("target", (12.0, 10.0))
    tracker.update(frame_index=2, candidates=[target], evidence=_evidence(target))
    merged = _candidate("merged", (13.0, 10.0))
    tracker.update(frame_index=3, candidates=[merged], evidence=_evidence(merged, merge_likelihood=0.9))
    tracker.update(frame_index=4, candidates=[], evidence={})

    decision = tracker.update(frame_index=5, candidates=[], evidence={})

    assert decision.state == "LOST"
    assert decision.point is None
    assert decision.candidate_id is None
    assert decision.reason == "hold_limit_exceeded"
