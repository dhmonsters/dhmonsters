diff --git a/shorts_growth_agent/README.md b/shorts_growth_agent/README.md
index 59eff849..ae25d161 100644
--- a/shorts_growth_agent/README.md
+++ b/shorts_growth_agent/README.md
@@ -1,3 +1,30 @@
 # Shorts Growth Agent
 
-백엔드 기반 골격과 헬스 체크 API를 위한 프로젝트입니다.
+쇼츠 기획/운영 API 중심의 테스트 프로젝트입니다.
+
+## Development
+
+### Backend install and run
+
+- `cd C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\backend`
+- `python -m venv .venv` (첫 세팅만)
+- `.\.venv\Scripts\python.exe -m pip install -e ".[dev]"`
+- `.\.venv\Scripts\python.exe -m uvicorn shorts_agent.main:app --reload`
+
+### Frontend install and run
+
+- `cd C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend`
+- `npm.cmd install`
+- `npm.cmd run dev`
+- `npm.cmd run build`
+
+### Verification commands
+
+- Backend smoke test: `.\.venv\Scripts\python.exe -m pytest tests/test_mvp_flow.py -q`
+- Backend 전체 테스트: `.\.venv\Scripts\python.exe -m pytest -q`
+- Frontend 테스트: `cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd test"`
+- Frontend 빌드: `cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd run build"`
+
+Temp 권한 이슈가 나면 백엔드 폴더에서 아래처럼 로컬 임시 폴더를 지정합니다.
+
+- `New-Item -ItemType Directory -Force .\.pytest_tmp | Out-Null; $env:TMP=(Resolve-Path .\.pytest_tmp).Path; $env:TEMP=(Resolve-Path .\.pytest_tmp).Path; .\.venv\Scripts\python.exe -m pytest -q`
diff --git a/shorts_growth_agent/backend/tests/test_mvp_flow.py b/shorts_growth_agent/backend/tests/test_mvp_flow.py
new file mode 100644
index 00000000..5fac08ee
--- /dev/null
+++ b/shorts_growth_agent/backend/tests/test_mvp_flow.py
@@ -0,0 +1,49 @@
+# MVP 엔드투엔드 파이프라인 스모크 테스트입니다.
+from pathlib import Path
+
+from shorts_agent.services.performance_analysis import PerformanceAnalysisService, PerformancePoint
+from shorts_agent.services.render_manifest import FfmpegCommandBuilder, RenderManifest, RenderScene
+from shorts_agent.services.script_planner import HarnessConfig, ScriptPlanner
+from shorts_agent.services.source_recommender import SourceRecommender
+from shorts_agent.services.subtitle_sync import SubtitleSyncService
+
+
+def test_mvp_pipeline_smoke():
+    harness = HarnessConfig(
+        name="뉴스+실험",
+        tone="톤다운",
+        hook_strength="강렬",
+        target_seconds=45,
+        forbidden_terms=["금지어", "100%"],
+    )
+    plan = ScriptPlanner().generate("요즘 화제", "뉴스", harness)
+    subtitles = SubtitleSyncService().sync([scene.subtitle for scene in plan.scenes], 45000)
+    source = SourceRecommender().recommend("뉴스", plan.scenes[1].index, plan.scenes[1].source_type)
+    first_subtitle = subtitles[0]
+    manifest = RenderManifest(
+        width=1080,
+        height=1920,
+        scenes=[
+            RenderScene(
+                Path("scene1.png"),
+                first_subtitle.end_ms - first_subtitle.start_ms,
+                first_subtitle.text,
+                plan.scenes[0].motion_type,
+            )
+        ],
+        audio_path=Path("voice.wav"),
+        output_path=Path("out.mp4"),
+    )
+    command = FfmpegCommandBuilder("ffmpeg").build(manifest)
+    report = PerformanceAnalysisService().analyze(
+        [
+            PerformancePoint(60, views=100, impressions=3000, ctr=0.02, retention_3s=0.7),
+            PerformancePoint(240, views=130, impressions=9000, ctr=0.014, retention_3s=0.68),
+        ],
+        {"source_type": source.source_type},
+    )
+
+    assert plan.scenes
+    assert subtitles
+    assert command[0] == "ffmpeg"
+    assert report.cause_candidates[0].code == "title_thumbnail_mismatch"
