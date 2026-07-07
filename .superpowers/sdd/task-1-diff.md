diff --git a/shorts_growth_agent/.env.example b/shorts_growth_agent/.env.example
new file mode 100644
index 00000000..61fc0660
--- /dev/null
+++ b/shorts_growth_agent/.env.example
@@ -0,0 +1,4 @@
+SHORTS_DATABASE_URL=sqlite:///./data/shorts_agent.db
+SHORTS_STORAGE_ROOT=./storage
+SHORTS_YOUTUBE_API_KEY=
+SHORTS_FFMPEG_PATH=ffmpeg
diff --git a/shorts_growth_agent/README.md b/shorts_growth_agent/README.md
new file mode 100644
index 00000000..59eff849
--- /dev/null
+++ b/shorts_growth_agent/README.md
@@ -0,0 +1,3 @@
+# Shorts Growth Agent
+
+백엔드 기반 골격과 헬스 체크 API를 위한 프로젝트입니다.
diff --git a/shorts_growth_agent/backend/pyproject.toml b/shorts_growth_agent/backend/pyproject.toml
new file mode 100644
index 00000000..ac1b572c
--- /dev/null
+++ b/shorts_growth_agent/backend/pyproject.toml
@@ -0,0 +1,24 @@
+[project]
+name = "shorts-growth-agent-backend"
+version = "0.1.0"
+requires-python = ">=3.12"
+dependencies = [
+  "fastapi>=0.115",
+  "uvicorn[standard]>=0.30",
+  "pydantic>=2.8",
+  "pydantic-settings>=2.4",
+  "sqlalchemy>=2.0",
+  "httpx>=0.27",
+]
+
+[project.optional-dependencies]
+dev = [
+  "pytest>=8.2",
+]
+
+[tool.pytest.ini_options]
+pythonpath = ["src"]
+testpaths = ["tests"]
+filterwarnings = [
+  "ignore:Using `httpx` with `starlette.testclient` is deprecated:starlette.exceptions.StarletteDeprecationWarning",
+]
diff --git a/shorts_growth_agent/backend/src/shorts_agent/__init__.py b/shorts_growth_agent/backend/src/shorts_agent/__init__.py
new file mode 100644
index 00000000..308cc37b
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/__init__.py
@@ -0,0 +1 @@
+# shorts_agent 패키지 초기화 모듈
diff --git a/shorts_growth_agent/backend/src/shorts_agent/api/__init__.py b/shorts_growth_agent/backend/src/shorts_agent/api/__init__.py
new file mode 100644
index 00000000..331da294
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/api/__init__.py
@@ -0,0 +1 @@
+# shorts_agent API 라우터 패키지 초기화 모듈
diff --git a/shorts_growth_agent/backend/src/shorts_agent/api/health.py b/shorts_growth_agent/backend/src/shorts_agent/api/health.py
new file mode 100644
index 00000000..8330814b
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/api/health.py
@@ -0,0 +1,9 @@
+# 헬스 체크 API 엔드포인트를 제공합니다.
+from fastapi import APIRouter
+
+router = APIRouter()
+
+
+@router.get("/health")
+def health_check() -> dict[str, str]:
+    return {"status": "ok", "app": "shorts-growth-agent"}
diff --git a/shorts_growth_agent/backend/src/shorts_agent/config.py b/shorts_growth_agent/backend/src/shorts_agent/config.py
new file mode 100644
index 00000000..442ecee1
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/config.py
@@ -0,0 +1,20 @@
+# 애플리케이션 설정을 정의하고 환경변수로부터 읽어옵니다.
+from functools import lru_cache
+from pathlib import Path
+
+from pydantic_settings import BaseSettings, SettingsConfigDict
+
+
+class Settings(BaseSettings):
+    app_name: str = "shorts-growth-agent"
+    database_url: str = "sqlite:///./data/shorts_agent.db"
+    storage_root: Path = Path("./storage")
+    youtube_api_key: str = ""
+    ffmpeg_path: str = "ffmpeg"
+
+    model_config = SettingsConfigDict(env_file=".env", env_prefix="SHORTS_")
+
+
+@lru_cache
+def get_settings() -> Settings:
+    return Settings()
diff --git a/shorts_growth_agent/backend/src/shorts_agent/main.py b/shorts_growth_agent/backend/src/shorts_agent/main.py
new file mode 100644
index 00000000..cf3a427e
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/main.py
@@ -0,0 +1,13 @@
+# FastAPI 앱 생성 및 라우터 등록을 담당합니다.
+from fastapi import FastAPI
+
+from shorts_agent.api.health import router as health_router
+
+
+def create_app() -> FastAPI:
+    app = FastAPI(title="Shorts Growth Agent")
+    app.include_router(health_router, prefix="/api")
+    return app
+
+
+app = create_app()
diff --git a/shorts_growth_agent/backend/tests/conftest.py b/shorts_growth_agent/backend/tests/conftest.py
new file mode 100644
index 00000000..21c7b3e1
--- /dev/null
+++ b/shorts_growth_agent/backend/tests/conftest.py
@@ -0,0 +1 @@
+# 현재 작업에는 공통 픽스처가 없어 기본 설정만 유지합니다.
diff --git a/shorts_growth_agent/backend/tests/test_health.py b/shorts_growth_agent/backend/tests/test_health.py
new file mode 100644
index 00000000..4b21f701
--- /dev/null
+++ b/shorts_growth_agent/backend/tests/test_health.py
@@ -0,0 +1,12 @@
+# 헬스 체크 API 동작을 검증합니다.
+from fastapi.testclient import TestClient
+from shorts_agent.main import create_app
+
+
+def test_health_check_returns_ok():
+    client = TestClient(create_app())
+
+    response = client.get("/api/health")
+
+    assert response.status_code == 200
+    assert response.json() == {"status": "ok", "app": "shorts-growth-agent"}
