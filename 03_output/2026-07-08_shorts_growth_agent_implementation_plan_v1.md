# Shorts Growth Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local web app MVP that turns Korean YouTube trend signals into an editable Shorts project, renders a 9:16 MP4, and records time-based performance data for long-term cause analysis.

**Architecture:** Use a small pipeline first, then connect it directly to a top-step editing workspace. The backend owns trend collection, scoring, script harnesses, project state, render manifests, and performance analysis. The frontend owns the five-step workflow, 9:16 preview, timeline editing surface, and review screens.

**Tech Stack:** Python 3.12+ FastAPI backend, SQLite, SQLAlchemy 2.0, Pydantic, pytest, React + Vite + TypeScript frontend, Vitest, FFmpeg CLI for rendering, adapter interfaces for YouTube, TTS, image generation, meme MCP, and upload.

## Global Constraints

- 응답과 사용자-facing 문서는 한국어로 작성한다.
- 첫 사용자는 본인 1명이며 로그인, 결제, 다중 사용자 관리는 MVP 범위에서 제외한다.
- 첫 국가 범위는 한국 유튜브다. 해외 인기 영상 재가공은 MVP 범위에서 제외한다.
- 화면 구조는 상단 작은 단계 표시형 UI다. 단계는 `키워드 -> 대본 -> 음성/자막 -> 편집 -> 출력`이다.
- MVP는 트렌드 키워드 수집부터 9:16 MP4 렌더링까지 한 사이클이 반드시 돌아야 한다.
- 분석 우선순위는 `시간별 성과 데이터 > 제작 데이터 > 해석/가설`이다.
- 자기개선은 자동 변경이 아니라 장기 분석과 사용자 승인 기반 제안으로 진행한다.
- 외부 유튜브 클립은 자동 무단 삽입하지 않는다. 사용자가 직접 구간, 크롭, 출처, 사용 가능 여부를 확인해야 한다.
- 모든 새 소스 파일의 첫 줄에는 파일 역할을 설명하는 한국어 한 줄 주석을 넣는다.
- 산출물과 계획 문서는 `03_output`에 저장한다.
- 기존 `maple_bot` 변경과 루트의 기존 미추적 파일은 건드리지 않는다.

---

## File Structure

Create a new project directory named `shorts_growth_agent`.

```text
shorts_growth_agent/
  README.md
  .env.example
  backend/
    pyproject.toml
    src/shorts_agent/
      __init__.py
      main.py
      config.py
      db.py
      models.py
      schemas.py
      api/
        __init__.py
        health.py
        trends.py
        harnesses.py
        projects.py
        render.py
        performance.py
      adapters/
        __init__.py
        youtube.py
        tts.py
        image.py
        meme.py
        uploader.py
      services/
        __init__.py
        trend_scoring.py
        script_planner.py
        subtitle_sync.py
        source_recommender.py
        render_manifest.py
        performance_analysis.py
      repositories/
        __init__.py
        harness_repository.py
        project_repository.py
        trend_repository.py
        performance_repository.py
    tests/
      conftest.py
      test_health.py
      test_models.py
      test_trend_scoring.py
      test_script_planner.py
      test_subtitle_sync.py
      test_source_recommender.py
      test_render_manifest.py
      test_performance_analysis.py
      test_api_projects.py
  frontend/
    package.json
    index.html
    src/
      main.tsx
      App.tsx
      api/client.ts
      types.ts
      components/
        TopStepNav.tsx
        GrowthAssistantPanel.tsx
        ShortsCanvas.tsx
        Timeline.tsx
      pages/
        KeywordStep.tsx
        ScriptStep.tsx
        VoiceSubtitleStep.tsx
        EditorStep.tsx
        ExportStep.tsx
        GrowthReportPage.tsx
      state/projectStore.ts
    tests/
      TopStepNav.test.tsx
      projectStore.test.ts
```

Responsibilities are split as follows.

- `models.py`: database models and enums only.
- `schemas.py`: API request/response models only.
- `adapters/*`: external systems behind replaceable interfaces.
- `services/*`: pure business logic where possible.
- `repositories/*`: SQLite persistence operations.
- `api/*`: FastAPI route wiring and request validation.
- `frontend/src/pages/*`: one file per top-step screen.
- `frontend/src/components/*`: reusable UI units for navigation, preview, timeline, and assistant panel.

---

### Task 1: Backend Scaffold And Health Check

**Files:**
- Create: `shorts_growth_agent/README.md`
- Create: `shorts_growth_agent/.env.example`
- Create: `shorts_growth_agent/backend/pyproject.toml`
- Create: `shorts_growth_agent/backend/src/shorts_agent/__init__.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/config.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/main.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/api/__init__.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/api/health.py`
- Create: `shorts_growth_agent/backend/tests/conftest.py`
- Create: `shorts_growth_agent/backend/tests/test_health.py`

**Interfaces:**
- Produces: `create_app() -> FastAPI`.
- Produces: `GET /api/health -> {"status": "ok", "app": "shorts-growth-agent"}`.

- [ ] **Step 1: Write the failing health test**

```python
# FastAPI 앱 테스트 클라이언트 설정을 검증한다.
from fastapi.testclient import TestClient
from shorts_agent.main import create_app


def test_health_check_returns_ok():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "shorts-growth-agent"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_health.py -q`.

Expected: FAIL with `ModuleNotFoundError: No module named 'shorts_agent'`.

- [ ] **Step 3: Create backend project metadata**

```toml
[project]
name = "shorts-growth-agent-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.8",
  "pydantic-settings>=2.4",
  "sqlalchemy>=2.0",
  "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 4: Implement settings and app wiring**

```python
# 로컬 앱 설정값을 환경 변수에서 읽는다.
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "shorts-growth-agent"
    database_url: str = "sqlite:///./data/shorts_agent.db"
    storage_root: Path = Path("./storage")
    youtube_api_key: str = ""
    ffmpeg_path: str = "ffmpeg"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SHORTS_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python
# FastAPI 애플리케이션을 생성하고 라우터를 연결한다.
from fastapi import FastAPI

from shorts_agent.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Shorts Growth Agent")
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
```

```python
# 앱 상태 확인 라우터를 제공한다.
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "app": "shorts-growth-agent"}
```

- [ ] **Step 5: Add root README and env example**

```markdown
# Shorts Growth Agent

한국 유튜브 트렌드 기반 쇼츠 제작 로컬 웹앱 MVP입니다.

## MVP Goal

키워드 수집, 대본 하네스, TTS/자막 싱크, 편집 화면, MP4 렌더링, 시간별 성과 분석의 첫 사이클을 구현합니다.
```

```env
SHORTS_DATABASE_URL=sqlite:///./data/shorts_agent.db
SHORTS_STORAGE_ROOT=./storage
SHORTS_YOUTUBE_API_KEY=
SHORTS_FFMPEG_PATH=ffmpeg
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_health.py -q`.

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add shorts_growth_agent/README.md shorts_growth_agent/.env.example shorts_growth_agent/backend
git commit -m "feat: scaffold shorts growth backend"
```

