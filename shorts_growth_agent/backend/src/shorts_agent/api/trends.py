# 트렌드 조회 API를 통해 인기 영상 분석 결과를 반환한다.
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
import httpx

from shorts_agent.adapters.youtube import YouTubeAdapter
from shorts_agent.config import get_settings
from shorts_agent.schemas import TrendCandidatePayload
from shorts_agent.services.sample_trends import get_sample_trend_signals
from shorts_agent.services.trend_analysis import TrendAnalysisService, TrendCandidateInput
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
    settings = get_settings()
    now = datetime.now(timezone.utc)
    source = "youtube"
    if settings.youtube_api_key:
        try:
            signals = adapter.fetch_popular(region_code=region, category_id=category_id)
        except httpx.HTTPError:
            source = "sample_fallback"
            signals = get_sample_trend_signals(now)
    else:
        source = "sample"
        signals = get_sample_trend_signals(now)
    if category_id:
        signals = [signal for signal in signals if signal.category_id == category_id]
    if keyword:
        keyword_lower = keyword.lower()
        signals = [
            signal
            for signal in signals
            if keyword_lower in signal.title.lower()
            or keyword_lower in signal.channel_title.lower()
        ]
    ranked = TrendScoringService().rank(signals, now)
    return {
        "region": region,
        "category_id": category_id,
        "keyword": keyword,
        "source": source,
        "items": [asdict(item) for item in ranked],
    }


@router.post("/trends/analyze")
def analyze_trend(payload: TrendCandidatePayload):
    analysis = TrendAnalysisService().analyze(
        TrendCandidateInput(
            video_id=payload.video_id,
            title=payload.title,
            category_id=payload.category_id,
            channel_title=payload.channel_title,
            view_count=payload.view_count,
            views_per_hour=payload.views_per_hour,
            score=payload.score,
            keyword_candidates=payload.keyword_candidates,
            thumbnail_url=payload.thumbnail_url,
        )
    )
    return asdict(analysis)
