# API 입출력을 위한 pydantic 스키마를 제공합니다.
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


class TrendCandidatePayload(BaseModel):
    video_id: str
    title: str
    category_id: str
    channel_title: str
    view_count: int
    views_per_hour: float
    score: float
    keyword_candidates: list[str]
    thumbnail_url: str = ""


class HarnessPayload(BaseModel):
    name: str = "기본 하네스"
    tone: str = "명료"
    hook_strength: str = "강함"
    target_seconds: int = 45
    forbidden_terms: list[str] = []
    custom_prompt: str = ""


class TrendAnalysisPayload(BaseModel):
    primary_angle: str = ""
    script_seed: str = ""


class GeneratePlanRequest(BaseModel):
    harness: HarnessPayload | None = None
    trend_analysis: TrendAnalysisPayload | None = None