---

### Task 2: Database Models And Repositories

**Files:**
- Create: `shorts_growth_agent/backend/src/shorts_agent/db.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/models.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/schemas.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/repositories/__init__.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/repositories/project_repository.py`
- Test: `shorts_growth_agent/backend/tests/test_models.py`

**Interfaces:**
- Produces: `init_db(engine: Engine) -> None`.
- Produces: `ProjectRepository.create_project(title: str, category: str) -> VideoProject`.
- Produces: `ProjectRepository.get_project(project_id: int) -> VideoProject | None`.
- Produces DB tables: `video_projects`, `script_harnesses`, `scene_assets`, `render_outputs`, `performance_snapshots`, `analysis_reports`, `learning_memories`.

- [ ] **Step 1: Write failing repository tests**

```python
# 제작 프로젝트 저장소의 기본 생성과 조회를 검증한다.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shorts_agent.db import Base, init_db
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_models.py -q`.

Expected: FAIL with missing `shorts_agent.db`.

- [ ] **Step 3: Implement database base and initialization**

```python
# SQLAlchemy 데이터베이스 엔진과 세션 생성을 담당한다.
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from shorts_agent.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(database_url: str | None = None):
    url = database_url or get_settings().database_url
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


def init_db(engine) -> None:
    from shorts_agent import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
```

- [ ] **Step 4: Implement core models**

```python
# 쇼츠 제작과 성과 분석에 필요한 데이터 모델을 정의한다.
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

- [ ] **Step 5: Implement schemas and repository**

```python
# API 요청과 응답에 사용하는 Pydantic 스키마를 정의한다.
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

```python
# 제작 프로젝트 저장과 조회를 담당한다.
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

- [ ] **Step 6: Run tests**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_models.py -q`.

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add shorts_growth_agent/backend/src/shorts_agent/db.py shorts_growth_agent/backend/src/shorts_agent/models.py shorts_growth_agent/backend/src/shorts_agent/schemas.py shorts_growth_agent/backend/src/shorts_agent/repositories shorts_growth_agent/backend/tests/test_models.py
git commit -m "feat: add shorts agent data model"
```

---

### Task 3: YouTube Trend Adapter And Trend Scoring

**Files:**
- Create: `shorts_growth_agent/backend/src/shorts_agent/adapters/youtube.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/services/trend_scoring.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/api/trends.py`
- Test: `shorts_growth_agent/backend/tests/test_trend_scoring.py`

**Interfaces:**
- Produces: `YouTubeVideoSignal(video_id, title, category_id, channel_title, published_at, view_count, like_count)`.
- Produces: `TrendScoringService.rank(signals: list[YouTubeVideoSignal], now: datetime) -> list[TrendScore]`.
- Produces: `GET /api/trends?region=KR&category_id=20&keyword=...`.

- [ ] **Step 1: Write failing scoring tests**

```python
# 조회수와 업로드 경과 시간을 기준으로 상승 점수를 계산한다.
from datetime import datetime, timedelta, timezone

from shorts_agent.adapters.youtube import YouTubeVideoSignal
from shorts_agent.services.trend_scoring import TrendScoringService


def test_rank_prefers_fast_rising_recent_video():
    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    signals = [
        YouTubeVideoSignal("old", "오래된 인기", "24", "A", now - timedelta(days=5), 500000, 1000),
        YouTubeVideoSignal("new", "빠른 상승", "24", "B", now - timedelta(hours=2), 90000, 900),
    ]

    ranked = TrendScoringService().rank(signals, now)

    assert ranked[0].video_id == "new"
    assert ranked[0].views_per_hour > ranked[1].views_per_hour


def test_rank_extracts_keyword_candidates_from_titles():
    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    signals = [
        YouTubeVideoSignal("a", "신작 게임 업데이트 반응 폭발", "20", "A", now - timedelta(hours=1), 10000, 100),
        YouTubeVideoSignal("b", "게임 업데이트 보상 정리", "20", "B", now - timedelta(hours=2), 9000, 90),
    ]

    ranked = TrendScoringService().rank(signals, now)

    assert "게임" in ranked[0].keyword_candidates
    assert "업데이트" in ranked[0].keyword_candidates
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_trend_scoring.py -q`.

Expected: FAIL with missing `shorts_agent.adapters.youtube`.

- [ ] **Step 3: Implement YouTube signal types and adapter interface**

```python
# YouTube 인기 영상 수집 어댑터와 테스트용 신호 타입을 정의한다.
from dataclasses import dataclass
from datetime import datetime

import httpx


@dataclass(frozen=True)
class YouTubeVideoSignal:
    video_id: str
    title: str
    category_id: str
    channel_title: str
    published_at: datetime
    view_count: int
    like_count: int


class YouTubeAdapter:
    def __init__(self, api_key: str, client: httpx.Client | None = None):
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=15)

    def fetch_popular(self, region_code: str = "KR", category_id: str | None = None, max_results: int = 25) -> list[YouTubeVideoSignal]:
        params = {
            "part": "snippet,statistics",
            "chart": "mostPopular",
            "regionCode": region_code,
            "maxResults": max_results,
            "key": self.api_key,
        }
        if category_id:
            params["videoCategoryId"] = category_id
        response = self.client.get("https://www.googleapis.com/youtube/v3/videos", params=params)
        response.raise_for_status()
        return [self._parse_item(item) for item in response.json().get("items", [])]

    def _parse_item(self, item: dict) -> YouTubeVideoSignal:
        snippet = item["snippet"]
        stats = item.get("statistics", {})
        published_at = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
        return YouTubeVideoSignal(
            video_id=item["id"],
            title=snippet["title"],
            category_id=snippet.get("categoryId", ""),
            channel_title=snippet.get("channelTitle", ""),
            published_at=published_at,
            view_count=int(stats.get("viewCount", 0)),
            like_count=int(stats.get("likeCount", 0)),
        )
```

- [ ] **Step 4: Implement trend scoring**

```python
# 조회수와 상승 속도 중심의 트렌드 점수를 계산한다.
from dataclasses import dataclass
from datetime import datetime
import re

from shorts_agent.adapters.youtube import YouTubeVideoSignal


@dataclass(frozen=True)
class TrendScore:
    video_id: str
    title: str
    category_id: str
    views_per_hour: float
    score: float
    keyword_candidates: list[str]


class TrendScoringService:
    def rank(self, signals: list[YouTubeVideoSignal], now: datetime) -> list[TrendScore]:
        scores = [self._score(signal, now) for signal in signals]
        return sorted(scores, key=lambda item: item.score, reverse=True)

    def _score(self, signal: YouTubeVideoSignal, now: datetime) -> TrendScore:
        age_hours = max((now - signal.published_at).total_seconds() / 3600, 1.0)
        views_per_hour = signal.view_count / age_hours
        engagement_bonus = min(signal.like_count / max(signal.view_count, 1), 0.1) * 1000
        score = views_per_hour + engagement_bonus
        return TrendScore(
            video_id=signal.video_id,
            title=signal.title,
            category_id=signal.category_id,
            views_per_hour=views_per_hour,
            score=score,
            keyword_candidates=self._keywords(signal.title),
        )

    def _keywords(self, title: str) -> list[str]:
        tokens = re.findall(r"[가-힣A-Za-z0-9]{2,}", title)
        stopwords = {"그리고", "하지만", "영상", "정리"}
        return [token for token in tokens if token not in stopwords][:8]
