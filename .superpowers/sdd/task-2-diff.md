diff --git a/shorts_growth_agent/backend/src/shorts_agent/db.py b/shorts_growth_agent/backend/src/shorts_agent/db.py
new file mode 100644
index 00000000..3216417c
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/db.py
@@ -0,0 +1,26 @@
+# 데이터베이스 엔진 생성 및 초기화 설정을 관리하는 모듈입니다.
+from sqlalchemy import create_engine
+from sqlalchemy.engine import Engine
+from sqlalchemy.orm import DeclarativeBase, sessionmaker
+
+from shorts_agent.config import get_settings
+
+
+class Base(DeclarativeBase):
+    pass
+
+
+def make_engine(database_url: str | None = None) -> Engine:
+    url = database_url or get_settings().database_url
+    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
+    return create_engine(url, connect_args=connect_args, future=True)
+
+
+def init_db(engine: Engine) -> None:
+    from shorts_agent import models  # noqa: F401
+
+    Base.metadata.create_all(bind=engine)
+
+
+def make_session_factory(engine: Engine):
+    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
diff --git a/shorts_growth_agent/backend/src/shorts_agent/models.py b/shorts_growth_agent/backend/src/shorts_agent/models.py
new file mode 100644
index 00000000..7da373b6
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/models.py
@@ -0,0 +1,112 @@
+# SQLAlchemy ORM 모델을 통해 Shorts Growth Agent의 데이터 스키마를 정의합니다.
+from datetime import UTC, datetime
+from enum import StrEnum
+
+from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
+from sqlalchemy.orm import Mapped, mapped_column, relationship
+
+from shorts_agent.db import Base
+
+
+def _utc_now() -> datetime:
+    return datetime.now(UTC).replace(tzinfo=None)
+
+
+class ProjectStatus(StrEnum):
+    DRAFT = "draft"
+    RENDERED = "rendered"
+    UPLOADED = "uploaded"
+    ARCHIVED = "archived"
+
+
+class VideoProject(Base):
+    __tablename__ = "video_projects"
+
+    id: Mapped[int] = mapped_column(Integer, primary_key=True)
+    title: Mapped[str] = mapped_column(String(200))
+    category: Mapped[str] = mapped_column(String(80))
+    selected_keyword: Mapped[str | None] = mapped_column(String(160), nullable=True)
+    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus), default=ProjectStatus.DRAFT)
+    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
+    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
+
+    scenes: Mapped[list["SceneAsset"]] = relationship(
+        back_populates="project", cascade="all, delete-orphan"
+    )
+
+
+class ScriptHarness(Base):
+    __tablename__ = "script_harnesses"
+
+    id: Mapped[int] = mapped_column(Integer, primary_key=True)
+    name: Mapped[str] = mapped_column(String(120))
+    mode: Mapped[str] = mapped_column(String(40))
+    system_prompt: Mapped[str] = mapped_column(Text)
+    output_schema: Mapped[dict] = mapped_column(JSON)
+    forbidden_terms: Mapped[list[str]] = mapped_column(JSON, default=list)
+    version: Mapped[int] = mapped_column(Integer, default=1)
+
+
+class SceneAsset(Base):
+    __tablename__ = "scene_assets"
+
+    id: Mapped[int] = mapped_column(Integer, primary_key=True)
+    project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"))
+    scene_index: Mapped[int] = mapped_column(Integer)
+    subtitle: Mapped[str] = mapped_column(Text)
+    source_type: Mapped[str] = mapped_column(String(40))
+    motion_type: Mapped[str] = mapped_column(String(40))
+    duration_ms: Mapped[int] = mapped_column(Integer)
+    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
+
+    project: Mapped[VideoProject] = relationship(back_populates="scenes")
+
+
+class RenderOutput(Base):
+    __tablename__ = "render_outputs"
+
+    id: Mapped[int] = mapped_column(Integer, primary_key=True)
+    project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"))
+    mp4_path: Mapped[str] = mapped_column(String(500))
+    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
+    upload_title: Mapped[str] = mapped_column(String(120))
+    upload_description: Mapped[str] = mapped_column(Text)
+    hashtags: Mapped[list[str]] = mapped_column(JSON, default=list)
+
+
+class PerformanceSnapshot(Base):
+    __tablename__ = "performance_snapshots"
+
+    id: Mapped[int] = mapped_column(Integer, primary_key=True)
+    project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"))
+    captured_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
+    minutes_since_upload: Mapped[int] = mapped_column(Integer)
+    views: Mapped[int] = mapped_column(Integer, default=0)
+    impressions: Mapped[int] = mapped_column(Integer, default=0)
+    ctr: Mapped[float] = mapped_column(default=0.0)
+    avg_view_duration_sec: Mapped[float] = mapped_column(default=0.0)
+    retention_3s: Mapped[float] = mapped_column(default=0.0)
+    likes: Mapped[int] = mapped_column(Integer, default=0)
+    comments: Mapped[int] = mapped_column(Integer, default=0)
+    subscribers_gained: Mapped[int] = mapped_column(Integer, default=0)
+
+
+class AnalysisReport(Base):
+    __tablename__ = "analysis_reports"
+
+    id: Mapped[int] = mapped_column(Integer, primary_key=True)
+    project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id"))
+    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
+    cause_candidates: Mapped[list[dict]] = mapped_column(JSON, default=list)
+    next_experiments: Mapped[list[str]] = mapped_column(JSON, default=list)
+
+
+class LearningMemory(Base):
+    __tablename__ = "learning_memories"
+
+    id: Mapped[int] = mapped_column(Integer, primary_key=True)
+    category: Mapped[str] = mapped_column(String(80))
+    pattern_type: Mapped[str] = mapped_column(String(80))
+    pattern: Mapped[dict] = mapped_column(JSON)
+    confidence: Mapped[float] = mapped_column(default=0.0)
+    approved: Mapped[bool] = mapped_column(default=False)
diff --git a/shorts_growth_agent/backend/src/shorts_agent/repositories/__init__.py b/shorts_growth_agent/backend/src/shorts_agent/repositories/__init__.py
new file mode 100644
index 00000000..605c9c62
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/repositories/__init__.py
@@ -0,0 +1 @@
+# 프로젝트 데이터 접근 계층 패키지 초기화 파일입니다.
diff --git a/shorts_growth_agent/backend/src/shorts_agent/repositories/project_repository.py b/shorts_growth_agent/backend/src/shorts_agent/repositories/project_repository.py
new file mode 100644
index 00000000..d0128d3f
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/repositories/project_repository.py
@@ -0,0 +1,23 @@
+# 프로젝트 생성/조회 기능을 담당하는 리포지토리입니다.
+from sqlalchemy.orm import Session
+
+from shorts_agent.models import VideoProject
+
+
+class ProjectRepository:
+    def __init__(self, session: Session):
+        self.session = session
+
+    def create_project(
+        self, title: str, category: str, selected_keyword: str | None = None
+    ) -> VideoProject:
+        project = VideoProject(
+            title=title, category=category, selected_keyword=selected_keyword
+        )
+        self.session.add(project)
+        self.session.commit()
+        self.session.refresh(project)
+        return project
+
+    def get_project(self, project_id: int) -> VideoProject | None:
+        return self.session.get(VideoProject, project_id)
diff --git a/shorts_growth_agent/backend/src/shorts_agent/schemas.py b/shorts_growth_agent/backend/src/shorts_agent/schemas.py
new file mode 100644
index 00000000..7d75f501
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/schemas.py
@@ -0,0 +1,18 @@
+# API 입출력을 위한 pydantic 스키마를 제공합니다.
+from pydantic import BaseModel
+
+
+class ProjectCreate(BaseModel):
+    title: str
+    category: str
+    selected_keyword: str | None = None
+
+
+class ProjectRead(BaseModel):
+    id: int
+    title: str
+    category: str
+    selected_keyword: str | None
+    status: str
+
+    model_config = {"from_attributes": True}
diff --git a/shorts_growth_agent/backend/tests/test_models.py b/shorts_growth_agent/backend/tests/test_models.py
new file mode 100644
index 00000000..f81ac563
--- /dev/null
+++ b/shorts_growth_agent/backend/tests/test_models.py
@@ -0,0 +1,52 @@
+# 프로젝트 데이터 모델과 리포지토리의 기본 동작을 검증합니다.
+from sqlalchemy import create_engine, inspect
+from sqlalchemy.orm import sessionmaker
+
+from shorts_agent.db import init_db
+from shorts_agent.models import ProjectStatus
+from shorts_agent.repositories.project_repository import ProjectRepository
+
+
+def test_create_project_sets_default_status():
+    engine = create_engine("sqlite:///:memory:", future=True)
+    init_db(engine)
+    Session = sessionmaker(bind=engine)
+
+    with Session() as session:
+        repo = ProjectRepository(session)
+        project = repo.create_project(title="테스트 프로젝트", category="일반")
+
+        assert project.id is not None
+        assert project.status == ProjectStatus.DRAFT
+        assert project.category == "일반"
+
+
+def test_get_project_returns_saved_project():
+    engine = create_engine("sqlite:///:memory:", future=True)
+    init_db(engine)
+    Session = sessionmaker(bind=engine)
+
+    with Session() as session:
+        repo = ProjectRepository(session)
+        created = repo.create_project(title="샘플 제목", category="샘플")
+        found = repo.get_project(created.id)
+
+        assert found is not None
+        assert found.title == "샘플 제목"
+
+
+def test_init_db_creates_required_tables():
+    engine = create_engine("sqlite:///:memory:", future=True)
+    init_db(engine)
+
+    table_names = set(inspect(engine).get_table_names())
+
+    assert {
+        "video_projects",
+        "script_harnesses",
+        "scene_assets",
+        "render_outputs",
+        "performance_snapshots",
+        "analysis_reports",
+        "learning_memories",
+    }.issubset(table_names)
