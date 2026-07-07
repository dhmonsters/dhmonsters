# source_type 추천 규칙 검증 테스트입니다.
from shorts_agent.services.source_recommender import SourceRecommender


def test_game_clip_hint_recommends_clip_candidate():
    result = SourceRecommender().recommend("게임", 2, "clip_candidate")

    assert result.source_type == "clip_candidate"
    assert result.requires_user_review is True


def test_info_category_defaults_to_ai_image():
    result = SourceRecommender().recommend("정보형", 1, "ai_image")

    assert result.source_type == "ai_image"
    assert result.requires_user_review is False
