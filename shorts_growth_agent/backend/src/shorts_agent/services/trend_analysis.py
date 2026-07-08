# 트렌드 후보를 쇼츠 제작 관점으로 분석합니다.
from dataclasses import dataclass


@dataclass(frozen=True)
class TrendCandidateInput:
    video_id: str
    title: str
    category_id: str
    channel_title: str
    view_count: int
    views_per_hour: float
    score: float
    keyword_candidates: list[str]
    thumbnail_url: str = ""


@dataclass(frozen=True)
class RecommendedHarness:
    tone: str
    hook_strength: str
    target_seconds: int
    forbidden_terms: list[str]


@dataclass(frozen=True)
class TrendAnalysis:
    video_id: str
    title: str
    summary: str
    production_angles: list[str]
    risk_level: str
    risk_notes: list[str]
    script_seed: str
    recommended_harness: RecommendedHarness


class TrendAnalysisService:
    def analyze(self, candidate: TrendCandidateInput) -> TrendAnalysis:
        keywords = candidate.keyword_candidates or [candidate.title]
        primary_keyword = keywords[0]
        category_label = self._category_label(candidate.category_id)
        production_angles = [
            f"{primary_keyword} 핵심만 30초 안에 요약",
            f"{category_label} 시청자가 궁금해할 반응 포인트 비교",
            f"지금 확인해야 할 체크리스트형 쇼츠",
        ]
        risk_level = "주의" if candidate.views_per_hour > 100_000 else "낮음"
        risk_notes = [
            "원본 영상 장면을 자동으로 가져오지 말고 직접 확인한 소스만 사용",
            "제목과 썸네일 표현은 과장보다 검증 가능한 문장 우선",
        ]
        if candidate.category_id == "25":
            risk_notes.append("뉴스 소재는 출처와 날짜를 화면 또는 설명에 남기는 편이 안전")
        return TrendAnalysis(
            video_id=candidate.video_id,
            title=candidate.title,
            summary=f"{candidate.channel_title}의 '{candidate.title}' 후보를 {category_label} 쇼츠 소재로 분석했습니다.",
            production_angles=production_angles,
            risk_level=risk_level,
            risk_notes=risk_notes,
            script_seed=" ".join(keywords[:3]),
            recommended_harness=RecommendedHarness(
                tone="명료",
                hook_strength="강함",
                target_seconds=45 if candidate.category_id != "20" else 30,
                forbidden_terms=["100%", "무조건", "충격"],
            ),
        )

    def _category_label(self, category_id: str) -> str:
        return {
            "20": "게임",
            "24": "엔터·블로그",
            "25": "뉴스",
            "26": "쇼핑·생활",
        }.get(category_id, "트렌드")
