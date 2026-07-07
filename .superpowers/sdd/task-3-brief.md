# Task 3 Brief: YouTube Trend Adapter And Trend Scoring

## Goal

Add YouTube popular-video signal types, a replaceable adapter interface, trend scoring, and the `/api/trends` route for Korean Shorts topic discovery.

## Global Constraints

- User-facing text and reports should be Korean.
- Work only inside the assigned files under `shorts_growth_agent`, plus write your report file at `.superpowers/sdd/task-3-report.md`.
- Do not touch `maple_bot`, frontend files, or unrelated root files.
- Every new source file must start with a one-line Korean comment explaining its role.
- Follow TDD. Write tests first, run them and observe failure, then implement the minimum code, then rerun tests.
- Do not run `git add` or `git commit`. The parent agent will commit because this workspace blocks the normal Git index.
- Use the existing backend virtual environment command when running tests: `.\.venv\Scripts\python.exe -m pytest ...`.

## Existing Context

Task 1 created the backend scaffold and `create_app()`.
Task 2 created database models and repositories.

## Files To Create Or Modify

- Create: `shorts_growth_agent/backend/src/shorts_agent/adapters/youtube.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/services/trend_scoring.py`
- Create: `shorts_growth_agent/backend/src/shorts_agent/api/trends.py`
- Modify: `shorts_growth_agent/backend/src/shorts_agent/main.py`
- Test: `shorts_growth_agent/backend/tests/test_trend_scoring.py`

## Required Interfaces

- `YouTubeVideoSignal(video_id, title, category_id, channel_title, published_at, view_count, like_count)`.
- `TrendScoringService.rank(signals: list[YouTubeVideoSignal], now: datetime) -> list[TrendScore]`.
- `GET /api/trends?region=KR&category_id=20&keyword=...`.

## Required Tests

Create `shorts_growth_agent/backend/tests/test_trend_scoring.py`.

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

## Required YouTube Adapter

Implement `shorts_growth_agent/backend/src/shorts_agent/adapters/youtube.py`.

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

    def fetch_popular(
        self,
        region_code: str = "KR",
        category_id: str | None = None,
        max_results: int = 25,
    ) -> list[YouTubeVideoSignal]:
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

## Required Trend Scoring

Implement `shorts_growth_agent/backend/src/shorts_agent/services/trend_scoring.py`.

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

## Required Trends Route

Implement `shorts_growth_agent/backend/src/shorts_agent/api/trends.py`.

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

Update `shorts_growth_agent/backend/src/shorts_agent/main.py`.

```python
from shorts_agent.api.trends import router as trends_router

app.include_router(trends_router, prefix="/api")
```

Keep the existing Korean first-line role comment in `main.py`.

## Verification

1. Run `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_trend_scoring.py -q` after writing tests and before implementation. It must fail with missing `shorts_agent.adapters.youtube` or missing scoring implementation.
2. Run the same command after implementation. It must pass with clean output.
3. Run `.\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py -q`. It must pass with clean output.

## Report Contract

Write the full report to `.superpowers/sdd/task-3-report.md`.

Return only this summary to the parent.

- Status: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`.
- Files changed.
- Red test result.
- Green test result.
- Concerns.
