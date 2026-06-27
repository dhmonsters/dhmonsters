# 투명도형 퍼즐 실패 후보 feature dump와 appearance support 계산을 검증한다.
import numpy as np

from _temporal_candidate_features import (
    box_internal_point,
    candidate_feature_row,
    candidate_local_appearance_supports,
    point_inside_candidate_box,
    prediction_box_point,
    rank_supports,
)


def test_rank_supports_maps_higher_values_to_larger_support():
    assert rank_supports([2.0, 10.0, 6.0]) == (0.0, 1.0, 0.5)


def test_candidate_feature_row_marks_selected_oracle_and_distances():
    candidate = (10.0, 20.0, 0.8, 12.0, 14.0)

    row = candidate_feature_row(
        "clip",
        frame_index=7,
        role="chosen",
        candidate_index=3,
        candidate=candidate,
        gt=(13.0, 24.0),
        selected_index=3,
        raw_center_index=5,
        raw_box_index=3,
    )

    assert row["clip"] == "clip"
    assert row["role"] == "chosen"
    assert row["is_selected"] is True
    assert row["is_raw_center"] is False
    assert row["is_raw_box"] is True
    assert row["gt_dist"] == 5.0


def test_box_internal_point_clamps_gt_inside_candidate_box():
    candidate = (10.0, 10.0, 0.9, 8.0, 6.0)

    assert box_internal_point((20.0, 0.0), candidate) == (14.0, 7.0)


def test_prediction_box_point_clamps_prediction_without_gt():
    candidate = (10.0, 10.0, 0.9, 8.0, 6.0)

    assert prediction_box_point((20.0, 0.0), candidate) == (14.0, 7.0)


def test_point_inside_candidate_box_respects_scale():
    candidate = (10.0, 10.0, 0.9, 8.0, 6.0)

    assert point_inside_candidate_box((14.0, 13.0), candidate)
    assert not point_inside_candidate_box((14.5, 13.5), candidate)
    assert point_inside_candidate_box((14.5, 13.5), candidate, scale=1.2)


def test_candidate_local_appearance_supports_uses_center_vs_ring_contrast():
    diff = np.zeros((40, 40), dtype=np.float32)
    diff[18:23, 18:23] = 20.0
    candidates = (
        (20.0, 20.0, 0.8, 10.0, 10.0),
        (5.0, 5.0, 0.8, 10.0, 10.0),
    )

    supports = candidate_local_appearance_supports(diff, candidates, inner_radius=3, outer_radius=8)

    assert supports[0] > supports[1]
    assert supports[0] == 1.0
