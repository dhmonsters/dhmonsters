# 헬스 체크 API 엔드포인트를 제공합니다.
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "app": "shorts-growth-agent"}