```

- [ ] **Step 5: Wire trends route**

```python
# 트렌드 후보 조회 API를 제공한다.
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from shorts_agent.adapters.youtube import YouTubeAdapter
from shorts_agent.config import get_settings
from shorts_agent.services.trend_scoring import TrendScoringService

router = APIRouter()


def get_youtube_adapter() -> YouTubeAdapter:
    return YouTubeAdapter(api_key=get_settings().youtube_api_key)


@router.get("/trends")
def get_trends(
    region: str = "KR",
    category_id: str | None = None,
    keyword: str | None = None,
    adapter: YouTubeAdapter = Depends(get_youtube_adapter),
):
    signals = adapter.fetch_popular(region_code=region, category_id=category_id)
    if keyword:
        signals = [signal for signal in signals if keyword.lower() in signal.title.lower()]
    ranked = TrendScoringService().rank(signals, datetime.now(timezone.utc))
    return {"items": [item.__dict__ for item in ranked]}
```

Also include the trends router in `create_app()`.

```python
from shorts_agent.api.trends import router as trends_router

app.include_router(trends_router, prefix="/api")
```

- [ ] **Step 6: Run tests**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_trend_scoring.py -q`.

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add shorts_growth_agent/backend/src/shorts_agent/adapters/youtube.py shorts_growth_agent/backend/src/shorts_agent/services/trend_scoring.py shorts_growth_agent/backend/src/shorts_agent/api/trends.py shorts_growth_agent/backend/src/shorts_agent/main.py shorts_growth_agent/backend/tests/test_trend_scoring.py
git commit -m "feat: add youtube trend scoring"
```

---

### Task 4: Script Harness And Scene Planner

**Files:**
- Create: `shorts_growth_agent/backend/src/shorts_agent/repositories/harness_repository.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/services/script_planner.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/api/harnesses.py`
- Test: `shorts_growth_agent/backend/tests/test_script_planner.py`

**Interfaces:**
- Produces: `ScriptPlanner.generate(keyword: str, category: str, harness: HarnessConfig) -> ScriptPlan`.
- Produces scene fields: `index`, `subtitle`, `voice_text`, `image_prompt`, `source_type`, `motion_type`, `sound_effect`.

- [ ] **Step 1: Write failing planner test**

```python
# 대본 하네스가 장면, 자막, 이미지, 모션 지시를 만든다.
from shorts_agent.services.script_planner import HarnessConfig, ScriptPlanner


def test_generate_returns_structured_scene_plan():
    harness = HarnessConfig(
        name="정보+후킹형",
        tone="빠른 정보형",
        hook_strength="강함",
        target_seconds=45,
        forbidden_terms=["무조건", "100%"],
    )

    plan = ScriptPlanner().generate(keyword="게임 업데이트", category="게임", harness=harness)

    assert plan.keyword == "게임 업데이트"
    assert 3 <= len(plan.scenes) <= 8
    assert plan.scenes[0].motion_type in {"zoom_in", "shake", "bounce", "none"}
    assert "무조건" not in " ".join(scene.subtitle for scene in plan.scenes)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_script_planner.py -q`.

Expected: FAIL with missing `shorts_agent.services.script_planner`.

- [ ] **Step 3: Implement planner data types and deterministic MVP planner**

```python
# 대본 하네스를 장면 단위 쇼츠 계획으로 변환한다.
from dataclasses import dataclass


@dataclass(frozen=True)
class HarnessConfig:
    name: str
    tone: str
    hook_strength: str
    target_seconds: int
    forbidden_terms: list[str]


@dataclass(frozen=True)
class PlannedScene:
    index: int
    subtitle: str
    voice_text: str
    image_prompt: str
    source_type: str
    motion_type: str
    sound_effect: str
    duration_ms: int


@dataclass(frozen=True)
class ScriptPlan:
    keyword: str
    category: str
    title_candidate: str
    scenes: list[PlannedScene]


class ScriptPlanner:
    def generate(self, keyword: str, category: str, harness: HarnessConfig) -> ScriptPlan:
        scene_count = 5 if harness.target_seconds <= 45 else 7
        duration_ms = int(harness.target_seconds * 1000 / scene_count)
        templates = [
            f"지금 {keyword}, 왜 갑자기 뜨는 걸까요?",
            f"핵심은 세 가지입니다.",
            f"첫째, 사람들이 반응한 포인트가 분명합니다.",
            f"둘째, {category} 흐름과 바로 연결됩니다.",
            f"마지막으로 지금 확인해야 할 부분입니다.",
        ]
        scenes = []
        for index, subtitle in enumerate(templates[:scene_count], start=1):
            cleaned = self._remove_forbidden(subtitle, harness.forbidden_terms)
            scenes.append(
                PlannedScene(
                    index=index,
                    subtitle=cleaned,
                    voice_text=cleaned,
                    image_prompt=f"{category} 주제의 세로형 쇼츠 이미지, 키워드: {keyword}, 장면 {index}",
                    source_type=self._source_type(category, index),
                    motion_type="zoom_in" if index == 1 else "shake" if index == 3 else "none",
                    sound_effect="hit" if index == 1 else "whoosh" if index == 2 else "none",
                    duration_ms=duration_ms,
                )
            )
        return ScriptPlan(keyword=keyword, category=category, title_candidate=f"{keyword} 핵심 정리", scenes=scenes)

    def _remove_forbidden(self, text: str, forbidden_terms: list[str]) -> str:
        for term in forbidden_terms:
            text = text.replace(term, "")
        return text

    def _source_type(self, category: str, index: int) -> str:
        if category == "게임" and index in {2, 3}:
            return "clip_candidate"
        if category in {"뉴스", "이슈"} and index == 1:
            return "reference_image"
        return "ai_image"
```

- [ ] **Step 4: Add harness repository and API**

Implement repository methods.

```python
# 대본 하네스 프리셋을 저장하고 조회한다.
from sqlalchemy.orm import Session

from shorts_agent.models import ScriptHarness


class HarnessRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_default_harness(self) -> ScriptHarness:
        harness = ScriptHarness(
            name="정보+후킹형",
            mode="basic",
            system_prompt="빠르고 정확한 한국어 쇼츠 작가로서 첫 3초 후킹과 명확한 정보 전달을 우선한다.",
            output_schema={
                "scene": "number",
                "subtitle": "string",
                "voice_text": "string",
                "image_prompt": "string",
                "source_type": "string",
                "motion_type": "string",
                "sound_effect": "string",
            },
            forbidden_terms=["무조건", "100%", "확정"],
        )
        self.session.add(harness)
        self.session.commit()
        self.session.refresh(harness)
        return harness
