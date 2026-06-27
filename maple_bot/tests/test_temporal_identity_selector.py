# 투명도형 퍼즐 시간축 신분 판별기가 보류와 복원을 수행하는지 검증한다.
from _temporal_identity_selector import (
    TemporalFrame,
    TemporalIdentityConfig,
    frames_from_jsonl_rows,
    select_temporal_identity,
)


def test_selector_prefers_smooth_identity_over_high_score_background():
    frames = [
        TemporalFrame(1, ((10.0, 0.0, 0.40, 20.0, 20.0), (100.0, 0.0, 0.99, 20.0, 20.0))),
        TemporalFrame(2, ((20.0, 0.0, 0.40, 20.0, 20.0), (100.0, 0.0, 0.99, 20.0, 20.0))),
        TemporalFrame(3, ((30.0, 0.0, 0.40, 20.0, 20.0), (100.0, 0.0, 0.99, 20.0, 20.0))),
    ]

    result = select_temporal_identity(frames, anchor=(0.0, 0.0), config=TemporalIdentityConfig(keep=8))

    assert result.path == {
        1: (10.0, 0.0),
        2: (20.0, 0.0),
        3: (30.0, 0.0),
    }
    assert result.states[3] == "TRACK_CONFIDENT"


def test_selector_holds_identity_inside_merge_box_then_reacquires_split_candidate():
    frames = [
        TemporalFrame(1, ((10.0, 0.0, 0.80, 20.0, 20.0),)),
        TemporalFrame(2, ((80.0, 0.0, 0.95, 160.0, 40.0),)),
        TemporalFrame(3, ((30.0, 0.0, 0.65, 20.0, 20.0), (80.0, 0.0, 0.95, 20.0, 20.0))),
    ]

    result = select_temporal_identity(frames, anchor=(0.0, 0.0), config=TemporalIdentityConfig(keep=8))

    assert result.path[1] == (10.0, 0.0)
    assert result.path[2] == (20.0, 0.0)
    assert result.path[3] == (30.0, 0.0)
    assert result.states[2] == "IDENTITY_HOLD"
    assert result.states[3] == "REACQUIRE"


def test_selector_coasts_without_candidates_and_marks_identity_hold():
    frames = [
        TemporalFrame(1, ((10.0, 0.0, 0.80, 20.0, 20.0),)),
        TemporalFrame(2, ()),
        TemporalFrame(3, ((30.0, 0.0, 0.80, 20.0, 20.0),)),
    ]

    result = select_temporal_identity(frames, anchor=(0.0, 0.0), config=TemporalIdentityConfig(keep=8))

    assert result.path[2] == (20.0, 0.0)
    assert result.path[3] == (30.0, 0.0)
    assert result.states[2] == "IDENTITY_HOLD"
    assert result.states[3] == "REACQUIRE"


def test_selector_uses_track_hint_as_soft_identity_evidence():
    frames = [
        TemporalFrame(
            1,
            ((10.0, 0.0, 0.99, 20.0, 20.0), (60.0, 0.0, 0.40, 20.0, 20.0)),
            track_hint=(60.0, 0.0),
        ),
        TemporalFrame(
            2,
            ((10.0, 0.0, 0.99, 20.0, 20.0), (70.0, 0.0, 0.40, 20.0, 20.0)),
            track_hint=(70.0, 0.0),
        ),
    ]

    result = select_temporal_identity(
        frames,
        anchor=(0.0, 0.0),
        config=TemporalIdentityConfig(keep=8, track_hint_weight=2.0),
    )

    assert result.path[1] == (60.0, 0.0)
    assert result.path[2] == (70.0, 0.0)


def test_frames_from_jsonl_rows_normalizes_candidates_and_anchor():
    rows = [
        {"track": [5, 6], "cands": [[10, 20, 0.9], ["bad"]]},
        {"track": None, "cands": [[30, 40, 0.8, 12, 14]]},
    ]

    frames, anchor = frames_from_jsonl_rows(rows, default_size=24.0)

    assert anchor == (5.0, 6.0)
    assert frames == [
        TemporalFrame(0, ((10.0, 20.0, 0.9, 24.0, 24.0),), track_hint=(5.0, 6.0)),
        TemporalFrame(1, ((30.0, 40.0, 0.8, 12.0, 14.0),)),
    ]
