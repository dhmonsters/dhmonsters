# Task 13 Brief: End-To-End MVP Smoke Test

## Goal

Verify one local MVP pipeline end to end and document how to run the backend and frontend.

## Scope

Modify only these files unless a test failure proves a directly related fix is required.

- `shorts_growth_agent/backend/tests/test_mvp_flow.py`
- `shorts_growth_agent/README.md`
- `.superpowers/sdd/task-13-report.md`

Do not add real YouTube, real TTS, real image generation, meme MCP, upload, analytics API, or external network calls.

## Required Behavior

The smoke test must connect these existing services in one flow:

1. Generate a script plan.
2. Sync subtitles.
3. Recommend a source for a planned scene.
4. Build an FFmpeg command from a render manifest.
5. Analyze performance snapshots.

Important: Task 8 made performance analysis time-series based. Use at least two sufficiently exposed low-CTR snapshots when expecting `title_thumbnail_mismatch`.

## Test First

Create `shorts_growth_agent/backend/tests/test_mvp_flow.py`.

```python
# MVP 전체 파이프라인이 한 번에 연결되는지 검증한다.
from pathlib import Path

from shorts_agent.services.performance_analysis import PerformanceAnalysisService, PerformancePoint
from shorts_agent.services.render_manifest import FfmpegCommandBuilder, RenderManifest, RenderScene
from shorts_agent.services.script_planner import HarnessConfig, ScriptPlanner
from shorts_agent.services.source_recommender import SourceRecommender
from shorts_agent.services.subtitle_sync import SubtitleSyncService


def test_mvp_pipeline_smoke():
    harness = HarnessConfig("정보+후킹형", "빠른 정보형", "강함", 45, ["무조건"])
    plan = ScriptPlanner().generate("게임 업데이트", "게임", harness)
    subtitles = SubtitleSyncService().sync([scene.subtitle for scene in plan.scenes], 45000)
    source = SourceRecommender().recommend("게임", plan.scenes[1].index, plan.scenes[1].source_type)
    manifest = RenderManifest(
        width=1080,
        height=1920,
        scenes=[RenderScene(Path("scene1.png"), subtitles[0].end_ms, subtitles[0].text, "zoom_in")],
        audio_path=Path("voice.wav"),
        output_path=Path("out.mp4"),
    )
    command = FfmpegCommandBuilder("ffmpeg").build(manifest)
    report = PerformanceAnalysisService().analyze(
        [
            PerformancePoint(60, views=100, impressions=5000, ctr=0.02, retention_3s=0.7),
            PerformancePoint(360, views=130, impressions=9000, ctr=0.014, retention_3s=0.68),
        ],
        {"source_type": source.source_type},
    )

    assert plan.scenes
    assert subtitles
    assert command[0] == "ffmpeg"
    assert report.cause_candidates[0].code == "title_thumbnail_mismatch"
```

Run it after creating the test.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_mvp_flow.py -q
```

This may pass immediately because all underlying services already exist. If it passes immediately, record that this is a smoke integration test over existing behavior, then continue.

## README Update

Update `shorts_growth_agent/README.md` with development commands.

Use Windows-friendly commands while also keeping the intent clear.

Required sections:

- `## Development`
- Backend install and run.
- Frontend install and run.
- Verification commands.

Mention the local Windows notes:

- Backend tests use `.\.venv\Scripts\python.exe`.
- Frontend commands should use `npm.cmd` in PowerShell.
- If Vitest scans outside the workspace, use the existing `subst X:` pattern.

## Verification

Run these commands.

Backend:

```powershell
cd shorts_growth_agent/backend
.\.venv\Scripts\python.exe -m pytest tests/test_mvp_flow.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

Frontend from workspace root:

```powershell
cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd test"
cmd /c "subst X: C:\Users\PC\Desktop\02_work\05_AI\shorts_growth_agent\frontend && X: && npm.cmd run build"
```

Report test output and changed files in `.superpowers/sdd/task-13-report.md`.
