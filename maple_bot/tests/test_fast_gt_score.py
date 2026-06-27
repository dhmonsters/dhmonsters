# 투명도형 퍼즐 16GT 경량 채점기의 순수 계산을 검증한다.
from pathlib import Path

import _fast_gt_score as fast_gt_score
from _fast_gt_score import (
    METRICS,
    markdown_report,
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


def test_markdown_report_includes_temporal_identity_metric():
    results = [
        {
            "name": "clip",
            "gt_frames": 1,
            "track": {"n": 1, "mean": 100.0, "success": False},
            "engine": {"n": 0, "mean": float("inf"), "success": False},
            "temporal_identity": {"n": 1, "mean": 20.0, "success": True},
            "raw_center_oracle": {"n": 1, "mean": 10.0, "success": True},
            "raw_box_oracle": {"n": 1, "mean": 5.0, "success": True},
        }
    ]

    text = markdown_report(results)

    assert "temporal identity" in text
    assert "`temporal_identity`: 1/1" in text
    assert "temporal_identity" in METRICS


def test_score_clip_passes_expected_background_to_temporal_identity():
    calls = {}
    rows = [{"cands": []} for _index in range(53)]
    expected = {
        50: [(7, (10.0, 20.0, 24.0, 24.0, 0.9))],
        51: [(7, (12.0, 20.0, 24.0, 24.0, 0.9))],
        52: [(7, (14.0, 20.0, 24.0, 24.0, 0.9))],
    }

    original_load_rows = fast_gt_score.load_jsonl_rows
    original_load_gt = fast_gt_score.load_red_gt
    original_temporal = fast_gt_score.temporal_identity_path_from_rows
    original_background = getattr(fast_gt_score, "load_expected_background_with_ids", None)
    try:
        fast_gt_score.load_jsonl_rows = lambda _path: rows
        fast_gt_score.load_red_gt = lambda _name, root, min_frame: {50: (10.0, 20.0)}

        def fake_background(name, frames):
            calls["background_name"] = name
            calls["background_frames"] = list(frames)
            return expected, {"period": 12}

        def fake_temporal_identity_path_from_rows(
            input_rows,
            *,
            default_size,
            expected_background_by_frame=None,
        ):
            calls["rows"] = input_rows
            calls["default_size"] = default_size
            calls["expected_background"] = expected_background_by_frame
            return {50: (10.0, 20.0)}

        fast_gt_score.load_expected_background_with_ids = fake_background
        fast_gt_score.temporal_identity_path_from_rows = fake_temporal_identity_path_from_rows

        result = fast_gt_score.score_clip(
            "clip",
            root=Path("unused"),
            min_gt_frame=50,
            default_candidate_size=30.0,
        )

        assert result["temporal_identity"]["success"] is True
        assert calls["background_name"] == "clip"
        assert calls["background_frames"] == [50, 51, 52]
        assert calls["rows"] is rows
        assert calls["default_size"] == 30.0
        assert calls["expected_background"] == expected
    finally:
        fast_gt_score.load_jsonl_rows = original_load_rows
        fast_gt_score.load_red_gt = original_load_gt
        fast_gt_score.temporal_identity_path_from_rows = original_temporal
        if original_background is None:
            delattr(fast_gt_score, "load_expected_background_with_ids")
        else:
            fast_gt_score.load_expected_background_with_ids = original_background
