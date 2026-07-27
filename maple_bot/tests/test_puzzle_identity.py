# 투명도형 퍼즐 신분 추적기가 보류와 복원 상태를 안정적으로 전환하는지 검증한다.
from core.puzzle.identity import IdentityTracker, _candidate_cost_parts
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
    color_residual: float = 0.0,
) -> dict[str, CandidateEvidence]:
    return {
        candidate.candidate_id: CandidateEvidence(
            candidate_id=candidate.candidate_id,
            bg_score=bg_score,
            motion_divergence=motion_divergence,
            rigid_violation=rigid_violation,
            color_residual=color_residual,
            merge_likelihood=merge_likelihood,
        )
    }


def _evidence_many(
    *items: tuple[Candidate, CandidateEvidence],
) -> dict[str, CandidateEvidence]:
    return {candidate.candidate_id: evidence for candidate, evidence in items}


def test_white_anchor_initializes_visible_identity():
    tracker = IdentityTracker()

    decision = tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(50.0, 60.0))

    assert decision.state == "INIT_VISIBLE"
    assert decision.point == (50.0, 60.0)
    assert decision.candidate_id is None
    assert decision.confidence == 1.0
    assert decision.hold_frames == 0


def test_cold_start_prefers_strong_white_candidate_over_low_score_noise():
    tracker = IdentityTracker()
    white = Candidate(
        candidate_id="white",
        frame_index=1,
        bbox=(175.0, 240.0, 280.0, 345.0),
        center=(228.0, 294.0),
        score=0.99,
        source="white_anchor",
        class_name="white_anchor",
    )
    noise = _candidate("noise", (199.0, 322.0), score=0.14)
    evidence = _evidence_many(
        (
            white,
            CandidateEvidence(
                candidate_id=white.candidate_id,
                bg_score=0.29,
                texture_bg_score=0.83,
                color_residual=0.23,
                merge_likelihood=0.79,
            ),
        ),
        (
            noise,
            CandidateEvidence(
                candidate_id=noise.candidate_id,
                bg_score=0.33,
                texture_bg_score=0.93,
                color_residual=0.24,
                merge_likelihood=0.08,
            ),
        ),
    )

    decision = tracker.update(frame_index=1, candidates=[white, noise], evidence=evidence)

    assert decision.state == "TRACK_CONFIDENT"
    assert decision.candidate_id == "white"
    assert decision.point == white.center
    assert decision.reason == "cold_start_white_candidate"


def test_reset_clears_identity_state_but_preserves_configuration():
    tracker = IdentityTracker(
        jump_distance=33.0,
        max_hold_frames=7,
        reacquire_distance=52.0,
    )
    tracker.update(frame_index=10, candidates=[], evidence={}, white_anchor=(50.0, 60.0))
    candidate = _candidate("target", (54.0, 63.0))
    tracker.update(frame_index=11, candidates=[candidate], evidence=_evidence(candidate))

    tracker.reset()

    assert tracker.state == "LOST"
    assert tracker.last_point is None
    assert tracker.last_candidate_id is None
    assert tracker.last_frame_index is None
    assert tracker.identity_start_frame_index is None
    assert tracker.velocity == (0.0, 0.0)
    assert tracker.hold_frames == 0
    assert tracker.jump_distance == 33.0
    assert tracker.max_hold_frames == 7
    assert tracker.reacquire_distance == 52.0


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


