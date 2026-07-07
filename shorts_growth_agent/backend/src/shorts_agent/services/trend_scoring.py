# 검색 타이밍별 트렌드 점수를 계산해 정렬용 모델을 생성한다.
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
