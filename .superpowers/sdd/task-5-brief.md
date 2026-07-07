# Task 5 Brief: TTS Adapter And Subtitle Sync

## Goal

Add a replaceable TTS adapter interface and deterministic subtitle cue synchronization for the Shorts creation pipeline.

## Global Constraints

- User-facing text and reports should be Korean.
- Work only inside the assigned files under `shorts_growth_agent`, plus write your report file at `.superpowers/sdd/task-5-report.md`.
- Do not touch `maple_bot`, frontend files, or unrelated root files.
- Every new source file must start with a one-line Korean comment explaining its role.
- Follow TDD for subtitle sync. Write tests first, run them and observe failure, then implement the minimum code, then rerun tests.
- Do not run `git add` or `git commit`. The parent agent will commit because this workspace blocks the normal Git index.
- Use the existing backend virtual environment command when running tests: `.\.venv\Scripts\python.exe -m pytest ...`.

## Existing Context

Task 4 created `ScriptPlanner` scene plans. This task prepares voice/audio duration and subtitle timing support for those scene lines.

## Files To Create

- `shorts_growth_agent/backend/src/shorts_agent/adapters/tts.py`
- `shorts_growth_agent/backend/src/shorts_agent/services/subtitle_sync.py`
- `shorts_growth_agent/backend/src/shorts_agent/api/projects.py`
- `shorts_growth_agent/backend/tests/test_subtitle_sync.py`

## Required Interfaces

- `TtsAdapter.synthesize(text: str, voice: str, speed: float, output_path: Path) -> TtsResult`.
- `SubtitleSyncService.sync(lines: list[str], total_duration_ms: int) -> list[SubtitleCue]`.

## Required Test

Create `shorts_growth_agent/backend/tests/test_subtitle_sync.py`.

```python
# TTS 길이에 맞춰 자막 큐를 균등 배분한다.
from shorts_agent.services.subtitle_sync import SubtitleSyncService


def test_sync_splits_duration_across_lines():
    cues = SubtitleSyncService().sync(["첫 문장", "두 번째 문장"], total_duration_ms=4000)

    assert cues[0].start_ms == 0
    assert cues[0].end_ms == 2000
    assert cues[1].start_ms == 2000
    assert cues[1].end_ms == 4000
```

## Required TTS Adapter

Implement `shorts_growth_agent/backend/src/shorts_agent/adapters/tts.py`.

```python
# TTS 엔진을 교체 가능하게 감싸는 어댑터를 정의한다.
from dataclasses import dataclass
from pathlib import Path
import wave


@dataclass(frozen=True)
class TtsResult:
    audio_path: Path
    duration_ms: int
    voice: str
    speed: float


class TtsAdapter:
    def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> TtsResult:
        raise NotImplementedError


class SilentTtsAdapter(TtsAdapter):
    def synthesize(self, text: str, voice: str, speed: float, output_path: Path) -> TtsResult:
        duration_ms = max(1000, int(len(text) * 80 / max(speed, 0.5)))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(output_path), "w") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(b"\\x00\\x00" * int(16000 * duration_ms / 1000))
        return TtsResult(audio_path=output_path, duration_ms=duration_ms, voice=voice, speed=speed)
```

## Required Subtitle Sync

Implement `shorts_growth_agent/backend/src/shorts_agent/services/subtitle_sync.py`.

```python
# 음성 길이에 맞춰 자막 타임코드를 만든다.
from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleCue:
    text: str
    start_ms: int
    end_ms: int


class SubtitleSyncService:
    def sync(self, lines: list[str], total_duration_ms: int) -> list[SubtitleCue]:
        if not lines:
            return []
        slot = total_duration_ms // len(lines)
        cues = []
        for index, line in enumerate(lines):
            start = index * slot
            end = total_duration_ms if index == len(lines) - 1 else (index + 1) * slot
            cues.append(SubtitleCue(text=line, start_ms=start, end_ms=end))
        return cues
```

## Required Projects API Placeholder

Create `shorts_growth_agent/backend/src/shorts_agent/api/projects.py` with a Korean first-line role comment and an `APIRouter`.
Do not wire it into `main.py` in this task. The project API integration is handled in Task 9.

## Verification

1. Run `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_subtitle_sync.py -q` after writing tests and before implementation. It must fail with missing `shorts_agent.services.subtitle_sync`.
2. Run the same command after implementation. It must pass with clean output.
3. Run `.\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py tests/test_subtitle_sync.py -q`. It must pass with clean output.

## Report Contract

Write the full report to `.superpowers/sdd/task-5-report.md`.

Return only this summary to the parent.

- Status: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`.
- Files changed.
- Red test result.
- Green test result.
- Concerns.
