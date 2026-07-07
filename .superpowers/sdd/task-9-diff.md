diff --git a/shorts_growth_agent/backend/src/shorts_agent/api/projects.py b/shorts_growth_agent/backend/src/shorts_agent/api/projects.py
index bc46b5cc..ddb8dfc6 100644
--- a/shorts_growth_agent/backend/src/shorts_agent/api/projects.py
+++ b/shorts_growth_agent/backend/src/shorts_agent/api/projects.py
@@ -1,4 +1,84 @@
-# 프로젝트 관련 API 라우터를 위한 플레이스홀더입니다.
-from fastapi import APIRouter
+# 프로젝트 API 라우터를 구성해 프로젝트 생성/조회/기획 생성 요청을 처리합니다.
+from pathlib import Path
+from uuid import uuid4
+
+from fastapi import APIRouter, Depends, HTTPException, Request, status
+from sqlalchemy.orm import Session
+
+from shorts_agent.db import init_db, make_engine, make_session_factory
+from shorts_agent.repositories.project_repository import ProjectRepository
+from shorts_agent.schemas import ProjectCreate, ProjectRead
+from shorts_agent.services.script_planner import HarnessConfig, ScriptPlanner
+
 
 router = APIRouter()
+
+
+def _prepare_sqlite_url(database_url: str) -> str:
+    if not database_url.startswith("sqlite:///"):
+        return database_url
+    db_path = Path(database_url.removeprefix("sqlite:///"))
+    if str(db_path) == ":memory:":
+        return f"sqlite:///file:shorts_growth_{uuid4().hex}?mode=memory&cache=shared&uri=true"
+    if db_path.parent:
+        db_path.parent.mkdir(parents=True, exist_ok=True)
+    return database_url
+
+
+def _get_session_factory(request: Request):
+    if not hasattr(request.app.state, "SessionFactory"):
+        database_url = _prepare_sqlite_url(request.app.state.database_url)
+        engine = make_engine(database_url=database_url)
+        init_db(engine)
+        request.app.state.SessionFactory = make_session_factory(engine)
+    return request.app.state.SessionFactory
+
+
+def get_session(request: Request):
+    SessionFactory = _get_session_factory(request)
+    with SessionFactory() as session:
+        yield session
+
+
+@router.post("/projects", status_code=status.HTTP_201_CREATED)
+def create_project(payload: ProjectCreate, session: Session = Depends(get_session)):
+    project = ProjectRepository(session).create_project(
+        title=payload.title,
+        category=payload.category,
+        selected_keyword=payload.selected_keyword,
+    )
+    return ProjectRead.model_validate(project).model_dump()
+
+
+@router.get("/projects/{project_id}")
+def get_project(project_id: int, session: Session = Depends(get_session)):
+    project = ProjectRepository(session).get_project(project_id)
+    if project is None:
+        raise HTTPException(status_code=404, detail="project not found")
+    return ProjectRead.model_validate(project).model_dump()
+
+
+@router.post("/projects/{project_id}/generate-plan")
+def generate_plan(project_id: int, session: Session = Depends(get_session)):
+    project = ProjectRepository(session).get_project(project_id)
+    if project is None:
+        raise HTTPException(status_code=404, detail="project not found")
+
+    harness = HarnessConfig(
+        name="뉴스+이슈",
+        tone="명료",
+        hook_strength="강함",
+        target_seconds=45,
+        forbidden_terms=["광고", "100%", "부적절"],
+    )
+    plan = ScriptPlanner().generate(
+        keyword=project.selected_keyword or project.title,
+        category=project.category,
+        harness=harness,
+    )
+    return {
+        "keyword": plan.keyword,
+        "category": plan.category,
+        "title_candidate": plan.title_candidate,
+        "scenes": [scene.__dict__ for scene in plan.scenes],
+    }
diff --git a/shorts_growth_agent/backend/src/shorts_agent/main.py b/shorts_growth_agent/backend/src/shorts_agent/main.py
index 294b7048..09d8036f 100644
--- a/shorts_growth_agent/backend/src/shorts_agent/main.py
+++ b/shorts_growth_agent/backend/src/shorts_agent/main.py
@@ -1,17 +1,22 @@
-# FastAPI 앱 생성 및 라우터 등록을 담당합니다.
+# FastAPI 앱 생성과 라우터 등록을 담당합니다.
 from fastapi import FastAPI
 
 from shorts_agent.api.health import router as health_router
 from shorts_agent.api.performance import router as performance_router
+from shorts_agent.api.projects import router as projects_router
 from shorts_agent.api.trends import router as trends_router
+from shorts_agent.config import get_settings
 
 
-def create_app() -> FastAPI:
+def create_app(database_url: str | None = None) -> FastAPI:
     app = FastAPI(title="Shorts Growth Agent")
+    app.state.database_url = database_url or get_settings().database_url
+
     app.include_router(health_router, prefix="/api")
     app.include_router(performance_router, prefix="/api")
     app.include_router(trends_router, prefix="/api")
+    app.include_router(projects_router, prefix="/api")
     return app
 
 
 app = create_app()
diff --git a/shorts_growth_agent/backend/tests/test_api_projects.py b/shorts_growth_agent/backend/tests/test_api_projects.py
new file mode 100644
index 00000000..59c42df6
--- /dev/null
+++ b/shorts_growth_agent/backend/tests/test_api_projects.py
@@ -0,0 +1,60 @@
+# 프로젝트 API 라우터 동작을 검증합니다.
+from fastapi.testclient import TestClient
+
+from shorts_agent.main import create_app
+
+
+def test_create_app_does_not_create_sqlite_file_until_project_route(tmp_path):
+    db_path = tmp_path / "shorts_agent.db"
+    app = create_app(database_url=f"sqlite:///{db_path.as_posix()}")
+
+    assert not db_path.exists()
+
+    client = TestClient(app)
+    response = client.post(
+        "/api/projects",
+        json={"title": "게임 이슈", "category": "게임", "selected_keyword": "업데이트"},
+    )
+
+    assert response.status_code == 201
+    assert db_path.exists()
+
+
+def test_create_project_and_generate_plan():
+    client = TestClient(create_app(database_url="sqlite:///:memory:"))
+
+    create_response = client.post(
+        "/api/projects",
+        json={
+            "title": "게임 이슈",
+            "category": "게임",
+            "selected_keyword": "업데이트",
+        },
+    )
+    assert create_response.status_code == 201
+    project_id = create_response.json()["id"]
+
+    plan_response = client.post(f"/api/projects/{project_id}/generate-plan")
+
+    assert plan_response.status_code == 200
+    body = plan_response.json()
+    assert body["keyword"] == "업데이트"
+    assert len(body["scenes"]) >= 3
+
+
+def test_get_project_not_found():
+    client = TestClient(create_app(database_url="sqlite:///:memory:"))
+
+    response = client.get("/api/projects/99999")
+
+    assert response.status_code == 404
+    assert response.json()["detail"] == "project not found"
+
+
+def test_generate_plan_not_found():
+    client = TestClient(create_app(database_url="sqlite:///:memory:"))
+
+    response = client.post("/api/projects/99999/generate-plan")
+
+    assert response.status_code == 404
+    assert response.json()["detail"] == "project not found"
