# Task 2 Brief: Database Models And Repositories

## Goal

Add the SQLite/SQLAlchemy data layer for the Shorts Growth Agent MVP and prove project creation/retrieval works.

## Global Constraints

- User-facing text and reports should be Korean.
- Work only inside the assigned files under `shorts_growth_agent`, plus write your report file at `.superpowers/sdd/task-2-report.md`.
- Do not touch `maple_bot` or unrelated root files.
- Every new source file must start with a one-line Korean comment explaining its role.
- Follow TDD. Write tests first, run them and observe failure, then implement the minimum code, then rerun tests.
- Do not run `git add` or `git commit`. The parent agent will commit because this workspace blocks the normal Git index.
- Use the existing backend virtual environment command when running tests: `.\.venv\Scripts\python.exe -m pytest ...`.

## Existing Context

Task 1 already created the backend scaffold, `create_app()`, `/api/health`, `pyproject.toml`, and the backend `.venv`.

## Files To Create

- `shorts_growth_agent/backend/src/shorts_agent/db.py`
- `shorts_growth_agent/backend/src/shorts_agent/models.py`
- `shorts_growth_agent/backend/src/shorts_agent/schemas.py`
- `shorts_growth_agent/backend/src/shorts_agent/repositories/__init__.py`
- `shorts_growth_agent/backend/src/shorts_agent/repositories/project_repository.py`
- `shorts_growth_agent/backend/tests/test_models.py`

## Required Interfaces

- `init_db(engine: Engine) -> None`.
- `ProjectRepository.create_project(title: str, category: str, selected_keyword: str | None = None) -> VideoProject`.
- `ProjectRepository.get_project(project_id: int) -> VideoProject | None`.
- DB tables: `video_projects`, `script_harnesses`, `scene_assets`, `render_outputs`, `performance_snapshots`, `analysis_reports`, `learning_memories`.

## Required Tests

Create `shorts_growth_agent/backend/tests/test_models.py` with focused tests for these behaviors.

```python
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from shorts_agent.db import init_db
from shorts_agent.models import ProjectStatus
from shorts_agent.repositories.project_repository import ProjectRepository


def test_create_project_sets_default_status():
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        repo = ProjectRepository(session)
        project = repo.create_project(title="첫 쇼츠", category="뉴스")

        assert project.id is not None
        assert project.status == ProjectStatus.DRAFT
        assert project.category == "뉴스"


def test_get_project_returns_saved_project():
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)
    Session = sessionmaker(bind=engine)

    with Session() as session:
        repo = ProjectRepository(session)
        created = repo.create_project(title="게임 이슈", category="게임")
        found = repo.get_project(created.id)

        assert found is not None
        assert found.title == "게임 이슈"


def test_init_db_creates_required_tables():
    engine = create_engine("sqlite:///:memory:", future=True)
    init_db(engine)

    table_names = set(inspect(engine).get_table_names())

    assert {
        "video_projects",
        "script_harnesses",
        "scene_assets",
        "render_outputs",
        "performance_snapshots",
        "analysis_reports",
        "learning_memories",
    }.issubset(table_names)
```

## Required Database Module

Implement `shorts_growth_agent/backend/src/shorts_agent/db.py`.

```python
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from shorts_agent.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def init_db(engine: Engine) -> None:
    from shorts_agent import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def make_session_factory(engine: Engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
```

## Required Models

Implement `shorts_growth_agent/backend/src/shorts_agent/models.py`.

```python
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shorts_agent.db import Base


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    RENDERED = "rendered"
    UPLOADED = "uploaded"
    ARCHIVED = "archived"


class VideoProject(Base):
    __tablename__ = "video_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(80))
    selected_keyword: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.DRAFT)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scenes: Mapped[list["SceneAsset"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ScriptHarness(Base):
    __tablename__ = "script_harnesses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(40))
    system_prompt: Mapped[str] = mapped_column(Text)
    output_schema: Mapped[dict] = mapped_column(JSON)
    forbidden_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)


class SceneAsset(Base):
    __tablename__ = "scene_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"))
    scene_index: Mapped[int] = mapped_column(Integer)
    subtitle: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(40))
    motion_type: Mapped[str] = mapped_column(String(40))
    duration_ms: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped[VideoProject] = relationship(back_populates="scenes")


class RenderOutput(Base):
    __tablename__ = "render_outputs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"))
    mp4_path: Mapped[str] = mapped_column(String(500))
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    upload_title: Mapped[str] = mapped_column(String(120))
    upload_description: Mapped[str] = mapped_column(Text)
    hashtags: Mapped[list[str]] = mapped_column(JSON, default=list)


class PerformanceSnapshot(Base):
    __tablename__ = "performance_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    minutes_since_upload: Mapped[int] = mapped_column(Integer)
    views: Mapped[int] = mapped_column(Integer, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(default=0.0)
    avg_view_duration_sec: Mapped[float] = mapped_column(default=0.0)
    retention_3s: Mapped[float] = mapped_column(default=0.0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    subscribers_gained: Mapped[int] = mapped_column(Integer, default=0)


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    cause_candidates: Mapped[list[dict]] = mapped_column(JSON, default=list)
    next_experiments: Mapped[list[str]] = mapped_column(JSON, default=list)


class LearningMemory(Base):
    __tablename__ = "learning_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(80))
    pattern_type: Mapped[str] = mapped_column(String(80))
    pattern: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(default=0.0)
    approved: Mapped[bool] = mapped_column(default=False)
```

## Required Schemas And Repository

Implement `shorts_growth_agent/backend/src/shorts_agent/schemas.py`.

```python
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    title: str
    category: str
    selected_keyword: str | None = None


class ProjectRead(BaseModel):
    id: int
    title: str
    category: str
    selected_keyword: str | None
    status: str

    model_config = {"from_attributes": True}
```

Implement `shorts_growth_agent/backend/src/shorts_agent/repositories/project_repository.py`.

```python
from sqlalchemy.orm import Session

from shorts_agent.models import VideoProject


class ProjectRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_project(self, title: str, category: str, selected_keyword: str | None = None) -> VideoProject:
        project = VideoProject(title=title, category=category, selected_keyword=selected_keyword)
        self.session.add(project)
        self.session.commit()
        self.session.refresh(project)
        return project

    def get_project(self, project_id: int) -> VideoProject | None:
        return self.session.get(VideoProject, project_id)
```

## Verification

1. Run `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_models.py -q` after writing tests and before implementation. It must fail because the data layer is missing.
2. Run the same command after implementation. It must pass with clean output.
3. Run `.\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py -q`. It must pass with clean output.

## Report Contract

Write the full report to `.superpowers/sdd/task-2-report.md`.

Return only this summary to the parent.

- Status: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`.
- Files changed.
- Red test result.
- Green test result.
- Concerns.
