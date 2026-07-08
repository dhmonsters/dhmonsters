# 트렌드 후보 검색 API의 사용자 체감 동작을 검증합니다.
from fastapi.testclient import TestClient

from shorts_agent.main import create_app


def test_get_trends_returns_korean_sample_candidates_without_api_key():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))

    response = client.get("/api/trends?region=KR&category_id=20")

    assert response.status_code == 200
    body = response.json()
    assert body["region"] == "KR"
    assert body["source"] == "sample"
    assert body["items"]
    assert all(item["category_id"] == "20" for item in body["items"])
    assert {"video_id", "title", "channel_title", "score", "keyword_candidates"} <= set(
        body["items"][0]
    )


def test_get_trends_filters_sample_candidates_by_keyword():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))

    response = client.get("/api/trends?region=KR&keyword=%EA%B2%8C%EC%9E%84")

    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert all(
        "게임" in item["title"] or "게임" in " ".join(item["keyword_candidates"])
        for item in body["items"]
    )


def test_trends_api_allows_local_frontend_preflight():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))

    response = client.options(
        "/api/trends",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
