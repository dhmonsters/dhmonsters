# 시간별 성과 곡선을 먼저 보고 제작 데이터를 보조로 사용한다.
from fastapi.testclient import TestClient
from shorts_agent.main import create_app
from shorts_agent.services.performance_analysis import PerformanceAnalysisService, PerformancePoint


def test_low_ctr_after_good_impressions_points_to_title_thumbnail():
    snapshots = [
        PerformancePoint(
            minutes_since_upload=60, views=100, impressions=5000, ctr=0.02, retention_3s=0.7
        ),
        PerformancePoint(
            minutes_since_upload=360, views=130, impressions=9000, ctr=0.014, retention_3s=0.68
        ),
    ]

    result = PerformanceAnalysisService().analyze(snapshots, {"hook_type": "question"})

    assert result.cause_candidates[0].code == "title_thumbnail_mismatch"


def test_latest_low_ctr_without_time_series_pattern_needs_more_data():
    snapshots = [
        PerformancePoint(
            minutes_since_upload=60, views=500, impressions=5000, ctr=0.1, retention_3s=0.72
        ),
        PerformancePoint(
            minutes_since_upload=360, views=130, impressions=9000, ctr=0.014, retention_3s=0.68
        ),
    ]

    result = PerformanceAnalysisService().analyze(snapshots, {"hook_type": "question"})

    assert result.cause_candidates[0].code == "insufficient_signal"


def test_high_ctr_low_three_second_retention_points_to_hook():
    snapshots = [
        PerformancePoint(
            minutes_since_upload=60, views=600, impressions=5000, ctr=0.12, retention_3s=0.22
        ),
    ]

    result = PerformanceAnalysisService().analyze(snapshots, {"first_scene_motion": "none"})

    assert result.cause_candidates[0].code == "weak_first_three_seconds"


def test_analyze_endpoint_registers_performance_router_low_ctr():
    client = TestClient(create_app())

    payload = {
        "snapshots": [
            {
                "minutes_since_upload": 360,
                "views": 130,
                "impressions": 9000,
                "ctr": 0.014,
                "retention_3s": 0.68,
            }
        ],
        "production_facts": {"hook_type": "question"},
    }

    response = client.post("/api/performance/analyze", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["cause_candidates"][0]["code"] == "title_thumbnail_mismatch"