def test_identity_decision_exposes_ranked_judge_costs_without_gt():
    tracker = IdentityTracker()
    tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(50.0, 50.0))
    near = _candidate("near", (54.0, 50.0), score=0.8)
    far = _candidate("far", (80.0, 50.0), score=0.9)
    evidence = _evidence_many(
        (near, CandidateEvidence(candidate_id=near.candidate_id, motion_divergence=0.4)),
        (far, CandidateEvidence(candidate_id=far.candidate_id, bg_score=0.8)),
    )

    decision = tracker.update(frame_index=2, candidates=[near, far], evidence=evidence)

    ranking = decision.debug["ranking"]
    assert ranking[0]["candidate_id"] == decision.candidate_id
    assert ranking[0]["total_cost"] <= ranking[1]["total_cost"]
    assert set(ranking[0]["cost_parts"]) == {
        "continuity",
        "yolo",
        "overlap",
        "background",
        "phase",
        "texture",
        "motion",
        "rigid",
        "white_blob",
    }
    assert round(sum(ranking[0]["judge_shares"].values()), 6) == 100.0


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


def test_first_hold_frame_rejects_broad_release_candidate_then_reacquires_local_target():
    tracker = IdentityTracker(
        jump_distance=40.0,
        reacquire_distance=45.0,
        release_reacquire_distance=85.0,
        max_hold_frames=4,
    )
    tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(100.0, 100.0))
    target = _candidate("target", (110.0, 100.0))
    tracker.update(frame_index=2, candidates=[target], evidence=_evidence(target))
    far = _candidate("far", (200.0, 100.0))
    suspected = tracker.update(frame_index=3, candidates=[far], evidence=_evidence(far))
    broad_release = _candidate("broad_release", (170.0, 100.0))

    held = tracker.update(
        frame_index=4,
        candidates=[broad_release],
        evidence=_evidence(broad_release),
    )
    local_target = _candidate("local_target", (123.0, 100.0))
    recovered = tracker.update(
        frame_index=5,
        candidates=[local_target],
        evidence=_evidence(local_target),
    )

    assert suspected.state == "OCCLUSION_SUSPECTED"
    assert held.state == "IDENTITY_HOLD"
    assert held.point == (110.0, 100.0)
    assert recovered.state == "REACQUIRE"
    assert recovered.candidate_id == "local_target"


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


def test_color_support_fades_after_initial_visible_frames():
    tracker = IdentityTracker(color_fade_frames=20)
    tracker.update(frame_index=10, candidates=[], evidence={}, white_anchor=(50.0, 50.0))
    near_plain = _candidate("near_plain", (55.0, 50.0))
    far_colored = _candidate("far_colored", (60.0, 50.0))
    early_evidence = _evidence_many(
        (
            near_plain,
            CandidateEvidence(candidate_id=near_plain.candidate_id),
        ),
        (
            far_colored,
            CandidateEvidence(candidate_id=far_colored.candidate_id, color_residual=1.0),
        ),
    )

    early = tracker.update(
        frame_index=11,
        candidates=[near_plain, far_colored],
        evidence=early_evidence,
    )

    assert early.candidate_id == "far_colored"

    tracker = IdentityTracker(color_fade_frames=20)
    tracker.update(frame_index=10, candidates=[], evidence={}, white_anchor=(50.0, 50.0))
    late = tracker.update(
        frame_index=35,
        candidates=[near_plain, far_colored],
        evidence=early_evidence,
    )

    assert late.candidate_id == "near_plain"


def test_white_blob_support_uses_step_schedule_until_frame_40():
    tracker = IdentityTracker()
    tracker.update(frame_index=10, candidates=[], evidence={}, white_anchor=(50.0, 50.0))

    assert tracker._color_weight(10) == 0.70
    assert tracker._color_weight(40) == 0.70
    assert tracker._color_weight(41) == 0.50
    assert tracker._color_weight(50) == 0.50
    assert tracker._color_weight(51) == 0.0


def test_white_blob_support_does_not_restart_on_repeated_visible_anchor():
    tracker = IdentityTracker()
    tracker.update(frame_index=0, candidates=[], evidence={}, white_anchor=(50.0, 50.0))
    tracker.update(frame_index=35, candidates=[], evidence={}, white_anchor=(55.0, 50.0))

    assert tracker._color_weight(39) == 0.50
    assert tracker._color_weight(40) == 0.50
    assert tracker._color_weight(41) == 0.0
    assert tracker._color_weight(51) == 0.0


