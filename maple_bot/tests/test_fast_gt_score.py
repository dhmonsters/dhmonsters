# 투명도형 퍼즐 16GT 경량 채점기의 순수 계산을 검증한다.

from _fast_gt_score import (
    raw_box_oracle_path,
    raw_center_oracle_path,
    score_path,
    summarize_results,
    track_path_from_rows,
)


def test_track_path_from_rows_reads_track_and_engine_points():
    rows = [
        {"track": [1, 2], "engine": {"track": [3, 4]}},
        {"track": None, "engine": {"track": [5, 6]}},
        {"track": [7, 8], "engine": {}},
    ]

    assert track_path_from_rows(rows, source="track") == {0: (1.0, 2.0), 2: (7.0, 8.0)}
    assert track_path_from_rows(rows, source="engine") == {0: (3.0, 4.0), 1: (5.0, 6.0)}


def test_raw_center_oracle_chooses_nearest_candidate_center():
    rows = [
        {"cands": [[0, 0, 0.9], [10, 0, 0.8]]},
        {"cands": [[100, 100, 0.9], [25, 25, 0.4]]},
    ]
    gt = {0: (8.0, 0.0), 1: (20.0, 25.0)}

    assert raw_center_oracle_path(rows, gt) == {0: (10.0, 0.0), 1: (25.0, 25.0)}


def test_raw_box_oracle_uses_closest_point_inside_candidate_box():
    rows = [
        {"cands": [[10, 10, 0.9, 10, 10]]},
        {"cands": [[50, 50, 0.9, 20, 20], [100, 100, 0.9, 20, 20]]},
    ]
    gt = {0: (14.0, 13.0), 1: (35.0, 50.0)}

    assert raw_box_oracle_path(rows, gt) == {0: (14.0, 13.0), 1: (40.0, 50.0)}


def test_score_path_requires_mean_error_and_coverage():
    gt = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (20.0, 0.0)}
    path = {0: (3.0, 4.0), 1: (13.0, 4.0)}

    score = score_path(path, gt, success_px=6.0, min_coverage=0.9)

    assert score["n"] == 2
    assert score["coverage"] == 2 / 3
    assert score["success"] is False


def test_summarize_results_counts_each_metric_success():
    results = [
        {"track": {"success": True}, "raw_center_oracle": {"success": False}},
        {"track": {"success": False}, "raw_center_oracle": {"success": True}},
    ]

    assert summarize_results(results, metrics=("track", "raw_center_oracle")) == {
        "track": 1,
        "raw_center_oracle": 1,
    }
