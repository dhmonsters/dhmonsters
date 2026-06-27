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
    assert result.states[2] == "MERGED_HOLD"
    assert result.states[3] == "REACQUIRE_CANDIDATE"


def test_selector_coasts_without_candidates_and_marks_identity_hold():
    frames = [
        TemporalFrame(1, ((10.0, 0.0, 0.80, 20.0, 20.0),)),
        TemporalFrame(2, ()),
        TemporalFrame(3, ((30.0, 0.0, 0.80, 20.0, 20.0),)),
    ]

    result = select_temporal_identity(frames, anchor=(0.0, 0.0), config=TemporalIdentityConfig(keep=8))

    assert result.path[2] == (20.0, 0.0)
    assert result.path[3] == (30.0, 0.0)
    assert result.states[2] == "MERGED_HOLD"
    assert result.states[3] == "REACQUIRE_CANDIDATE"


def test_selector_can_defer_identity_when_candidate_center_jumps_from_prediction():
    frames = [
        TemporalFrame(1, ((10.0, 0.0, 0.80, 20.0, 20.0),)),
        TemporalFrame(2, ((20.0, 0.0, 0.80, 20.0, 20.0),)),
        TemporalFrame(3, ((60.0, 0.0, 0.99, 20.0, 20.0),)),
        TemporalFrame(4, ((40.0, 0.0, 0.80, 20.0, 20.0),)),
    ]

    result = select_temporal_identity(
        frames,
        anchor=(0.0, 0.0),
        config=TemporalIdentityConfig(
            keep=8,
            prediction_hold_cost=1.0,
            prediction_hold_distance_gate=32.0,
            score_weight=0.0,
        ),
    )

    assert result.path[3] == (30.0, 0.0)
    assert result.path[4] == (40.0, 0.0)
    assert result.states[3] == "RELEASE_PENDING"
    assert result.states[4] == "REACQUIRE_CANDIDATE"


def test_selector_restores_internal_point_when_prediction_is_inside_small_box():
    frames = [
        TemporalFrame(1, ((10.0, 0.0, 0.80, 20.0, 20.0),)),
        TemporalFrame(2, ((20.0, 0.0, 0.80, 20.0, 20.0),)),
        TemporalFrame(3, ((34.0, 0.0, 0.99, 30.0, 20.0),)),
    ]

    result = select_temporal_identity(
        frames,
        anchor=(0.0, 0.0),
        config=TemporalIdentityConfig(
            keep=8,
            prediction_hold_cost=1.0,
            score_weight=0.0,
        ),
    )

    assert result.path[3] == (30.0, 0.0)
    assert result.states[3] == "RELEASE_PENDING"


def test_selector_does_not_defer_identity_when_track_disagrees_with_prediction():
    frames = [
        TemporalFrame(1, ((10.0, 0.0, 0.80, 20.0, 20.0),), track_hint=(10.0, 0.0)),
        TemporalFrame(2, ((20.0, 0.0, 0.80, 20.0, 20.0),), track_hint=(20.0, 0.0)),
        TemporalFrame(3, ((34.0, 0.0, 0.99, 30.0, 20.0),), track_hint=(120.0, 120.0)),
    ]

    result = select_temporal_identity(
        frames,
        anchor=(0.0, 0.0),
        config=TemporalIdentityConfig(
            keep=8,
            prediction_hold_cost=1.0,
            prediction_hold_track_gate=40.0,
            score_weight=0.0,
        ),
    )

    assert result.path[3] == (34.0, 0.0)
    assert result.states[3] == "TRACK_CONFIDENT"


def test_selector_defers_identity_when_track_agrees_with_prediction_gate():
    frames = [
        TemporalFrame(1, ((10.0, 0.0, 0.80, 20.0, 20.0),), track_hint=(10.0, 0.0)),
        TemporalFrame(2, ((20.0, 0.0, 0.80, 20.0, 20.0),), track_hint=(20.0, 0.0)),
        TemporalFrame(3, ((34.0, 0.0, 0.99, 30.0, 20.0),), track_hint=(31.0, 0.0)),
    ]

    result = select_temporal_identity(
        frames,
        anchor=(0.0, 0.0),
        config=TemporalIdentityConfig(
            keep=8,
            prediction_hold_cost=1.0,
            prediction_hold_track_gate=40.0,
            score_weight=0.0,
        ),
    )

    assert result.path[3] == (30.0, 0.0)
    assert result.states[3] == "RELEASE_PENDING"