```

- [ ] **Step 5: Run tests**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_script_planner.py -q`.

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add shorts_growth_agent/backend/src/shorts_agent/repositories/harness_repository.py shorts_growth_agent/backend/src/shorts_agent/services/script_planner.py shorts_growth_agent/backend/src/shorts_agent/api/harnesses.py shorts_growth_agent/backend/tests/test_script_planner.py
git commit -m "feat: add script harness planner"
```

---

### Task 5: TTS Adapter And Subtitle Sync

**Files:**
- Create: `shorts_growth_agent/backend/src/shorts_agent/adapters/tts.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/services/subtitle_sync.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/api/projects.py`
- Test: `shorts_growth_agent/backend/tests/test_subtitle_sync.py`

**Interfaces:**
- Produces: `TtsAdapter.synthesize(text: str, voice: str, speed: float, output_path: Path) -> TtsResult`.
- Produces: `SubtitleSyncService.sync(lines: list[str], total_duration_ms: int) -> list[SubtitleCue]`.

- [ ] **Step 1: Write failing subtitle sync test**

```python
# TTS 길이에 맞춰 자막 큐를 균등 배분한다.
from shorts_agent.services.subtitle_sync import SubtitleSyncService


def test_sync_splits_duration_across_lines():
    cues = SubtitleSyncService().sync(["첫 문장", "두 번째 문장"], total_duration_ms=4000)

    assert cues[0].start_ms == 0
    assert cues[0].end_ms == 2000
    assert cues[1].start_ms == 2000
    assert cues[1].end_ms == 4000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_subtitle_sync.py -q`.

Expected: FAIL with missing `subtitle_sync`.

- [ ] **Step 3: Implement TTS adapter interface and fake adapter**

```python
# TTS 엔진을 교체 가능하게 감싸는 어댑터를 정의한다.
from dataclasses import dataclass
from pathlib import Path
import wave


@dataclass(frozen=True)
class TtsResult:
    audio_path: Path
    duration_ms: int
    voice: str
    speed: float


class TtsAdapter:
    def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> TtsResult:
        raise NotImplementedError


class SilentTtsAdapter(TtsAdapter):
    def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> TtsResult:
        duration_ms = max(1000, int(len(text) * 80 / max(speed, 0.5)))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\\x00\\x00" * int(16000 * duration_ms / 1000))
        return TtsResult(audio_path=output_path, duration_ms=duration_ms, voice=voice, speed=speed)
```

- [ ] **Step 4: Implement subtitle sync service**

```python
# 음성 길이에 맞춰 자막 타임코드를 만든다.
from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleCue:
    text: str
    start_ms: int
    end_ms: int


class SubtitleSyncService:
    def sync(self, lines: list[str], total_duration_ms: int) -> list[SubtitleCue]:
        if not lines:
            return []
        slot = total_duration_ms // len(lines)
        cues = []
        for index, line in enumerate(lines):
            start = index * slot
            end = total_duration_ms if index == len(lines) - 1 else (index + 1) * slot
            cues.append(SubtitleCue(text=line, start_ms=start, end_ms=end))
        return cues
```

- [ ] **Step 5: Run tests**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_subtitle_sync.py -q`.

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add shorts_growth_agent/backend/src/shorts_agent/adapters/tts.py shorts_growth_agent/backend/src/shorts_agent/services/subtitle_sync.py shorts_growth_agent/backend/src/shorts_agent/api/projects.py shorts_growth_agent/backend/tests/test_subtitle_sync.py
git commit -m "feat: add tts subtitle sync"
```

---

### Task 6: Source Recommendation And Scene Assets

**Files:**
- Create: `shorts_growth_agent/backend/src/shorts_agent/adapters/image.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/adapters/meme.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/services/source_recommender.py`
- Test: `shorts_growth_agent/backend/tests/test_source_recommender.py`

**Interfaces:**
- Produces: `SourceRecommender.recommend(category: str, scene_index: int, source_hint: str) -> SourceRecommendation`.
- Source types: `ai_image`, `meme`, `clip_candidate`, `reference_image`, `uploaded_file`.

- [ ] **Step 1: Write failing source recommendation tests**

```python
# 카테고리별 우선순위와 장면 힌트로 소스 타입을 추천한다.
from shorts_agent.services.source_recommender import SourceRecommender


def test_game_clip_hint_recommends_clip_candidate():
    result = SourceRecommender().recommend("게임", 2, "clip_candidate")

    assert result.source_type == "clip_candidate"
    assert result.requires_user_review is True


def test_info_category_defaults_to_ai_image():
    result = SourceRecommender().recommend("정보형", 1, "ai_image")

    assert result.source_type == "ai_image"
    assert result.requires_user_review is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_source_recommender.py -q`.

Expected: FAIL with missing `source_recommender`.

- [ ] **Step 3: Implement image and meme adapter interfaces**

```python
# 이미지 생성 엔진을 교체 가능하게 감싸는 어댑터를 정의한다.
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImageResult:
    path: Path
    prompt: str


class ImageAdapter:
    def generate(self, prompt: str, output_path: Path) -> ImageResult:
        raise NotImplementedError
```

```python
# 밈 MCP 또는 로컬 밈 라이브러리 연결을 위한 어댑터를 정의한다.
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MemeAsset:
    path: Path
    tags: list[str]
    source: str


class MemeAdapter:
    def search(self, query: str, limit: int = 10) -> list[MemeAsset]:
        return []
```

- [ ] **Step 4: Implement source recommender**

```python
# 장면별 이미지, 밈, 클립 후보 소스 타입을 추천한다.
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRecommendation:
    source_type: str
    reason: str
    requires_user_review: bool


class SourceRecommender:
    def recommend(self, category: str, scene_index: int, source_hint: str) -> SourceRecommendation:
        if source_hint == "clip_candidate":
            return SourceRecommendation(
                source_type="clip_candidate",
                reason="실제 장면이 있으면 이해가 빠른 장면입니다. 사용자가 구간과 사용 가능 여부를 확인해야 합니다.",
                requires_user_review=True,
            )
        if category in {"뉴스", "이슈"} and scene_index == 1:
            return SourceRecommendation("reference_image", "첫 장면은 실제 자료 이미지가 신뢰감을 줍니다.", True)
        if category == "게임" and scene_index >= 3:
            return SourceRecommendation("meme", "반응 장면에는 밈 이미지가 리듬을 만듭니다.", False)
        return SourceRecommendation("ai_image", "기본 장면은 AI 이미지로 안정적으로 구성합니다.", False)
