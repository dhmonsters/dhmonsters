diff --git a/shorts_growth_agent/backend/src/shorts_agent/adapters/__init__.py b/shorts_growth_agent/backend/src/shorts_agent/adapters/__init__.py
new file mode 100644
index 00000000..39fabced
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/adapters/__init__.py
@@ -0,0 +1,2 @@
+# YouTube 연동 어댑터 패키지를 노출하는 초기화 파일
+
diff --git a/shorts_growth_agent/backend/src/shorts_agent/adapters/youtube.py b/shorts_growth_agent/backend/src/shorts_agent/adapters/youtube.py
new file mode 100644
index 00000000..eb199fd1
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/adapters/youtube.py
@@ -0,0 +1,55 @@
+# YouTube 인기 영상 신호를 API 응답에서 파싱해 도메인 신호로 변환한다.
+from dataclasses import dataclass
+from datetime import datetime
+
+import httpx
+
+
+@dataclass(frozen=True)
+class YouTubeVideoSignal:
+    video_id: str
+    title: str
+    category_id: str
+    channel_title: str
+    published_at: datetime
+    view_count: int
+    like_count: int
+
+
+class YouTubeAdapter:
+    def __init__(self, api_key: str, client: httpx.Client | None = None):
+        self.api_key = api_key
+        self.client = client or httpx.Client(timeout=15)
+
+    def fetch_popular(
+        self,
+        region_code: str = "KR",
+        category_id: str | None = None,
+        max_results: int = 25,
+    ) -> list[YouTubeVideoSignal]:
+        params = {
+            "part": "snippet,statistics",
+            "chart": "mostPopular",
+            "regionCode": region_code,
+            "maxResults": max_results,
+            "key": self.api_key,
+        }
+        if category_id:
+            params["videoCategoryId"] = category_id
+        response = self.client.get("https://www.googleapis.com/youtube/v3/videos", params=params)
+        response.raise_for_status()
+        return [self._parse_item(item) for item in response.json().get("items", [])]
+
+    def _parse_item(self, item: dict) -> YouTubeVideoSignal:
+        snippet = item["snippet"]
+        stats = item.get("statistics", {})
+        published_at = datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00"))
+        return YouTubeVideoSignal(
+            video_id=item["id"],
+            title=snippet["title"],
+            category_id=snippet.get("categoryId", ""),
+            channel_title=snippet.get("channelTitle", ""),
+            published_at=published_at,
+            view_count=int(stats.get("viewCount", 0)),
+            like_count=int(stats.get("likeCount", 0)),
+        )
diff --git a/shorts_growth_agent/backend/src/shorts_agent/api/trends.py b/shorts_growth_agent/backend/src/shorts_agent/api/trends.py
new file mode 100644
index 00000000..21aadad8
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/api/trends.py
@@ -0,0 +1,28 @@
+# 트렌드 조회 API를 통해 인기 영상 분석 결과를 반환한다.
+from datetime import datetime, timezone
+
+from fastapi import APIRouter, Depends
+
+from shorts_agent.adapters.youtube import YouTubeAdapter
+from shorts_agent.config import get_settings
+from shorts_agent.services.trend_scoring import TrendScoringService
+
+router = APIRouter()
+
+
+def get_youtube_adapter() -> YouTubeAdapter:
+    return YouTubeAdapter(api_key=get_settings().youtube_api_key)
+
+
+@router.get("/trends")
+def get_trends(
+    region: str = "KR",
+    category_id: str | None = None,
+    keyword: str | None = None,
+    adapter: YouTubeAdapter = Depends(get_youtube_adapter),
+):
+    signals = adapter.fetch_popular(region_code=region, category_id=category_id)
+    if keyword:
+        signals = [signal for signal in signals if keyword.lower() in signal.title.lower()]
+    ranked = TrendScoringService().rank(signals, datetime.now(timezone.utc))
+    return {"items": [item.__dict__ for item in ranked]}
diff --git a/shorts_growth_agent/backend/src/shorts_agent/main.py b/shorts_growth_agent/backend/src/shorts_agent/main.py
index cf3a427e..8fc43192 100644
--- a/shorts_growth_agent/backend/src/shorts_agent/main.py
+++ b/shorts_growth_agent/backend/src/shorts_agent/main.py
@@ -1,13 +1,15 @@
 # FastAPI 앱 생성 및 라우터 등록을 담당합니다.
 from fastapi import FastAPI
 
 from shorts_agent.api.health import router as health_router
