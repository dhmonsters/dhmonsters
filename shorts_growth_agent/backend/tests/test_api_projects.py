# 프로젝트 API 라우터 동작을 검증합니다.
from fastapi.testclient import TestClient

from shorts_agent.main import create_app


def test_create_app_does_not_create_sqlite_file_until_project_route(tmp_path):
    db_path = tmp_path / "shorts_agent.db"
    app = create_app(database_url=f"sqlite:///{db_path.as_posix()}")

    assert not db_path.exists()

    client = TestClient(app)
    response = client.post(
        "/api/projects",
        json={"title": "게임 이슈", "category": "게임", "selected_keyword": "업데이트"},
    )

    assert response.status_code == 201
    assert db_path.exists()


def test_create_project_and_generate_plan():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))

    create_response = client.post(
        "/api/projects",
        json={
            "title": "게임 이슈",
            "category": "게임",
            "selected_keyword": "업데이트",
        },
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    plan_response = client.post(f"/api/projects/{project_id}/generate-plan")

    assert plan_response.status_code == 200
    body = plan_response.json()
    assert body["keyword"] == "업데이트"
    assert len(body["scenes"]) >= 3


def test_generate_plan_uses_request_harness_and_trend_analysis():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))
    create_response = client.post(
        "/api/projects",
        json={
            "title": "신작 게임 업데이트 보상 정리와 반응",
            "category": "게임",
            "selected_keyword": "게임 업데이트",
        },
    )
    project_id = create_response.json()["id"]

    plan_response = client.post(
        f"/api/projects/{project_id}/generate-plan",
        json={
            "harness": {
                "name": "게임 반응형",
                "tone": "친근",
                "hook_strength": "강함",
                "target_seconds": 30,
                "forbidden_terms": ["100%"],
                "custom_prompt": "첫 장면은 보상부터 말하기",
            },
            "trend_analysis": {
                "primary_angle": "업데이트 보상만 빠르게 비교",
                "script_seed": "게임 업데이트 보상",
            },
        },
    )

    assert plan_response.status_code == 200
    body = plan_response.json()
    assert body["harness"]["tone"] == "친근"
    assert body["harness"]["target_seconds"] == 30
    assert "업데이트 보상" in body["scenes"][0]["subtitle"]


def test_get_project_not_found():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))

    response = client.get("/api/projects/99999")

    assert response.status_code == 404
    assert response.json()["detail"] == "project not found"


def test_generate_plan_not_found():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))

    response = client.post("/api/projects/99999/generate-plan")

    assert response.status_code == 404
    assert response.json()["detail"] == "project not found"