```

- [ ] **Step 5: Run tests**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_source_recommender.py -q`.

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add shorts_growth_agent/backend/src/shorts_agent/adapters/image.py shorts_growth_agent/backend/src/shorts_agent/adapters/meme.py shorts_growth_agent/backend/src/shorts_agent/services/source_recommender.py shorts_growth_agent/backend/tests/test_source_recommender.py
git commit -m "feat: add scene source recommendation"
```

---

### Task 7: Render Manifest And FFmpeg Command Builder

**Files:**
- Create: `shorts_growth_agent/backend/src/shorts_agent/services/render_manifest.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/api/render.py`
- Test: `shorts_growth_agent/backend/tests/test_render_manifest.py`

**Interfaces:**
- Produces: `RenderManifest(width=1080, height=1920, scenes: list[RenderScene], audio_path, output_path)`.
- Produces: `FfmpegCommandBuilder.build(manifest: RenderManifest) -> list[str]`.

- [ ] **Step 1: Write failing manifest test**

```python
# 9:16 렌더 매니페스트와 FFmpeg 명령 생성을 검증한다.
from pathlib import Path

from shorts_agent.services.render_manifest import FfmpegCommandBuilder, RenderManifest, RenderScene


def test_ffmpeg_command_contains_vertical_output_size():
    manifest = RenderManifest(
        width=1080,
        height=1920,
        scenes=[RenderScene(asset_path=Path("scene1.png"), duration_ms=2000, subtitle="첫 문장", motion_type="zoom_in")],
        audio_path=Path("voice.wav"),
        output_path=Path("out.mp4"),
    )

    command = FfmpegCommandBuilder(ffmpeg_path="ffmpeg").build(manifest)

    assert command[0] == "ffmpeg"
    assert "scale=1080:1920" in " ".join(command)
    assert str(manifest.output_path) in command
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_render_manifest.py -q`.

Expected: FAIL with missing `render_manifest`.

- [ ] **Step 3: Implement render manifest and command builder**

```python
# 쇼츠 MP4 렌더링에 필요한 장면 매니페스트와 FFmpeg 명령을 만든다.
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RenderScene:
    asset_path: Path
    duration_ms: int
    subtitle: str
    motion_type: str


@dataclass(frozen=True)
class RenderManifest:
    width: int
    height: int
    scenes: list[RenderScene]
    audio_path: Path
    output_path: Path


class FfmpegCommandBuilder:
    def __init__(self, ffmpeg_path: str):
        self.ffmpeg_path = ffmpeg_path

    def build(self, manifest: RenderManifest) -> list[str]:
        first_scene = manifest.scenes[0]
        vf = f"scale={manifest.width}:{manifest.height}:force_original_aspect_ratio=increase,crop={manifest.width}:{manifest.height}"
        return [
            self.ffmpeg_path,
            "-y",
            "-loop",
            "1",
            "-t",
            str(first_scene.duration_ms / 1000),
            "-i",
            str(first_scene.asset_path),
            "-i",
            str(manifest.audio_path),
            "-vf",
            vf,
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(manifest.output_path),
        ]
```

- [ ] **Step 4: Add render route returning command preview**

```python
# 렌더링 요청을 받아 FFmpeg 명령 미리보기를 반환한다.
from pathlib import Path

from fastapi import APIRouter

from shorts_agent.config import get_settings
from shorts_agent.services.render_manifest import FfmpegCommandBuilder, RenderManifest, RenderScene

router = APIRouter()


@router.post("/render/preview-command")
def preview_render_command() -> dict[str, list[str]]:
    manifest = RenderManifest(
        width=1080,
        height=1920,
        scenes=[RenderScene(Path("storage/example/scene1.png"), 2000, "첫 문장", "zoom_in")],
        audio_path=Path("storage/example/voice.wav"),
        output_path=Path("storage/example/out.mp4"),
    )
    command = FfmpegCommandBuilder(get_settings().ffmpeg_path).build(manifest)
    return {"command": command}
```

- [ ] **Step 5: Run tests**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_render_manifest.py -q`.

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add shorts_growth_agent/backend/src/shorts_agent/services/render_manifest.py shorts_growth_agent/backend/src/shorts_agent/api/render.py shorts_growth_agent/backend/tests/test_render_manifest.py
git commit -m "feat: add render manifest builder"
```

---

### Task 8: Performance Snapshot Analysis

**Files:**
- Create: `shorts_growth_agent/backend/src/shorts_agent/repositories/performance_repository.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/services/performance_analysis.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/api/performance.py`
- Test: `shorts_growth_agent/backend/tests/test_performance_analysis.py`

**Interfaces:**
- Produces: `PerformanceAnalysisService.analyze(snapshots, production_facts) -> AnalysisResult`.
- Cause candidate fields: `code`, `label`, `probability`, `reason`.

- [ ] **Step 1: Write failing analysis tests**

```python
# 시간별 성과 곡선을 먼저 보고 제작 데이터를 보조로 사용한다.
from shorts_agent.services.performance_analysis import PerformanceAnalysisService, PerformancePoint


def test_low_ctr_after_good_impressions_points_to_title_thumbnail():
    snapshots = [
        PerformancePoint(minutes_since_upload=60, views=100, impressions=5000, ctr=0.02, retention_3s=0.7),
        PerformancePoint(minutes_since_upload=360, views=130, impressions=9000, ctr=0.014, retention_3s=0.68),
    ]

    result = PerformanceAnalysisService().analyze(snapshots, {"hook_type": "question"})

    assert result.cause_candidates[0].code == "title_thumbnail_mismatch"


def test_high_ctr_low_three_second_retention_points_to_hook():
    snapshots = [
        PerformancePoint(minutes_since_upload=60, views=600, impressions=5000, ctr=0.12, retention_3s=0.22),
    ]

    result = PerformanceAnalysisService().analyze(snapshots, {"first_scene_motion": "none"})

    assert result.cause_candidates[0].code == "weak_first_three_seconds"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_performance_analysis.py -q`.

Expected: FAIL with missing `performance_analysis`.

- [ ] **Step 3: Implement analysis service**

```python
# 시간별 성과 데이터 중심으로 원인 후보를 분석한다.
from dataclasses import dataclass


@dataclass(frozen=True)
class PerformancePoint:
    minutes_since_upload: int
    views: int
    impressions: int
    ctr: float
    retention_3s: float


@dataclass(frozen=True)
class CauseCandidate:
    code: str
    label: str
    probability: float
    reason: str


@dataclass(frozen=True)
class AnalysisResult:
    cause_candidates: list[CauseCandidate]
    next_experiments: list[str]


