diff --git a/shorts_growth_agent/backend/src/shorts_agent/api/harnesses.py b/shorts_growth_agent/backend/src/shorts_agent/api/harnesses.py
new file mode 100644
index 00000000..97b411e7
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/api/harnesses.py
@@ -0,0 +1,24 @@
+# 하네스 기본값을 제공하는 API 라우터입니다.
+from fastapi import APIRouter
+
+
+router = APIRouter()
+
+
+@router.get("/harnesses/default")
+def get_default_harness():
+    return {
+        "name": "정보+후킹형",
+        "mode": "basic",
+        "system_prompt": "빠르고 정확한 한국어 쇼츠 작가로서 첫 3초 후킹과 명확한 정보 전달을 우선한다.",
+        "output_schema": {
+            "scene": "number",
+            "subtitle": "string",
+            "voice_text": "string",
+            "image_prompt": "string",
+            "source_type": "string",
+            "motion_type": "string",
+            "sound_effect": "string",
+        },
+        "forbidden_terms": ["무조건", "100%", "확정"],
+    }
diff --git a/shorts_growth_agent/backend/src/shorts_agent/repositories/harness_repository.py b/shorts_growth_agent/backend/src/shorts_agent/repositories/harness_repository.py
new file mode 100644
index 00000000..77260c93
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/repositories/harness_repository.py
@@ -0,0 +1,30 @@
+# Shorts용 하네스 기본값을 생성하고 읽는 저장소입니다.
+from sqlalchemy.orm import Session
+
+from shorts_agent.models import ScriptHarness
+
+
+class HarnessRepository:
+    def __init__(self, session: Session):
+        self.session = session
+
+    def create_default_harness(self) -> ScriptHarness:
+        harness = ScriptHarness(
+            name="정보+후킹형",
+            mode="basic",
+            system_prompt="빠르고 정확한 한국어 쇼츠 작가로서 첫 3초 후킹과 명확한 정보 전달을 우선한다.",
+            output_schema={
+                "scene": "number",
+                "subtitle": "string",
+                "voice_text": "string",
+                "image_prompt": "string",
+                "source_type": "string",
+                "motion_type": "string",
+                "sound_effect": "string",
+            },
+            forbidden_terms=["무조건", "100%", "확정"],
+        )
+        self.session.add(harness)
+        self.session.commit()
+        self.session.refresh(harness)
+        return harness
diff --git a/shorts_growth_agent/backend/src/shorts_agent/services/script_planner.py b/shorts_growth_agent/backend/src/shorts_agent/services/script_planner.py
new file mode 100644
index 00000000..edea0c81
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/services/script_planner.py
@@ -0,0 +1,80 @@
+﻿# Shorts 숏폼 장면 계획을 생성하는 서비스입니다.
+from dataclasses import dataclass
+
+
+@dataclass(frozen=True)
+class HarnessConfig:
+    name: str
+    tone: str
+    hook_strength: str
+    target_seconds: int
+    forbidden_terms: list[str]
+
+
+@dataclass(frozen=True)
+class PlannedScene:
+    index: int
+    subtitle: str
+    voice_text: str
+    image_prompt: str
+    source_type: str
+    motion_type: str
+    sound_effect: str
+    duration_ms: int
+
+
+@dataclass(frozen=True)
+class ScriptPlan:
+    keyword: str
+    category: str
+    title_candidate: str
+    scenes: list[PlannedScene]
+
+
+class ScriptPlanner:
+    def generate(self, keyword: str, category: str, harness: HarnessConfig) -> ScriptPlan:
+        scene_count = 5 if harness.target_seconds <= 45 else 7
+        duration_ms = int(harness.target_seconds * 1000 / scene_count)
+        cleaned_keyword = self._remove_forbidden(keyword, harness.forbidden_terms)
+        cleaned_category = self._remove_forbidden(category, harness.forbidden_terms)
+        templates = [
+            f"지금 {cleaned_keyword}, 왜 갑자기 뜨는 걸까요?",
+            f"핵심은 세 가지입니다.",
+            f"첫째, 사람들이 반응한 포인트가 분명합니다.",
+            f"둘째, {cleaned_category} 흐름과 바로 연결됩니다.",
+            f"마지막으로 지금 확인해야 할 부분입니다.",
+        ]
+        scenes = []
+        for index, subtitle in enumerate(templates[:scene_count], start=1):
+            cleaned = self._remove_forbidden(subtitle, harness.forbidden_terms)
+            image_prompt = self._remove_forbidden(
+                f"{cleaned_category} 주제의 세로형 쇼츠 이미지, 키워드: {cleaned_keyword}, 장면 {index}",
+                harness.forbidden_terms,
+            )
+            scenes.append(
+                PlannedScene(
+                    index=index,
+                    subtitle=cleaned,
+                    voice_text=cleaned,
+                    image_prompt=image_prompt,
+                    source_type=self._source_type(category, index),
+                    motion_type="zoom_in" if index == 1 else "shake" if index == 3 else "none",
+                    sound_effect="hit" if index == 1 else "whoosh" if index == 2 else "none",
+                    duration_ms=duration_ms,
+                )
+            )
+        title_candidate = self._remove_forbidden(f"{cleaned_keyword} 핵심 정리", harness.forbidden_terms)
+        return ScriptPlan(keyword=keyword, category=category, title_candidate=title_candidate, scenes=scenes)
+
+    def _remove_forbidden(self, text: str, forbidden_terms: list[str]) -> str:
+        text = text.strip()
+        for term in forbidden_terms:
+            text = text.replace(term, "")
+        return " ".join(text.split())
+
+    def _source_type(self, category: str, index: int) -> str:
+        if category == "게임" and index in {2, 3}:
+            return "clip_candidate"
+        if category in {"뉴스", "이슈"} and index == 1:
+            return "reference_image"
+        return "ai_image"
diff --git a/shorts_growth_agent/backend/tests/test_script_planner.py b/shorts_growth_agent/backend/tests/test_script_planner.py
new file mode 100644
index 00000000..130e9d4f
--- /dev/null
+++ b/shorts_growth_agent/backend/tests/test_script_planner.py
@@ -0,0 +1,69 @@
+# ScriptPlanner 설계 동작을 검증합니다.
+from shorts_agent.services.script_planner import HarnessConfig, ScriptPlanner
+
+
+def _default_harness():
+    return HarnessConfig(
+        name="정보+후킹형",
+        tone="빠른 정보형",
+        hook_strength="강함",
+        target_seconds=45,
+        forbidden_terms=["무조건", "100%"],
+    )
+
+
+def _contains_forbidden(text: str, forbidden_terms: list[str]) -> bool:
+    return any(term in text for term in forbidden_terms)
+
+
+def test_generate_filters_forbidden_terms_from_user_facing_outputs():
+    harness = HarnessConfig(
+        name="정보+후킹형",
+        tone="빠른 정보형",
+        hook_strength="강함",
+        target_seconds=45,
+        forbidden_terms=["무조건", "100%"],
+    )
+
+    plan = ScriptPlanner().generate(
+        keyword="무조건 게임 업데이트",
+        category="게임",
+        harness=harness,
+    )
+
+    flattened_user_outputs = " ".join(
+        [
+            plan.title_candidate,
+            *(scene.subtitle for scene in plan.scenes),
+            *(scene.voice_text for scene in plan.scenes),
+            *(scene.image_prompt for scene in plan.scenes),
+        ]
+    )
+    assert not _contains_forbidden(flattened_user_outputs, harness.forbidden_terms)
+
+
+def test_generate_filters_forbidden_terms_from_category_path():
+    harness = _default_harness()
+    plan = ScriptPlanner().generate(keyword="게임 업데이트", category="무조건 게임", harness=harness)
+
+    flattened_user_outputs = " ".join(
+        [
+            plan.title_candidate,
+            *(scene.subtitle for scene in plan.scenes),
+            *(scene.voice_text for scene in plan.scenes),
+            *(scene.image_prompt for scene in plan.scenes),
+        ]
+    )
+    assert not _contains_forbidden(flattened_user_outputs, harness.forbidden_terms)
+    assert plan.scenes[3].subtitle == "둘째, 게임 흐름과 바로 연결됩니다."
+    assert plan.scenes[3].image_prompt == "게임 주제의 세로형 쇼츠 이미지, 키워드: 게임 업데이트, 장면 4"
+
+
+def test_generate_returns_structured_scene_plan():
+    harness = _default_harness()
+    plan = ScriptPlanner().generate(keyword="게임 업데이트", category="게임", harness=harness)
+
+    assert plan.keyword == "게임 업데이트"
+    assert 3 <= len(plan.scenes) <= 8
+    assert plan.scenes[0].motion_type in {"zoom_in", "shake", "bounce", "none"}
+    assert not _contains_forbidden(" ".join(scene.subtitle for scene in plan.scenes), harness.forbidden_terms)
