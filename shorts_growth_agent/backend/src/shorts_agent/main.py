# FastAPI 앱 생성 및 라우터 등록을 담당합니다.
from fastapi import FastAPI

from shorts_agent.api.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Shorts Growth Agent")
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
