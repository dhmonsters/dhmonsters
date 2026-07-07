# 헬스 체크 API 동작을 검증합니다.
from fastapi.testclient import TestClient
from shorts_agent.main import create_app


def test_health_check_returns_ok():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "shorts-growth-agent"}
