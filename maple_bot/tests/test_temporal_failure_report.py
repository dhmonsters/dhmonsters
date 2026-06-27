# 투명도형 퍼즐 시간축 selector 실패 분류 리포트를 검증한다.
from _temporal_failure_report import classify_failure, first_bad_frame


def test_first_bad_frame_returns_first_frame_over_threshold():
    path = {10: (0.0, 0.0), 11: (50.0, 0.0), 12: (60.0, 0.0)}
    gt = {10: (5.0, 0.0), 11: (0.0, 0.0), 12: (0.0, 0.0)}

    assert first_bad_frame(path, gt, threshold=40.0) == 11


def test_classify_failure_detects_candidate_selection_failure():
    temporal = {"success": False, "mean": 90.0}
    raw_center = {"success": True, "mean": 20.0}
    raw_box = {"success": True, "mean": 10.0}

    assert classify_failure(temporal, raw_center, raw_box) == "candidate_selection"


def test_classify_failure_detects_box_internal_reconstruction_gap():
    temporal = {"success": False, "mean": 55.0}
    raw_center = {"success": False, "mean": 51.0}
    raw_box = {"success": True, "mean": 12.0}

    assert classify_failure(temporal, raw_center, raw_box) == "box_internal_reconstruction"


def test_classify_failure_detects_candidate_source_gap():
    temporal = {"success": False, "mean": 100.0}
    raw_center = {"success": False, "mean": 80.0}
    raw_box = {"success": False, "mean": 60.0}

    assert classify_failure(temporal, raw_center, raw_box) == "candidate_source_gap"
