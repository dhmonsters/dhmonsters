# 트렌드 조회 API를 통해 인기 영상 분석 결과를 반환한다.
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
