# 투명도형 퍼즐 배경 데칼 신분 판별 feature를 검증한다.
from _temporal_decal_identity import (
    background_identity_penalties,
    split_recovery_supports,
)


def test_background_identity_penalties_mark_matched_background_candidates():
    penalties = background_identity_penalties((None, 3, 9))

    assert penalties == (0.0, 1.0, 1.0)


def test_split_recovery_supports_prefers_near_non_background_candidate():
    candidates = (
        (30.0, 0.0, 0.9, 20.0, 20.0),
        (32.0, 0.0, 0.2, 20.0, 20.0),
        (90.0, 0.0, 0.2, 20.0, 20.0),
    )

    supports = split_recovery_supports(
        candidates,
        predicted=(30.0, 0.0),
        background_penalties=(1.0, 0.0, 0.0),
        gate=40.0,
    )

    assert supports[1] == 1.0
    assert supports[0] == 0.0
    assert supports[2] == 0.0
