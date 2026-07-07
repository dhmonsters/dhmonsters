# Task 1 Brief: Backend Scaffold And Health Check

## Goal

Create the first backend scaffold for `shorts_growth_agent` and prove `GET /api/health` works.

## Global Constraints

- User-facing text and reports should be Korean.
- Work only inside `shorts_growth_agent` and progress files under `03_output` or `.superpowers/sdd`.
- Do not touch `maple_bot` or unrelated root files.
- Every new source file must start with a one-line Korean comment explaining its role.
- Follow TDD. Write the test first, run it and observe failure, then implement the minimum code, then rerun tests.
- Do not run `git add` or `git commit`. The parent agent will commit after review because this workspace blocks the normal Git index.

## Files To Create

- `shorts_growth_agent/README.md`
- `shorts_growth_agent/.env.example`
- `shorts_growth_agent/backend/pyproject.toml`
- `shorts_growth_agent/backend/src/shorts_agent/__init__.py`
- `shorts_growth_agent/backend/src/shorts_agent/config.py`
- `shorts_growth_agent/backend/src/shorts_agent/main.py`
- `shorts_growth_agent/backend/src/shorts_agent/api/__init__.py`
- `shorts_growth_agent/backend/src/shorts_agent/api/health.py`
- `shorts_growth_agent/backend/tests/conftest.py`
- `shorts_growth_agent/backend/tests/test_health.py`

## Required Interfaces

- `create_app() -> FastAPI`.
- `GET /api/health -> {"status": "ok", "app": "shorts-growth-agent"}`.

## Required Test

Create `shorts_growth_agent/backend/tests/test_health.py` with a test equivalent to this behavior.

```python
from fastapi.testclient import TestClient
from shorts_agent.main import create_app


def test_health_check_returns_ok():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "shorts-growth-agent"}
```

## Backend Metadata

Create `shorts_growth_agent/backend/pyproject.toml`.

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

## Required Settings

Implement `shorts_growth_agent/backend/src/shorts_agent/config.py`.

```python
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

## Required App Wiring

Implement `shorts_growth_agent/backend/src/shorts_agent/main.py`.

```python
from fastapi import FastAPI

from shorts_agent.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Shorts Growth Agent")
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
```

Implement `shorts_growth_agent/backend/src/shorts_agent/api/health.py`.

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "app": "shorts-growth-agent"}
```

## Env Example

Create `shorts_growth_agent/.env.example`.

```env
SHORTS_DATABASE_URL=sqlite:///./data/shorts_agent.db
SHORTS_STORAGE_ROOT=./storage
SHORTS_YOUTUBE_API_KEY=
SHORTS_FFMPEG_PATH=ffmpeg
```

## Verification

1. Run `cd shorts_growth_agent/backend && python -m pytest tests/test_health.py -q` after writing the test and before implementation. It must fail for the expected missing implementation reason.
2. Run the same command after implementation. It must pass.

## Report Contract

Write the full report to `.superpowers/sdd/task-1-report.md`.

Return only this summary to the parent.

- Status: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`.
- Files changed.
- Red test result.
- Green test result.
- Concerns.
