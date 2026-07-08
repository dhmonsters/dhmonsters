# 한국 인기 영상 후보 샘플 데이터를 제공합니다.
from datetime import datetime, timedelta, timezone

from shorts_agent.adapters.youtube import YouTubeVideoSignal


def get_sample_trend_signals(now: datetime | None = None) -> list[YouTubeVideoSignal]:
    base_time = now or datetime.now(timezone.utc)
    return [
        YouTubeVideoSignal(
            video_id="sample-game-001",
            title="신작 게임 업데이트 보상 정리와 반응",
            category_id="20",
            channel_title="게임 이슈 연구소",
            published_at=base_time - timedelta(hours=3),
            view_count=320_000,
            like_count=9_800,
            thumbnail_url="",
        ),
        YouTubeVideoSignal(
            video_id="sample-game-002",
            title="모바일 게임 쿠폰 이벤트 오늘 꼭 확인",
            category_id="20",
            channel_title="빠른 게임 뉴스",
            published_at=base_time - timedelta(hours=5),
            view_count=210_000,
            like_count=5_200,
            thumbnail_url="",
        ),
        YouTubeVideoSignal(
            video_id="sample-news-001",
            title="오늘 한국에서 화제 된 생활 뉴스 세 가지",
            category_id="25",
            channel_title="요약 뉴스룸",
            published_at=base_time - timedelta(hours=2),
            view_count=480_000,
            like_count=7_400,
            thumbnail_url="",
        ),
        YouTubeVideoSignal(
            video_id="sample-shopping-001",
            title="쿠팡 인기템 실제 후기와 할인 포인트",
            category_id="26",
            channel_title="쇼핑 실험실",
            published_at=base_time - timedelta(hours=4),
            view_count=180_000,
            like_count=4_100,
            thumbnail_url="",
        ),
        YouTubeVideoSignal(
            video_id="sample-blog-001",
            title="블로그에서 터진 다이어트 루틴 핵심만 요약",
            category_id="24",
            channel_title="트렌드 요약소",
            published_at=base_time - timedelta(hours=6),
            view_count=260_000,
            like_count=6_300,
            thumbnail_url="",
        ),
    ]
