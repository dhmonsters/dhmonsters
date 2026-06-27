# 투명도형 퍼즐 residual 채점기의 박스 예측 복원 동작을 검증한다.
from _temporal_identity_selector import TemporalFrame, TemporalIdentityConfig, TemporalIdentityResult
from _temporal_residual_score import box_projected_identity_path


def test_box_projected_identity_path_uses_prediction_inside_candidate_box():
    frames = [TemporalFrame(1, ((20.0, 0.0, 0.9, 20.0, 20.0),))]
    result = TemporalIdentityResult(
        path={1: (20.0, 0.0)},
        states={1: "TRACK_CONFIDENT"},
        candidate_indices={1: 0},
        cost=0.0,
    )

    path = box_projected_identity_path(
        frames,
        result,
        anchor=(10.0, 0.0),
        config=TemporalIdentityConfig(prediction_hold_box_scale=1.0),
    )

    assert path[1] == (10.0, 0.0)


def test_box_projected_identity_path_keeps_center_when_prediction_is_outside_box():
    frames = [TemporalFrame(1, ((50.0, 0.0, 0.9, 10.0, 10.0),))]
    result = TemporalIdentityResult(
        path={1: (50.0, 0.0)},
        states={1: "TRACK_CONFIDENT"},
        candidate_indices={1: 0},
        cost=0.0,
    )

    path = box_projected_identity_path(
        frames,
        result,
        anchor=(0.0, 0.0),
        config=TemporalIdentityConfig(prediction_hold_box_scale=1.0),
    )

    assert path[1] == (50.0, 0.0)
