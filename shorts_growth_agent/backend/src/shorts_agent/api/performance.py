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
