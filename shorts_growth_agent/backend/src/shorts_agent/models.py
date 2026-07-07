# SQLAlchemy ORM 모델을 통해 Shorts Growth Agent의 데이터 스키마를 정의합니다.
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shorts_agent.db import Base


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)

    scenes: Mapped[list["SceneAsset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


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
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utc_now)
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
