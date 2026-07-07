# YouTube 인기 영상 신호를 API 응답에서 파싱해 도메인 신호로 변환한다.
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
