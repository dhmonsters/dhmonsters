# 투명도형 퍼즐 시간축 실패 전환 리포트를 검증한다.
from _temporal_identity_selector import TemporalFrame, TemporalIdentityResult
from _temporal_transition_report import first_failure_transition, transition_window_rows


def test_first_failure_transition_returns_first_bad_after_good_frame():
    path = {10: (0.0, 0.0), 11: (5.0, 0.0), 12: (80.0, 0.0)}
    gt = {10: (0.0, 0.0), 11: (5.0, 0.0), 12: (10.0, 0.0)}

    transition = first_failure_transition(path, gt, fail_px=40.0)

    assert transition == 12


def test_transition_window_rows_include_candidate_state_and_background_id():
    frames = [
        TemporalFrame(10, ((0.0, 0.0, 0.9, 20.0, 20.0),), background_ids=(None,)),
        TemporalFrame(11, ((5.0, 0.0, 0.9, 20.0, 20.0),), background_ids=(None,)),
        TemporalFrame(12, ((80.0, 0.0, 0.9, 20.0, 20.0),), background_ids=(7,)),
    ]
    result = TemporalIdentityResult(
        path={10: (0.0, 0.0), 11: (5.0, 0.0), 12: (80.0, 0.0)},
        states={10: "TRACK_CONFIDENT", 11: "TRACK_CONFIDENT", 12: "TRACK_CONFIDENT"},
        candidate_indices={10: 0, 11: 0, 12: 0},
        cost=0.0,
    )
    gt = {10: (0.0, 0.0), 11: (5.0, 0.0), 12: (10.0, 0.0)}

    rows = transition_window_rows("clip", frames, result, gt, fail_px=40.0, radius=1)

    assert [row["frame"] for row in rows] == [11, 12]
    assert rows[-1]["transition"] is True
    assert rows[-1]["candidate_index"] == 0
    assert rows[-1]["background_id"] == 7
    assert rows[-1]["error"] == 70.0
