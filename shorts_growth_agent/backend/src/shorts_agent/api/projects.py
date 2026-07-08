# 프로젝트 API 라우터를 구성해 프로젝트 생성/조회/기획 생성 요청을 처리합니다.
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from shorts_agent.db import init_db, make_engine, make_session_factory
from shorts_agent.repositories.project_repository import ProjectRepository
from shorts_agent.schemas import GeneratePlanRequest, ProjectCreate, ProjectRead
from shorts_agent.services.script_planner import HarnessConfig, ScriptPlanner


router = APIRouter()


def _prepare_sqlite_url(database_url: str) -> str:
    if not database_url.startswith("sqlite:///"):
        return database_url
    db_path = Path(database_url.removeprefix("sqlite:///"))
    if str(db_path) == ":memory:":
        return f"sqlite:///file:shorts_growth_{uuid4().hex}?mode=memory&cache=shared&uri=true"
    if db_path.parent:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return database_url


def _get_session_factory(request: Request):
    if not hasattr(request.app.state, "SessionFactory"):
        database_url = _prepare_sqlite_url(request.app.state.database_url)
        engine = make_engine(database_url=database_url)
        init_db(engine)
        request.app.state.SessionFactory = make_session_factory(engine)
    return request.app.state.SessionFactory


def get_session(request: Request):
    SessionFactory = _get_session_factory(request)
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
def generate_plan(
    project_id: int,
    payload: GeneratePlanRequest | None = None,
    session: Session = Depends(get_session),
):
    project = ProjectRepository(session).get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")

    request_harness = payload.harness if payload else None
    harness = HarnessConfig(
        name=request_harness.name if request_harness else "뉴스+이슈",
        tone=request_harness.tone if request_harness else "명료",
        hook_strength=request_harness.hook_strength if request_harness else "강함",
        target_seconds=request_harness.target_seconds if request_harness else 45,
        forbidden_terms=request_harness.forbidden_terms if request_harness else ["광고", "100%", "부적절"],
        custom_prompt=request_harness.custom_prompt if request_harness else "",
    )
    trend_analysis = payload.trend_analysis if payload else None
    plan = ScriptPlanner().generate(
        keyword=project.selected_keyword or project.title,
        category=project.category,
        harness=harness,
        primary_angle=trend_analysis.primary_angle if trend_analysis else "",
        script_seed=trend_analysis.script_seed if trend_analysis else "",
    )
    return {
        "keyword": plan.keyword,
        "category": plan.category,
        "title_candidate": plan.title_candidate,
        "harness": {
            "name": harness.name,
            "tone": harness.tone,
            "hook_strength": harness.hook_strength,
            "target_seconds": harness.target_seconds,
            "forbidden_terms": harness.forbidden_terms,
            "custom_prompt": harness.custom_prompt,
        },
        "scenes": [scene.__dict__ for scene in plan.scenes],
    }
