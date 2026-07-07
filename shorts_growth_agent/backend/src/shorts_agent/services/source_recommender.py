# 장면별 소스를 추천하고 사용자 검토 필요 여부를 판단합니다.
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRecommendation:
    source_type: str
    reason: str
    requires_user_review: bool


class SourceRecommender:
    def recommend(self, category: str, scene_index: int, source_hint: str) -> SourceRecommendation:
        if source_hint == "clip_candidate":
            return SourceRecommendation(
                source_type="clip_candidate",
                reason="실제 장면이 있으면 이해가 빠른 장면입니다. 사용자가 구간과 사용 가능 여부를 확인해야 합니다.",
                requires_user_review=True,
            )
        if category in {"뉴스", "이슈"} and scene_index == 1:
            return SourceRecommendation(
                "reference_image",
                "첫 장면은 실제 자료 이미지가 신뢰감을 줍니다.",
                True,
            )
        if category == "게임" and scene_index >= 3:
            return SourceRecommendation(
                "meme",
                "반응 장면에는 밈 이미지가 리듬을 만듭니다.",
                False,
            )
        return SourceRecommendation("ai_image", "기본 장면은 AI 이미지로 안정적으로 구성합니다.", False)