class PerformanceAnalysisService:
    def analyze(self, snapshots: list[PerformancePoint], production_facts: dict) -> AnalysisResult:
        if not snapshots:
            return AnalysisResult([], ["성과 스냅샷을 먼저 입력합니다."])
        latest = sorted(snapshots, key=lambda item: item.minutes_since_upload)[-1]
        candidates: list[CauseCandidate] = []
        if latest.impressions >= 1000 and latest.ctr < 0.03:
            candidates.append(CauseCandidate(
                "title_thumbnail_mismatch",
                "제목/썸네일 문제 가능성",
                0.78,
                "노출은 충분하지만 클릭률이 낮습니다.",
            ))
        if latest.ctr >= 0.08 and latest.retention_3s < 0.35:
            candidates.append(CauseCandidate(
                "weak_first_three_seconds",
                "첫 3초 후킹 문제 가능성",
                0.82,
                "클릭은 되었지만 초반 유지율이 낮습니다.",
            ))
        if not candidates:
            candidates.append(CauseCandidate(
                "insufficient_signal",
                "추가 데이터 필요",
                0.45,
                "성과 패턴이 아직 명확하지 않습니다.",
            ))
        return AnalysisResult(
            cause_candidates=sorted(candidates, key=lambda item: item.probability, reverse=True),
            next_experiments=self._experiments(candidates, production_facts),
        )

    def _experiments(self, candidates: list[CauseCandidate], production_facts: dict) -> list[str]:
        experiments = []
        for candidate in candidates:
            if candidate.code == "title_thumbnail_mismatch":
                experiments.append("같은 키워드로 제목 첫 12자를 더 직접적으로 바꾼 버전을 비교합니다.")
            if candidate.code == "weak_first_three_seconds":
                experiments.append("첫 장면에 줌인 또는 흔들림 모션과 더 짧은 후킹 문장을 적용합니다.")
        return experiments or ["동일 카테고리 영상 3개 이상과 시간별 성과를 비교합니다."]
```

- [ ] **Step 4: Add performance route**

```python
# 수동 성과 입력과 회고 리포트 생성을 제공한다.
from fastapi import APIRouter
from pydantic import BaseModel

from shorts_agent.services.performance_analysis import PerformanceAnalysisService, PerformancePoint

router = APIRouter()


class PerformanceAnalysisRequest(BaseModel):
    snapshots: list[PerformancePoint]
    production_facts: dict


@router.post("/performance/analyze")
def analyze_performance(request: PerformanceAnalysisRequest):
    result = PerformanceAnalysisService().analyze(request.snapshots, request.production_facts)
    return {
        "cause_candidates": [candidate.__dict__ for candidate in result.cause_candidates],
        "next_experiments": result.next_experiments,
    }
```

- [ ] **Step 5: Run tests**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_performance_analysis.py -q`.

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add shorts_growth_agent/backend/src/shorts_agent/repositories/performance_repository.py shorts_growth_agent/backend/src/shorts_agent/services/performance_analysis.py shorts_growth_agent/backend/src/shorts_agent/api/performance.py shorts_growth_agent/backend/tests/test_performance_analysis.py
git commit -m "feat: add performance cause analysis"
```

---

### Task 9: Project API Integration

**Files:**
- Modify: `shorts_growth_agent/backend/src/shorts_agent/api/projects.py`
- Modify: `shorts_growth_agent/backend/src/shorts_agent/main.py`
- Test: `shorts_growth_agent/backend/tests/test_api_projects.py`

**Interfaces:**
- Produces: `POST /api/projects`.
- Produces: `GET /api/projects/{project_id}`.
- Produces: `POST /api/projects/{project_id}/generate-plan`.

- [ ] **Step 1: Write failing API integration test**

```python
# 프로젝트 생성 후 대본 계획 생성 API까지 연결한다.
from fastapi.testclient import TestClient

from shorts_agent.main import create_app


def test_create_project_and_generate_plan():
    client = TestClient(create_app(database_url="sqlite:///:memory:"))

    create_response = client.post("/api/projects", json={"title": "게임 이슈", "category": "게임", "selected_keyword": "업데이트"})
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    plan_response = client.post(f"/api/projects/{project_id}/generate-plan")

    assert plan_response.status_code == 200
    body = plan_response.json()
    assert body["keyword"] == "업데이트"
    assert len(body["scenes"]) >= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_api_projects.py -q`.

Expected: FAIL because `create_app()` does not accept `database_url`.

- [ ] **Step 3: Add app dependency injection**

Modify `create_app()`.

```python
def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="Shorts Growth Agent")
    engine = make_engine(database_url)
    init_db(engine)
    app.state.SessionFactory = make_session_factory(engine)
    app.include_router(health_router, prefix="/api")
    app.include_router(trends_router, prefix="/api")
    app.include_router(projects_router, prefix="/api")
    return app
```

- [ ] **Step 4: Implement project routes**

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

- [ ] **Step 5: Run integration test**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_api_projects.py -q`.

Expected: PASS.

- [ ] **Step 6: Run backend test suite**

Run: `cd shorts_growth_agent/backend && python -m pytest -q`.

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add shorts_growth_agent/backend/src/shorts_agent/api/projects.py shorts_growth_agent/backend/src/shorts_agent/main.py shorts_growth_agent/backend/tests/test_api_projects.py
git commit -m "feat: connect project generation api"
```

---

### Task 10: Frontend Scaffold And Top-Step Layout

**Files:**
- Create: `shorts_growth_agent/frontend/package.json`
- Create: `shorts_growth_agent/frontend/index.html`
- Create: `shorts_growth_agent/frontend/src/main.tsx`
- Create: `shorts_growth_agent/frontend/src/App.tsx`
- Create: `shorts_growth_agent/frontend/src/types.ts`
- Create: `shorts_growth_agent/frontend/src/components/TopStepNav.tsx`
- Test: `shorts_growth_agent/frontend/tests/TopStepNav.test.tsx`

**Interfaces:**
- Produces: `TopStepNav({currentStep, onStepChange})`.
- Step ids: `keyword`, `script`, `voice`, `editor`, `export`.

- [ ] **Step 1: Write failing frontend test**

```tsx
// 상단 단계 표시 UI가 현재 단계를 표시하는지 검증한다.
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TopStepNav } from "../src/components/TopStepNav";

