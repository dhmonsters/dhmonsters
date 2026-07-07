# 트렌드 스코어링 동작을 검증하는 테스트 모음
from datetime import datetime, timedelta, timezone

from shorts_agent.adapters.youtube import YouTubeVideoSignal
from shorts_agent.services.trend_scoring import TrendScoringService


def test_rank_prefers_fast_rising_recent_video():
    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    signals = [
        YouTubeVideoSignal(
            "old",
            "오래된 인기",
            "24",
            "A",
            now - timedelta(days=5),
            500_000,
            1_000,
        ),
        YouTubeVideoSignal(
            "new",
            "빠른 상승",
            "24",
            "B",
            now - timedelta(hours=2),
            90_000,
            900,
        ),
    ]

    ranked = TrendScoringService().rank(signals, now)

    assert ranked[0].video_id == "new"
    assert ranked[0].views_per_hour > ranked[1].views_per_hour


def test_rank_extracts_keyword_candidates_from_titles():
    now = datetime(2026, 7, 8, 12, 0, tzinfo=timezone.utc)
    signals = [
        YouTubeVideoSignal(
            "a",
            "신작 게임 업데이트 반응 폭발",
            "20",
            "A",
            now - timedelta(hours=1),
            10_000,
            100,
        ),
        YouTubeVideoSignal(
            "b",
            "게임 업데이트 보상 정리",
            "20",
            "B",
            now - timedelta(hours=2),
            9_000,
            90,
        ),
    ]

    ranked = TrendScoringService().rank(signals, now)

    assert "게임" in ranked[0].keyword_candidates
    assert "업데이트" in ranked[0].keyword_candidates
