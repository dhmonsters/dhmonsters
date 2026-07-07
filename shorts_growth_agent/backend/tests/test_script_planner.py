# ScriptPlanner 설계 동작을 검증합니다.
from shorts_agent.services.script_planner import HarnessConfig, ScriptPlanner


def _default_harness():
    return HarnessConfig(
        name="정보+후킹형",
        tone="빠른 정보형",
        hook_strength="강함",
        target_seconds=45,
        forbidden_terms=["무조건", "100%"],
    )


def _contains_forbidden(text: str, forbidden_terms: list[str]) -> bool:
    return any(term in text for term in forbidden_terms)


def test_generate_filters_forbidden_terms_from_user_facing_outputs():
    harness = HarnessConfig(
        name="정보+후킹형",
        tone="빠른 정보형",
        hook_strength="강함",
        target_seconds=45,
        forbidden_terms=["무조건", "100%"],
    )

    plan = ScriptPlanner().generate(
        keyword="무조건 게임 업데이트",
        category="게임",
        harness=harness,
    )

    flattened_user_outputs = " ".join(
        [
            plan.title_candidate,
            *(scene.subtitle for scene in plan.scenes),
            *(scene.voice_text for scene in plan.scenes),
            *(scene.image_prompt for scene in plan.scenes),
        ]
    )
    assert not _contains_forbidden(flattened_user_outputs, harness.forbidden_terms)


def test_generate_filters_forbidden_terms_from_category_path():
    harness = _default_harness()
    plan = ScriptPlanner().generate(keyword="게임 업데이트", category="무조건 게임", harness=harness)

    flattened_user_outputs = " ".join(
        [
            plan.title_candidate,
            *(scene.subtitle for scene in plan.scenes),
            *(scene.voice_text for scene in plan.scenes),
            *(scene.image_prompt for scene in plan.scenes),
        ]
    )
    assert not _contains_forbidden(flattened_user_outputs, harness.forbidden_terms)
    assert plan.scenes[3].subtitle == "둘째, 게임 흐름과 바로 연결됩니다."
    assert plan.scenes[3].image_prompt == "게임 주제의 세로형 쇼츠 이미지, 키워드: 게임 업데이트, 장면 4"


def test_generate_returns_structured_scene_plan():
    harness = _default_harness()
    plan = ScriptPlanner().generate(keyword="게임 업데이트", category="게임", harness=harness)

    assert plan.keyword == "게임 업데이트"
    assert 3 <= len(plan.scenes) <= 8
    assert plan.scenes[0].motion_type in {"zoom_in", "shake", "bounce", "none"}
    assert not _contains_forbidden(" ".join(scene.subtitle for scene in plan.scenes), harness.forbidden_terms)