def test_late_overlap_boosts_motion_and_rigid_after_white_support_is_gone():
    candidate = _candidate("release_candidate", (100.0, 100.0), score=0.8)
    evidence = CandidateEvidence(
        candidate_id=candidate.candidate_id,
        bg_score=0.5,
        phase_similarity=0.5,
        texture_bg_score=0.5,
        motion_divergence=0.5,
        rigid_violation=0.5,
        merge_likelihood=0.4,
    )

    parts = _candidate_cost_parts(candidate, evidence, distance=12.0, color_weight=0.0)

    assert abs(parts["motion"]) > parts["background"]
    assert abs(parts["rigid"]) > parts["phase"]


def test_motion_and_rigid_boost_applies_below_overlap_threshold():
    candidate = _candidate("subtle_release_candidate", (100.0, 100.0), score=0.8)
    evidence = CandidateEvidence(
        candidate_id=candidate.candidate_id,
        motion_divergence=0.2,
        rigid_violation=0.2,
        merge_likelihood=0.0,
    )

    parts = _candidate_cost_parts(candidate, evidence, distance=12.0, color_weight=0.0)

    assert round(abs(parts["motion"]), 3) == 11.04
    assert round(abs(parts["rigid"]), 3) == 11.04


def test_overlap_candidate_gets_extra_switch_penalty():
    tracker = IdentityTracker(merge_threshold=0.95, overlap_switch_penalty=20.0)
    tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(50.0, 50.0))
    target = _candidate("target", (54.0, 50.0))
    tracker.update(frame_index=2, candidates=[target], evidence=_evidence(target))
    continuation = _candidate("target", (61.0, 50.0), score=0.75)
    overlap_decoy = _candidate("overlap_decoy", (58.0, 50.0), score=0.95)
    evidence = _evidence_many(
        (
            continuation,
            CandidateEvidence(candidate_id=continuation.candidate_id),
        ),
        (
            overlap_decoy,
            CandidateEvidence(candidate_id=overlap_decoy.candidate_id, merge_likelihood=0.3),
        ),
    )

    decision = tracker.update(
        frame_index=3,
        candidates=[continuation, overlap_decoy],
        evidence=evidence,
    )

    assert decision.state == "TRACK_CONFIDENT"
    assert decision.candidate_id == "target"
    assert decision.point == (61.0, 50.0)


def test_continuity_can_beat_low_yolo_fragment_during_split():
    tracker = IdentityTracker()
    tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(562.0, 119.0))
    previous = _candidate("previous", (571.0, 118.0), score=0.74)
    tracker.update(frame_index=2, candidates=[previous], evidence=_evidence(previous, merge_likelihood=0.24))
    low_score_fragment = _candidate("low_score_fragment", (570.0, 103.0), score=0.106)
    release_candidate = _candidate("release_candidate", (597.0, 120.0), score=0.717)
    evidence = _evidence_many(
        (
            low_score_fragment,
            CandidateEvidence(candidate_id=low_score_fragment.candidate_id, merge_likelihood=0.265),
        ),
        (
            release_candidate,
            CandidateEvidence(candidate_id=release_candidate.candidate_id, merge_likelihood=0.44),
        ),
    )

    decision = tracker.update(
        frame_index=3,
        candidates=[low_score_fragment, release_candidate],
        evidence=evidence,
    )

    assert decision.state == "TRACK_CONFIDENT"
    assert decision.candidate_id == "release_candidate"
    assert decision.point == (597.0, 120.0)