def test_selector_default_does_not_use_conflicting_track_hint_as_identity_cost():
    frames = [
        TemporalFrame(1, ((10.0, 0.0, 0.80, 20.0, 20.0),), track_hint=(10.0, 0.0)),
        TemporalFrame(2, ((20.0, 0.0, 0.80, 20.0, 20.0),), track_hint=(20.0, 0.0)),
        TemporalFrame(
            3,
            (
                (30.0, 45.0, 0.80, 20.0, 20.0),
                (30.0, -45.0, 0.80, 20.0, 20.0),
            ),
            track_hint=(30.0, -45.0),
        ),
    ]

    result = select_temporal_identity(frames, anchor=(0.0, 0.0))

    assert result.path[3] == (30.0, 45.0)


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


def test_selector_uses_candidate_background_penalty_and_target_support():
    frames = [
        TemporalFrame(
            1,
            ((10.0, 0.0, 0.99, 20.0, 20.0), (12.0, 0.0, 0.30, 20.0, 20.0)),
            background_penalties=(1.0, 0.0),
            target_supports=(0.0, 1.0),
        ),
        TemporalFrame(
            2,
            ((20.0, 0.0, 0.99, 20.0, 20.0), (24.0, 0.0, 0.30, 20.0, 20.0)),
            background_penalties=(1.0, 0.0),
            target_supports=(0.0, 1.0),
        ),
    ]

    result = select_temporal_identity(
        frames,
        anchor=(0.0, 0.0),
        config=TemporalIdentityConfig(
            keep=8,
            track_hint_weight=0.0,
            background_penalty_weight=20.0,
            target_support_weight=20.0,
        ),
    )

    assert result.path == {
        1: (12.0, 0.0),
        2: (24.0, 0.0),
    }


def test_frames_from_jsonl_rows_normalizes_candidates_and_anchor():
    rows = [
        {"track": [5, 6], "cands": [[10, 20, 0.9], ["bad"]]},
        {"track": None, "cands": [[30, 40, 0.8, 12, 14]]},
    ]

    frames, anchor = frames_from_jsonl_rows(rows, default_size=24.0)

    assert anchor == (5.0, 6.0)
    assert frames == [
        TemporalFrame(
            0,
            ((10.0, 20.0, 0.9, 24.0, 24.0),),
            track_hint=(5.0, 6.0),
            background_penalties=(0.0,),
            target_supports=(0.0,),
            background_ids=(None,),
        ),
        TemporalFrame(
            1,
            ((30.0, 40.0, 0.8, 12.0, 14.0),),
            background_penalties=(0.0,),
            target_supports=(0.0,),
            background_ids=(None,),
        ),
    ]


def test_frames_from_jsonl_rows_marks_motion_outlier_as_target_support():
    rows = [
        {
            "track": [0, 0],
            "cands": [
                [0, 0, 0.9, 20, 20],
                [20, 0, 0.9, 20, 20],
                [40, 0, 0.9, 20, 20],
                [100, 0, 0.6, 20, 20],
            ],
        },
        {
            "track": [0, 0],
            "cands": [
                [2, 0, 0.9, 20, 20],
                [22, 0, 0.9, 20, 20],
                [42, 0, 0.9, 20, 20],
                [130, 0, 0.6, 20, 20],
            ],
        },
    ]

    frames, _anchor = frames_from_jsonl_rows(rows, default_size=20.0)

    assert frames[1].target_supports[3] > frames[1].target_supports[0]


def test_selector_penalizes_long_run_on_same_background_id():
    frames = [
        TemporalFrame(
            1,
            ((10.0, 0.0, 0.99, 20.0, 20.0), (12.0, 0.0, 0.40, 20.0, 20.0)),
            background_ids=(7, None),
        ),
        TemporalFrame(
            2,
            ((20.0, 0.0, 0.99, 20.0, 20.0), (24.0, 0.0, 0.40, 20.0, 20.0)),
            background_ids=(7, None),
        ),
        TemporalFrame(
            3,
            ((30.0, 0.0, 0.99, 20.0, 20.0), (36.0, 0.0, 0.40, 20.0, 20.0)),
            background_ids=(7, None),
        ),
    ]

    result = select_temporal_identity(
        frames,
        anchor=(0.0, 0.0),
        config=TemporalIdentityConfig(
            keep=8,
            track_hint_weight=0.0,
            target_support_weight=0.0,
            background_penalty_weight=0.0,
            background_run_weight=30.0,
            background_run_grace=1,
        ),
    )

    assert result.path[3] == (36.0, 0.0)
