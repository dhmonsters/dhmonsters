# FastAPI 앱 생성과 라우터 등록을 담당합니다.
from fastapi import FastAPI

from shorts_agent.api.health import router as health_router
from shorts_agent.api.performance import router as performance_router
from shorts_agent.api.projects import router as projects_router
from shorts_agent.api.trends import router as trends_router
from shorts_agent.config import get_settings


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="Shorts Growth Agent")
    app.state.database_url = database_url or get_settings().database_url

    app.include_router(health_router, prefix="/api")
    app.include_router(performance_router, prefix="/api")
    app.include_router(trends_router, prefix="/api")
    app.include_router(projects_router, prefix="/api")
    return app


app = create_app()
