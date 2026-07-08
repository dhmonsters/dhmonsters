# Shorts 숏폼 장면 계획을 생성하는 서비스입니다.
from dataclasses import dataclass


@dataclass(frozen=True)
class HarnessConfig:
    name: str
    tone: str
    hook_strength: str
    target_seconds: int
    forbidden_terms: list[str]
    custom_prompt: str = ""


@dataclass(frozen=True)
class PlannedScene:
    index: int
    subtitle: str
    voice_text: str
    image_prompt: str
    source_type: str
    motion_type: str
    sound_effect: str
    duration_ms: int


@dataclass(frozen=True)
class ScriptPlan:
    keyword: str
    category: str
    title_candidate: str
    scenes: list[PlannedScene]


class ScriptPlanner:
    def generate(
        self,
        keyword: str,
        category: str,
        harness: HarnessConfig,
        primary_angle: str = "",
        script_seed: str = "",
    ) -> ScriptPlan:
        scene_count = 5 if harness.target_seconds <= 45 else 7
        duration_ms = int(harness.target_seconds * 1000 / scene_count)
        seed = script_seed or keyword
        cleaned_keyword = self._remove_forbidden(seed, harness.forbidden_terms)
        cleaned_category = self._remove_forbidden(category, harness.forbidden_terms)
        cleaned_angle = self._remove_forbidden(primary_angle, harness.forbidden_terms)
        opening = (
            f"{cleaned_angle}: {cleaned_keyword}, 지금 봐야 할 포인트입니다."
            if cleaned_angle
            else f"지금 {cleaned_keyword}, 왜 갑자기 뜨는 걸까요?"
        )
        templates = [
            opening,
            f"핵심은 세 가지입니다.",
            f"첫째, 사람들이 반응한 포인트가 분명합니다.",
            f"둘째, {cleaned_category} 흐름과 바로 연결됩니다.",
            f"마지막으로 지금 확인해야 할 부분입니다.",
        ]
        if harness.custom_prompt:
            templates[0] = self._remove_forbidden(
                f"{harness.custom_prompt}: {cleaned_keyword}",
                harness.forbidden_terms,
            )
        scenes = []
        for index, subtitle in enumerate(templates[:scene_count], start=1):
            cleaned = self._remove_forbidden(subtitle, harness.forbidden_terms)
            image_prompt = self._remove_forbidden(
                f"{cleaned_category} 주제의 세로형 쇼츠 이미지, 키워드: {cleaned_keyword}, 장면 {index}",
                harness.forbidden_terms,
            )
            scenes.append(
                PlannedScene(
                    index=index,
                    subtitle=cleaned,
                    voice_text=cleaned,
                    image_prompt=image_prompt,
                    source_type=self._source_type(category, index),
                    motion_type="zoom_in" if index == 1 else "shake" if index == 3 else "none",
                    sound_effect="hit" if index == 1 else "whoosh" if index == 2 else "none",
                    duration_ms=duration_ms,
                )
            )
        title_candidate = self._remove_forbidden(f"{cleaned_keyword} 핵심 정리", harness.forbidden_terms)
        return ScriptPlan(keyword=keyword, category=category, title_candidate=title_candidate, scenes=scenes)

    def _remove_forbidden(self, text: str, forbidden_terms: list[str]) -> str:
        text = text.strip()
        for term in forbidden_terms:
            text = text.replace(term, "")
        return " ".join(text.split())

    def _source_type(self, category: str, index: int) -> str:
        if category == "게임" and index in {2, 3}:
            return "clip_candidate"
        if category in {"뉴스", "이슈"} and index == 1:
            return "reference_image"
        return "ai_image"
