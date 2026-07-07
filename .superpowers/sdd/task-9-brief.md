# Task 9 Brief: Project API Integration

## Goal

Connect project creation, project lookup, and script plan generation to the real FastAPI app.

## Scope

Modify only these files unless a test failure proves a directly related fix is required.

- `shorts_growth_agent/backend/src/shorts_agent/api/projects.py`
- `shorts_growth_agent/backend/src/shorts_agent/main.py`
- `shorts_growth_agent/backend/tests/test_api_projects.py`
- `.superpowers/sdd/task-9-report.md`

Do not remove existing health, trends, or performance routes.

## Required Behavior

- `create_app(database_url: str | None = None)` accepts an optional database URL.
- `create_app()` initializes the DB and exposes a SQLAlchemy session factory on `app.state.SessionFactory`.
- `POST /api/projects` creates a project and returns status code `201`.
- `GET /api/projects/{project_id}` returns the saved project or `404`.
- `POST /api/projects/{project_id}/generate-plan` generates a deterministic script plan using the saved project's `selected_keyword` when present, otherwise the project title.

## Test First

Create `shorts_growth_agent/backend/tests/test_api_projects.py`.

```python
# 프로젝트 생성 후 대본 계획 생성 API까지 연결한다.
from fastapi.testclient import TestClient

from shorts_agent.main import create_app


def test_create_project_and_generate_plan():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))

    create_response = client.post(
        "/api/projects",
        json={"title": "게임 이슈", "category": "게임", "selected_keyword": "업데이트"},
    )
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    plan_response = client.post(f"/api/projects/{project_id}/generate-plan")

    assert plan_response.status_code == 200
    body = plan_response.json()
    assert body["keyword"] == "업데이트"
    assert len(body["scenes"]) >= 3
```

Add a 404 test for missing project lookup or missing plan generation if it stays small.

Run it before implementation.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api_projects.py -q
```

Expected first failure: `create_app()` does not accept `database_url`, or project routes are missing.

## Implementation Notes

Use the actual existing DB helpers from `shorts_agent.db`.

```python
from shorts_agent.db import init_db, make_engine, make_session_factory
```

`main.py` should keep existing routers and add `projects_router`.

`projects.py` should use the existing repository, schemas, and planner.

```python
# 쇼츠 프로젝트 생성과 대본 계획 생성을 제공한다.
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from shorts_agent.repositories.project_repository import ProjectRepository
from shorts_agent.schemas import ProjectCreate, ProjectRead
from shorts_agent.services.script_planner import HarnessConfig, ScriptPlanner

router = APIRouter()


def get_session(request: Request):
    SessionFactory = request.app.state.SessionFactory
    with SessionFactory() as session:
        yield session


@router.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)):
    project = ProjectRepository(session).create_project(
        title=payload.title,
        category=payload.category,
        selected_keyword=payload.selected_keyword,
    )
    return ProjectRead.model_validate(project).model_dump()


@router.get("/projects/{project_id}")
def get_project(project_id: int, session: Session = Depends(get_session)):
    project = ProjectRepository(session).get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return ProjectRead.model_validate(project).model_dump()


@router.post("/projects/{project_id}/generate-plan")
def generate_plan(project_id: int, session: Session = Depends(get_session)):
    project = ProjectRepository(session).get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    harness = HarnessConfig(
        name="정보+후킹형",
        tone="빠른 정보형",
        hook_strength="강함",
        target_seconds=45,
        forbidden_terms=["무조건", "100%", "확정"],
    )
    plan = ScriptPlanner().generate(project.selected_keyword or project.title, project.category, harness)
    return {
        "keyword": plan.keyword,
        "category": plan.category,
        "title_candidate": plan.title_candidate,
        "scenes": [scene.__dict__ for scene in plan.scenes],
    }
```

## Verification

Run these commands from `shorts_growth_agent/backend`.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api_projects.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py tests/test_subtitle_sync.py tests/test_source_recommender.py tests/test_render_manifest.py tests/test_performance_analysis.py tests/test_api_projects.py -q
```

Report red test output, green test output, and changed files in `.superpowers/sdd/task-9-report.md`.