def test_overlap_evidence_can_beat_near_yolo_continuity():
    tracker = IdentityTracker(jump_distance=80.0, merge_threshold=0.95)
    tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(100.0, 100.0))
    previous = _candidate("previous", (110.0, 100.0), score=0.9)
    tracker.update(frame_index=2, candidates=[previous], evidence=_evidence(previous))
    near_background = _candidate("near_background", (121.0, 100.0), score=0.9)
    release_target = _candidate("release_target", (170.0, 100.0), score=0.42)
    evidence = _evidence_many(
        (
            near_background,
            CandidateEvidence(
                candidate_id=near_background.candidate_id,
                bg_score=0.9,
                phase_similarity=0.9,
                texture_bg_score=0.9,
                merge_likelihood=0.45,
            ),
        ),
        (
            release_target,
            CandidateEvidence(
                candidate_id=release_target.candidate_id,
                motion_divergence=0.55,
                rigid_violation=0.55,
                bg_score=0.2,
                phase_similarity=0.2,
                texture_bg_score=0.2,
                merge_likelihood=0.35,
            ),
        ),
    )

    decision = tracker.update(
        frame_index=3,
        candidates=[near_background, release_target],
        evidence=evidence,
    )

    assert decision.state == "TRACK_CONFIDENT"
    assert decision.candidate_id == "release_target"
    assert decision.point == (170.0, 100.0)


def test_overlap_evidence_does_not_promote_low_yolo_noise_over_local_track():
    tracker = IdentityTracker(jump_distance=80.0, merge_threshold=0.95)
    tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(180.0, 100.0))
    previous = _candidate("previous", (180.0, 100.0), score=0.9)
    tracker.update(frame_index=2, candidates=[previous], evidence=_evidence(previous))
    local_track = _candidate("local_track", (185.0, 100.0), score=0.59)
    low_yolo_noise = _candidate("low_yolo_noise", (220.0, 100.0), score=0.16)
    evidence = _evidence_many(
        (
            local_track,
            CandidateEvidence(
                candidate_id=local_track.candidate_id,
                motion_divergence=0.47,
                rigid_violation=0.47,
                bg_score=0.2,
                phase_similarity=0.2,
                texture_bg_score=0.2,
                merge_likelihood=0.37,
            ),
        ),
        (
            low_yolo_noise,
            CandidateEvidence(
                candidate_id=low_yolo_noise.candidate_id,
                motion_divergence=1.0,
                rigid_violation=1.0,
                bg_score=0.34,
                phase_similarity=0.0,
                texture_bg_score=0.98,
                merge_likelihood=0.38,
            ),
        ),
    )

    decision = tracker.update(
        frame_index=3,
        candidates=[local_track, low_yolo_noise],
        evidence=evidence,
    )

    assert decision.state == "TRACK_CONFIDENT"
    assert decision.candidate_id == "local_track"
    assert decision.point == (185.0, 100.0)


def test_hold_reacquires_candidate_near_last_identity_after_one_extra_confirmation_frame():
    tracker = IdentityTracker(jump_distance=60.0, reacquire_distance=45.0, merge_threshold=0.6)
    tracker.update(frame_index=1, candidates=[], evidence={}, white_anchor=(100.0, 100.0))
    previous = _candidate("previous", (150.0, 100.0), score=0.8)
    tracker.update(frame_index=2, candidates=[previous], evidence=_evidence(previous))
    merged = _candidate("merged", (200.0, 100.0), score=0.8)
    tracker.update(frame_index=3, candidates=[merged], evidence=_evidence(merged, merge_likelihood=0.9))
    release = _candidate("release", (160.0, 140.0), score=0.72)

    first_release = tracker.update(
        frame_index=4,
        candidates=[release],
        evidence=_evidence(release, merge_likelihood=0.2),
    )
    release_confirmed = _candidate("release_confirmed", (162.0, 141.0), score=0.72)
    decision = tracker.update(
        frame_index=5,
        candidates=[release_confirmed],
        evidence=_evidence(release_confirmed, merge_likelihood=0.2),
    )

    assert first_release.state == "IDENTITY_HOLD"
    assert decision.state == "REACQUIRE"
    assert decision.candidate_id == "release_confirmed"
    assert decision.point == (162.0, 141.0)
