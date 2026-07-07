# Task 7 Brief: Render Manifest And FFmpeg Command Builder

## Goal

Add a render manifest and FFmpeg command builder that can produce a 9:16 MP4 command preview for the Shorts pipeline.

## Global Constraints

- User-facing text and reports should be Korean.
- Work only inside the assigned files under `shorts_growth_agent`, plus write your report file at `.superpowers/sdd/task-7-report.md`.
- Do not touch `maple_bot`, frontend files, or unrelated root files.
- Every new source file must start with a one-line Korean comment explaining its role.
- Follow TDD. Write tests first, run them and observe failure, then implement the minimum code, then rerun tests.
- Do not run `git add` or `git commit`. The parent agent will commit because this workspace blocks the normal Git index.
- Use the existing backend virtual environment command when running tests: `.\.venv\Scripts\python.exe -m pytest ...`.

## Existing Context

Tasks 4-6 provide script scenes, TTS/subtitle timing, and scene source recommendations. This task prepares a render command manifest but does not execute FFmpeg.

## Files To Create

- `shorts_growth_agent/backend/src/shorts_agent/services/render_manifest.py`
- `shorts_growth_agent/backend/src/shorts_agent/api/render.py`
- `shorts_growth_agent/backend/tests/test_render_manifest.py`

## Required Interfaces

- `RenderManifest(width=1080, height=1920, scenes: list[RenderScene], audio_path, output_path)`.
- `FfmpegCommandBuilder.build(manifest: RenderManifest) -> list[str]`.

## Required Test

Create `shorts_growth_agent/backend/tests/test_render_manifest.py`.

```python
# 9:16 렌더 매니페스트와 FFmpeg 명령 생성을 검증한다.
from pathlib import Path

from shorts_agent.services.render_manifest import FfmpegCommandBuilder, RenderManifest, RenderScene


def test_ffmpeg_command_contains_vertical_output_size():
    manifest = RenderManifest(
        width=1080,
        height=1920,
        scenes=[RenderScene(asset_path=Path("scene1.png"), duration_ms=2000, subtitle="첫 문장", motion_type="zoom_in")],
        audio_path=Path("voice.wav"),
        output_path=Path("out.mp4"),
    )

    command = FfmpegCommandBuilder(ffmpeg_path="ffmpeg").build(manifest)

    assert command[0] == "ffmpeg"
    assert "scale=1080:1920" in " ".join(command)
    assert str(manifest.output_path) in command
```

## Required Render Manifest Service

Implement `shorts_growth_agent/backend/src/shorts_agent/services/render_manifest.py`.

```python
# 쇼츠 MP4 렌더링에 필요한 장면 매니페스트와 FFmpeg 명령을 만든다.
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RenderScene:
    asset_path: Path
    duration_ms: int
    subtitle: str
    motion_type: str


@dataclass(frozen=True)
class RenderManifest:
    width: int
    height: int
    scenes: list[RenderScene]
    audio_path: Path
    output_path: Path


class FfmpegCommandBuilder:
    def __init__(self, ffmpeg_path: str):
        self.ffmpeg_path = ffmpeg_path

    def build(self, manifest: RenderManifest) -> list[str]:
        first_scene = manifest.scenes[0]
        vf = f"scale={manifest.width}:{manifest.height}:force_original_aspect_ratio=increase,crop={manifest.width}:{manifest.height}"
        return [
            self.ffmpeg_path,
            "-y",
            "-loop",
            "1",
            "-t",
            str(first_scene.duration_ms / 1000),
            "-i",
            str(first_scene.asset_path),
            "-i",
            str(manifest.audio_path),
            "-vf",
            vf,
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(manifest.output_path),
        ]
```

## Required Render API

Implement `shorts_growth_agent/backend/src/shorts_agent/api/render.py`.

```python
# 렌더링 요청을 받아 FFmpeg 명령 미리보기를 반환한다.
from pathlib import Path

from fastapi import APIRouter

from shorts_agent.config import get_settings
from shorts_agent.services.render_manifest import FfmpegCommandBuilder, RenderManifest, RenderScene

router = APIRouter()


@router.post("/render/preview-command")
def preview_render_command() -> dict[str, list[str]]:
    manifest = RenderManifest(
        width=1080,
        height=1920,
        scenes=[RenderScene(Path("storage/example/scene1.png"), 2000, "첫 문장", "zoom_in")],
        audio_path=Path("storage/example/voice.wav"),
        output_path=Path("storage/example/out.mp4"),
    )
    command = FfmpegCommandBuilder(get_settings().ffmpeg_path).build(manifest)
    return {"command": command}
```

Do not wire `render.py` into `main.py` in this task unless the implementation plan explicitly requires it. Route integration can happen in the later API integration step.

## Verification

1. Run `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_render_manifest.py -q` after writing tests and before implementation. It must fail with missing `shorts_agent.services.render_manifest`.
2. Run the same command after implementation. It must pass with clean output.
3. Run `.\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py tests/test_subtitle_sync.py tests/test_source_recommender.py tests/test_render_manifest.py -q`. It must pass with clean output.

## Report Contract

Write the full report to `.superpowers/sdd/task-7-report.md`.

Return only this summary to the parent.

- Status: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`.
- Files changed.
- Red test result.
- Green test result.
- Concerns.