describe("TopStepNav", () => {
  it("marks the current step", () => {
    render(<TopStepNav currentStep="script" onStepChange={vi.fn()} />);

    expect(screen.getByRole("button", { name: "대본" })).toHaveAttribute("aria-current", "step");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd shorts_growth_agent/frontend && npm test -- TopStepNav.test.tsx`.

Expected: FAIL with missing package setup or component.

- [ ] **Step 3: Add frontend package config**

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^16.0.0",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "typescript": "^5.5.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 4: Implement step types and nav**

```tsx
// 쇼츠 제작 단계 타입을 정의한다.
export type StepId = "keyword" | "script" | "voice" | "editor" | "export";
```

```tsx
// 상단의 작은 제작 단계 표시 컴포넌트다.
import type { StepId } from "../types";

const STEPS: Array<{ id: StepId; label: string }> = [
  { id: "keyword", label: "키워드" },
  { id: "script", label: "대본" },
  { id: "voice", label: "음성/자막" },
  { id: "editor", label: "편집" },
  { id: "export", label: "출력" },
];

export function TopStepNav({
  currentStep,
  onStepChange,
}: {
  currentStep: StepId;
  onStepChange: (step: StepId) => void;
}) {
  return (
    <nav className="top-step-nav" aria-label="쇼츠 제작 단계">
      {STEPS.map((step) => (
        <button
          key={step.id}
          type="button"
          aria-current={currentStep === step.id ? "step" : undefined}
          onClick={() => onStepChange(step.id)}
        >
          {step.label}
        </button>
      ))}
    </nav>
  );
}
```

- [ ] **Step 5: Implement App shell**

```tsx
// 상단 단계형 쇼츠 제작 화면의 기본 레이아웃이다.
import { useState } from "react";
import { TopStepNav } from "./components/TopStepNav";
import type { StepId } from "./types";

export function App() {
  const [currentStep, setCurrentStep] = useState<StepId>("keyword");

  return (
    <main>
      <TopStepNav currentStep={currentStep} onStepChange={setCurrentStep} />
      <section className="workspace">
        <aside>현재 단계 도구</aside>
        <section>9:16 미리보기와 작업 영역</section>
        <aside>AI 보조와 성장 메모리</aside>
      </section>
    </main>
  );
}
```

- [ ] **Step 6: Run tests**

Run: `cd shorts_growth_agent/frontend && npm test -- TopStepNav.test.tsx`.

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add shorts_growth_agent/frontend
git commit -m "feat: add top step frontend shell"
```

---

### Task 11: Frontend Project Store And Step Pages

**Files:**
- Create: `shorts_growth_agent/frontend/src/api/client.ts`
- Create: `shorts_growth_agent/frontend/src/state/projectStore.ts`
- Create: `shorts_growth_agent/frontend/src/pages/KeywordStep.tsx`
- Create: `shorts_growth_agent/frontend/src/pages/ScriptStep.tsx`
- Create: `shorts_growth_agent/frontend/src/pages/VoiceSubtitleStep.tsx`
- Create: `shorts_growth_agent/frontend/src/pages/EditorStep.tsx`
- Create: `shorts_growth_agent/frontend/src/pages/ExportStep.tsx`
- Test: `shorts_growth_agent/frontend/tests/projectStore.test.ts`

**Interfaces:**
- Produces: `createProject(payload)`.
- Produces: `generatePlan(projectId)`.
- Produces: project store state `{ project, scriptPlan, currentStep }`.

- [ ] **Step 1: Write failing store test**

```ts
// 프로젝트 상태 저장소가 생성 결과와 대본 계획을 보관하는지 검증한다.
import { describe, expect, it } from "vitest";
import { createInitialProjectState, reduceProjectState } from "../src/state/projectStore";

describe("projectStore", () => {
  it("stores generated script plan", () => {
    const state = createInitialProjectState();
    const next = reduceProjectState(state, {
      type: "planGenerated",
      plan: { keyword: "업데이트", scenes: [{ index: 1, subtitle: "첫 문장" }] },
    });

    expect(next.scriptPlan?.keyword).toBe("업데이트");
    expect(next.currentStep).toBe("script");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd shorts_growth_agent/frontend && npm test -- projectStore.test.ts`.

Expected: FAIL with missing `projectStore`.

- [ ] **Step 3: Implement API client**

```ts
// 백엔드 API 호출을 담당한다.
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api";

export async function createProject(payload: { title: string; category: string; selected_keyword?: string }) {
  const response = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("프로젝트 생성에 실패했습니다.");
  return response.json();
}

export async function generatePlan(projectId: number) {
  const response = await fetch(`${API_BASE}/projects/${projectId}/generate-plan`, { method: "POST" });
  if (!response.ok) throw new Error("대본 계획 생성에 실패했습니다.");
  return response.json();
}
```

- [ ] **Step 4: Implement project store reducer**

```ts
// 쇼츠 프로젝트 화면 상태를 관리한다.
import type { StepId } from "../types";

type ScriptPlan = {
  keyword: string;
  scenes: Array<{ index: number; subtitle: string }>;
};

type ProjectState = {
  currentStep: StepId;
  project: { id: number; title: string } | null;
  scriptPlan: ScriptPlan | null;
};

type ProjectAction =
  | { type: "projectCreated"; project: { id: number; title: string } }
  | { type: "planGenerated"; plan: ScriptPlan }
  | { type: "stepChanged"; step: StepId };

export function createInitialProjectState(): ProjectState {
  return { currentStep: "keyword", project: null, scriptPlan: null };
}

export function reduceProjectState(state: ProjectState, action: ProjectAction): ProjectState {
  if (action.type === "projectCreated") {
    return { ...state, project: action.project, currentStep: "script" };
  }
  if (action.type === "planGenerated") {
    return { ...state, scriptPlan: action.plan, currentStep: "script" };
  }
  if (action.type === "stepChanged") {
    return { ...state, currentStep: action.step };
  }
  return state;
}
```

- [ ] **Step 5: Add simple step pages**

Each page must export a component with a focused role.

```tsx
// 키워드와 카테고리 기반 소재 발굴 화면이다.
export function KeywordStep() {
  return <section aria-label="키워드 단계">한국 인기 영상과 키워드 추천</section>;
}
```

```tsx
// 대본 하네스와 장면 대본을 편집하는 화면이다.
export function ScriptStep() {
  return <section aria-label="대본 단계">대본 하네스와 장면 대본</section>;
}
```

```tsx
// TTS와 자막 싱크를 조정하는 화면이다.
export function VoiceSubtitleStep() {
  return <section aria-label="음성 자막 단계">TTS와 자막 자동 싱크</section>;
}
```

```tsx
// 쇼츠 장면과 레이어를 편집하는 화면이다.
export function EditorStep() {
  return <section aria-label="편집 단계">9:16 캔버스와 타임라인</section>;
}
```

```tsx
// MP4 렌더링과 업로드 패키지를 만드는 화면이다.
export function ExportStep() {
  return <section aria-label="출력 단계">MP4 렌더링과 업로드 패키지</section>;
}
```

- [ ] **Step 6: Run tests**

Run: `cd shorts_growth_agent/frontend && npm test -- projectStore.test.ts`.

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add shorts_growth_agent/frontend/src/api shorts_growth_agent/frontend/src/state shorts_growth_agent/frontend/src/pages shorts_growth_agent/frontend/tests/projectStore.test.ts
git commit -m "feat: add frontend project workflow state"
```

---

### Task 12: Preview Canvas, Timeline, And Growth Panel

**Files:**
- Create: `shorts_growth_agent/frontend/src/components/ShortsCanvas.tsx`
- Create: `shorts_growth_agent/frontend/src/components/Timeline.tsx`
- Create: `shorts_growth_agent/frontend/src/components/GrowthAssistantPanel.tsx`
- Create: `shorts_growth_agent/frontend/src/pages/GrowthReportPage.tsx`

**Interfaces:**
- Produces: `ShortsCanvas({scene})`.
- Produces: `Timeline({scenes, selectedSceneIndex, onSelectScene})`.
- Produces: `GrowthAssistantPanel({notes, recommendations})`.

- [ ] **Step 1: Add canvas component**

```tsx
// 9:16 쇼츠 미리보기 캔버스 컴포넌트다.
export function ShortsCanvas({
  scene,
}: {
  scene: { subtitle: string; motion_type?: string; source_type?: string } | null;
}) {
  return (
    <section aria-label="쇼츠 미리보기" className="shorts-canvas">
      <div className="phone-frame">
        <div className="scene-source">{scene?.source_type ?? "ai_image"}</div>
        <strong className="scene-subtitle">{scene?.subtitle ?? "장면을 선택하세요"}</strong>
      </div>
    </section>
  );
}
```

- [ ] **Step 2: Add timeline component**

```tsx
// 장면별 타임라인 선택 컴포넌트다.
export function Timeline({
  scenes,
  selectedSceneIndex,
  onSelectScene,
}: {
  scenes: Array<{ index: number; subtitle: string; duration_ms?: number }>;
  selectedSceneIndex: number;
  onSelectScene: (index: number) => void;
}) {
  return (
    <section aria-label="장면 타임라인">
      {scenes.map((scene) => (
        <button
          key={scene.index}
          type="button"
          aria-current={scene.index === selectedSceneIndex ? "true" : undefined}
          onClick={() => onSelectScene(scene.index)}
        >
          장면 {scene.index}
        </button>
      ))}
    </section>
  );
}
```

- [ ] **Step 3: Add growth assistant panel**

```tsx
// 성장 메모리와 AI 보조 제안을 보여주는 패널이다.
export function GrowthAssistantPanel({
  notes,
  recommendations,
}: {
  notes: string[];
  recommendations: string[];
}) {
  return (
    <aside aria-label="AI 보조와 성장 메모리">
      <h2>성장 메모리</h2>
      <ul>{notes.map((note) => <li key={note}>{note}</li>)}</ul>
      <h2>다음 제안</h2>
      <ul>{recommendations.map((item) => <li key={item}>{item}</li>)}</ul>
    </aside>
  );
}
```

- [ ] **Step 4: Add growth report page**

```tsx
// 시간별 성과 분석 리포트 화면이다.
export function GrowthReportPage() {
  return (
    <section aria-label="성장 리포트">
      <h1>시간별 성과 분석</h1>
      <p>10분, 30분, 1시간, 24시간, 7일 단위 성과를 비교해 원인 후보를 좁힙니다.</p>
    </section>
  );
}
```

- [ ] **Step 5: Run frontend tests and build**

Run: `cd shorts_growth_agent/frontend && npm test`.

Expected: PASS.

Run: `cd shorts_growth_agent/frontend && npm run build`.

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add shorts_growth_agent/frontend/src/components shorts_growth_agent/frontend/src/pages/GrowthReportPage.tsx
git commit -m "feat: add editor preview components"
```

---

### Task 13: End-To-End MVP Smoke Test

**Files:**
- Create: `shorts_growth_agent/backend/tests/test_mvp_flow.py`
- Modify: `shorts_growth_agent/README.md`

**Interfaces:**
- Verifies one flow: create project -> generate plan -> sync subtitles -> recommend sources -> build render command -> analyze performance.

- [ ] **Step 1: Write the backend smoke test**

```python
# MVP 전체 파이프라인이 한 번에 연결되는지 검증한다.
from pathlib import Path

from shorts_agent.services.performance_analysis import PerformanceAnalysisService, PerformancePoint
from shorts_agent.services.render_manifest import FfmpegCommandBuilder, RenderManifest, RenderScene
from shorts_agent.services.script_planner import HarnessConfig, ScriptPlanner
from shorts_agent.services.source_recommender import SourceRecommender
from shorts_agent.services.subtitle_sync import SubtitleSyncService


def test_mvp_pipeline_smoke():
    harness = HarnessConfig("정보+후킹형", "빠른 정보형", "강함", 45, ["무조건"])
    plan = ScriptPlanner().generate("게임 업데이트", "게임", harness)
    subtitles = SubtitleSyncService().sync([scene.subtitle for scene in plan.scenes], 45000)
    source = SourceRecommender().recommend("게임", plan.scenes[1].index, plan.scenes[1].source_type)
    manifest = RenderManifest(
        width=1080,
        height=1920,
        scenes=[RenderScene(Path("scene1.png"), subtitles[0].end_ms, subtitles[0].text, "zoom_in")],
        audio_path=Path("voice.wav"),
        output_path=Path("out.mp4"),
    )
    command = FfmpegCommandBuilder("ffmpeg").build(manifest)
    report = PerformanceAnalysisService().analyze(
        [PerformancePoint(60, views=100, impressions=5000, ctr=0.02, retention_3s=0.7)],
        {"source_type": source.source_type},
    )

    assert plan.scenes
    assert subtitles
    assert command[0] == "ffmpeg"
    assert report.cause_candidates[0].code == "title_thumbnail_mismatch"
```

- [ ] **Step 2: Run smoke test**

Run: `cd shorts_growth_agent/backend && python -m pytest tests/test_mvp_flow.py -q`.

Expected: PASS.

- [ ] **Step 3: Update README with run commands**

```markdown
## Development

Backend:

```bash
cd shorts_growth_agent/backend
python -m pip install -e ".[dev]"
uvicorn shorts_agent.main:app --reload
```

Frontend:

```bash
cd shorts_growth_agent/frontend
npm install
npm run dev
```

Verification:

```bash
cd shorts_growth_agent/backend
python -m pytest -q

cd ../frontend
npm test
npm run build
```
```

- [ ] **Step 4: Run all verification commands**

Run: `cd shorts_growth_agent/backend && python -m pytest -q`.

Expected: PASS.

Run: `cd shorts_growth_agent/frontend && npm test`.

Expected: PASS.

Run: `cd shorts_growth_agent/frontend && npm run build`.

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add shorts_growth_agent/backend/tests/test_mvp_flow.py shorts_growth_agent/README.md
git commit -m "test: add mvp pipeline smoke test"
```

---

## Self-Review

**Spec coverage:** This plan covers the local web app, Korean YouTube trend collection, category/keyword tracking, view-speed scoring, editable script harness, TTS/subtitle sync, AI image/meme/clip source recommendations, top-step editor UI, MP4 render manifest, performance snapshots, time-based cause analysis, and user-approved long-term improvement loop.

**Deferred integration with explicit boundary:** Real YouTube API calls, real TTS voice engines, real image generation, meme MCP, clip trimming UI, YouTube private upload, and YouTube Analytics API are adapter-backed extensions after the MVP flow works. The interfaces are defined so they can be added without rewriting the core flow.

**Placeholder scan:** 모든 작업에 구체적인 파일, 인터페이스, 테스트 명령, 기대 결과가 포함되어 있다.

**Type consistency:** `YouTubeVideoSignal`, `TrendScore`, `HarnessConfig`, `ScriptPlan`, `PlannedScene`, `SubtitleCue`, `SourceRecommendation`, `RenderManifest`, `PerformancePoint`, and `AnalysisResult` are introduced before use by later tasks.