+from shorts_agent.api.trends import router as trends_router
 
 
 def create_app() -> FastAPI:
     app = FastAPI(title="Shorts Growth Agent")
     app.include_router(health_router, prefix="/api")
+    app.include_router(trends_router, prefix="/api")
     return app
 
 
 app = create_app()
diff --git a/shorts_growth_agent/backend/src/shorts_agent/services/__init__.py b/shorts_growth_agent/backend/src/shorts_agent/services/__init__.py
new file mode 100644
index 00000000..5f65add9
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/services/__init__.py
@@ -0,0 +1,2 @@
+# 트렌드 스코어링 서비스를 노출하는 서비스 패키지 초기화 파일
+
diff --git a/shorts_growth_agent/backend/src/shorts_agent/services/trend_scoring.py b/shorts_growth_agent/backend/src/shorts_agent/services/trend_scoring.py
new file mode 100644
index 00000000..578cb35b
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/services/trend_scoring.py
@@ -0,0 +1,41 @@
+# 검색 타이밍별 트렌드 점수를 계산해 정렬용 모델을 생성한다.
+from dataclasses import dataclass
+from datetime import datetime
+import re
+
+from shorts_agent.adapters.youtube import YouTubeVideoSignal
+
+
+@dataclass(frozen=True)
+class TrendScore:
+    video_id: str
+    title: str
+    category_id: str
+    views_per_hour: float
+    score: float
+    keyword_candidates: list[str]
+
+
+class TrendScoringService:
+    def rank(self, signals: list[YouTubeVideoSignal], now: datetime) -> list[TrendScore]:
+        scores = [self._score(signal, now) for signal in signals]
+        return sorted(scores, key=lambda item: item.score, reverse=True)
+
+    def _score(self, signal: YouTubeVideoSignal, now: datetime) -> TrendScore:
+        age_hours = max((now - signal.published_at).total_seconds() / 3600, 1.0)
+        views_per_hour = signal.view_count / age_hours
+        engagement_bonus = min(signal.like_count / max(signal.view_count, 1), 0.1) * 1000
+        score = views_per_hour + engagement_bonus
+        return TrendScore(
+            video_id=signal.video_id,
+            title=signal.title,
+            category_id=signal.category_id,
+            views_per_hour=views_per_hour,
+            score=score,
+            keyword_candidates=self._keywords(signal.title),
+        )
+
+    def _keywords(self, title: str) -> list[str]:
+        tokens = re.findall(r"[가-힣A-Za-z0-9]{2,}", title)
+        stopwords = {"그리고", "하지만", "영상", "정리"}
+        return [token for token in tokens if token not in stopwords][:8]
diff --git a/shorts_growth_agent/backend/tests/test_trend_scoring.py b/shorts_growth_agent/backend/tests/test_trend_scoring.py
new file mode 100644
index 00000000..53fe4e6f
--- /dev/null
+++ b/shorts_growth_agent/backend/tests/test_trend_scoring.py
@@ -0,0 +1,63 @@
+# 트렌드 스코어링 동작을 검증하는 테스트 모음
+from datetime import datetime, timedelta, timezone
+
+from shorts_agent.adapters.youtube import YouTubeVideoSignal
+from shorts_agent.services.trend_scoring import TrendScoringService
+
+
+def test_rank_prefers_fast_rising_recent_video():
+    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
+    signals = [
+        YouTubeVideoSignal(
+            "old",
+            "오래된 인기",
+            "24",
+            "A",
+            now - timedelta(days=5),
+            500_000,
+            1_000,
+        ),
+        YouTubeVideoSignal(
+            "new",
+            "빠른 상승",
+            "24",
+            "B",
+            now - timedelta(hours=2),
+            90_000,
+            900,
+        ),
+    ]
+
+    ranked = TrendScoringService().rank(signals, now)
+
+    assert ranked[0].video_id == "new"
+    assert ranked[0].views_per_hour > ranked[1].views_per_hour
+
+
+def test_rank_extracts_keyword_candidates_from_titles():
+    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
+    signals = [
+        YouTubeVideoSignal(
+            "a",
+            "신작 게임 업데이트 반응 폭발",
+            "20",
+            "A",
+            now - timedelta(hours=1),
+            10_000,
+            100,
+        ),
+        YouTubeVideoSignal(
+            "b",
+            "게임 업데이트 보상 정리",
+            "20",
+            "B",
+            now - timedelta(hours=2),
+            9_000,
+            90,
+        ),
+    ]
+
+    ranked = TrendScoringService().rank(signals, now)
+
+    assert "게임" in ranked[0].keyword_candidates
+    assert "업데이트" in ranked[0].keyword_candidates
