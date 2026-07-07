diff --git a/shorts_growth_agent/backend/src/shorts_agent/adapters/image.py b/shorts_growth_agent/backend/src/shorts_agent/adapters/image.py
new file mode 100644
index 00000000..a1287867
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/adapters/image.py
@@ -0,0 +1,14 @@
+# AI 이미지 생성을 위한 어댑터 인터페이스입니다.
+from dataclasses import dataclass
+from pathlib import Path
+
+
+@dataclass(frozen=True)
+class ImageResult:
+    path: Path
+    prompt: str
+
+
+class ImageAdapter:
+    def generate(self, prompt: str, output_path: Path) -> ImageResult:
+        raise NotImplementedError
diff --git a/shorts_growth_agent/backend/src/shorts_agent/adapters/meme.py b/shorts_growth_agent/backend/src/shorts_agent/adapters/meme.py
new file mode 100644
index 00000000..cbf55027
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/adapters/meme.py
@@ -0,0 +1,15 @@
+# Meme 라이브러리를 검색하는 어댑터 인터페이스입니다.
+from dataclasses import dataclass
+from pathlib import Path
+
+
+@dataclass(frozen=True)
+class MemeAsset:
+    path: Path
+    tags: list[str]
+    source: str
+
+
+class MemeAdapter:
+    def search(self, query: str, limit: int = 10) -> list[MemeAsset]:
+        return []
diff --git a/shorts_growth_agent/backend/src/shorts_agent/services/source_recommender.py b/shorts_growth_agent/backend/src/shorts_agent/services/source_recommender.py
new file mode 100644
index 00000000..e7ce6f05
--- /dev/null
+++ b/shorts_growth_agent/backend/src/shorts_agent/services/source_recommender.py
@@ -0,0 +1,32 @@
+# 장면별 소스를 추천하고 사용자 검토 필요 여부를 판단합니다.
+from dataclasses import dataclass
+
+
+@dataclass(frozen=True)
+class SourceRecommendation:
+    source_type: str
+    reason: str
+    requires_user_review: bool
+
+
+class SourceRecommender:
+    def recommend(self, category: str, scene_index: int, source_hint: str) -> SourceRecommendation:
+        if source_hint == "clip_candidate":
+            return SourceRecommendation(
+                source_type="clip_candidate",
+                reason="실제 장면이 있으면 이해가 빠른 장면입니다. 사용자가 구간과 사용 가능 여부를 확인해야 합니다.",
+                requires_user_review=True,
+            )
+        if category in {"뉴스", "이슈"} and scene_index == 1:
+            return SourceRecommendation(
+                "reference_image",
+                "첫 장면은 실제 자료 이미지가 신뢰감을 줍니다.",
+                True,
+            )
+        if category == "게임" and scene_index >= 3:
+            return SourceRecommendation(
+                "meme",
+                "반응 장면에는 밈 이미지가 리듬을 만듭니다.",
+                False,
+            )
+        return SourceRecommendation("ai_image", "기본 장면은 AI 이미지로 안정적으로 구성합니다.", False)
diff --git a/shorts_growth_agent/backend/tests/test_source_recommender.py b/shorts_growth_agent/backend/tests/test_source_recommender.py
new file mode 100644
index 00000000..6a156d3c
--- /dev/null
+++ b/shorts_growth_agent/backend/tests/test_source_recommender.py
@@ -0,0 +1,16 @@
+﻿# source_type 추천 규칙 검증 테스트입니다.
+from shorts_agent.services.source_recommender import SourceRecommender
+
+
+def test_game_clip_hint_recommends_clip_candidate():
+    result = SourceRecommender().recommend("게임", 2, "clip_candidate")
+
+    assert result.source_type == "clip_candidate"
+    assert result.requires_user_review is True
+
+
+def test_info_category_defaults_to_ai_image():
+    result = SourceRecommender().recommend("정보형", 1, "ai_image")
+
+    assert result.source_type == "ai_image"
+    assert result.requires_user_review is False
