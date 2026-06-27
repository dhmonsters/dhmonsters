# 투명도형 퍼즐 decal identity 실험 채점 경로를 검증한다.
from _temporal_decal_identity_score import choose_guarded_decal_path, decal_identity_path_from_frames
from _temporal_identity_selector import TemporalFrame


def test_decal_identity_path_uses_background_penalty_and_split_recovery():
    frames = [
        TemporalFrame(1, ((10.0, 0.0, 0.80, 20.0, 20.0),)),
        TemporalFrame(2, ((80.0, 0.0, 0.95, 160.0, 40.0),)),
        TemporalFrame(
            3,
            (
                (32.0, 0.0, 0.99, 20.0, 20.0),
                (30.0, 0.0, 0.20, 20.0, 20.0),
            ),
            background_identity_penalties=(1.0, 0.0),
        ),
    ]

    path = decal_identity_path_from_frames(frames, anchor=(0.0, 0.0))

    assert path[3] == (30.0, 0.0)


def test_choose_guarded_decal_path_accepts_smoother_lower_background_ratio_path():
    expected = {
        1: [(1, (0.0, 0.0, 24.0, 24.0, 0.9))],
        2: [(1, (10.0, 0.0, 24.0, 24.0, 0.9))],
    }
    base = {1: (0.0, 0.0), 2: (10.0, 0.0)}
    decal = {1: (0.0, 0.0), 2: (50.0, 0.0)}

    chosen = choose_guarded_decal_path(base, decal, expected, frames=[1, 2], max_step=80.0)

    assert chosen == decal


def test_choose_guarded_decal_path_rejects_too_rough_decal_path():
    expected = {
        1: [(1, (0.0, 0.0, 24.0, 24.0, 0.9))],
        2: [(1, (10.0, 0.0, 24.0, 24.0, 0.9))],
    }
    base = {1: (0.0, 0.0), 2: (10.0, 0.0)}
    decal = {1: (0.0, 0.0), 2: (120.0, 0.0)}

    chosen = choose_guarded_decal_path(base, decal, expected, frames=[1, 2], max_step=80.0)

    assert chosen == base
