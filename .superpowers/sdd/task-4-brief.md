# Task 4 Brief: Script Harness And Scene Planner

## Goal

Add the editable script harness foundation and deterministic MVP scene planner that turns a keyword/category into structured Shorts scenes.

## Global Constraints

- User-facing text and reports should be Korean.
- Work only inside the assigned files under `shorts_growth_agent`, plus write your report file at `.superpowers/sdd/task-4-report.md`.
- Do not touch `maple_bot`, frontend files, or unrelated root files.
- Every new source file must start with a one-line Korean comment explaining its role.
- Follow TDD. Write tests first, run them and observe failure, then implement the minimum code, then rerun tests.
- Do not run `git add` or `git commit`. The parent agent will commit because this workspace blocks the normal Git index.
- Use the existing backend virtual environment command when running tests: `.\.venv\Scripts\python.exe -m pytest ...`.

## Existing Context

Task 1 created FastAPI scaffolding.
Task 2 created `ScriptHarness` model and repository package.
Task 3 created trend scoring and services package.

## Files To Create

- `shorts_growth_agent/backend/src/shorts_agent/repositories/harness_repository.py`
- `shorts_growth_agent/backend/src/shorts_agent/services/script_planner.py`
- `shorts_growth_agent/backend/src/shorts_agent/api/harnesses.py`
- `shorts_growth_agent/backend/tests/test_script_planner.py`

## Required Interfaces

- `ScriptPlanner.generate(keyword: str, category: str, harness: HarnessConfig) -> ScriptPlan`.
- Scene fields: `index`, `subtitle`, `voice_text`, `image_prompt`, `source_type`, `motion_type`, `sound_effect`, `duration_ms`.

## Required Test

Create `shorts_growth_agent/backend/tests/test_script_planner.py`.

```python
# 대본 하네스가 장면, 자막, 이미지, 모션 지시를 만든다.
from shorts_agent.services.script_planner import HarnessConfig, ScriptPlanner


def test_generate_returns_structured_scene_plan():
    harness = HarnessConfig(
        name="정보+후킹형",
        tone="빠른 정보형",
        hook_strength="강함",
        target_seconds=45,
        forbidden_terms=["무조건", "100%"],
    )

    plan = ScriptPlanner().generate(keyword="게임 업데이트", category="게임", harness=harness)

    assert plan.keyword == "게임 업데이트"
    assert 3 <= len(plan.scenes) <= 8
    assert plan.scenes[0].motion_type in {"zoom_in", "shake", "bounce", "none"}
    assert "무조건" not in " ".join(scene.subtitle for scene in plan.scenes)
```

## Required Planner

Implement `shorts_growth_agent/backend/src/shorts_agent/services/script_planner.py`.

```python
# 대본 하네스를 장면 단위 쇼츠 계획으로 변환한다.
from dataclasses import dataclass


@dataclass(frozen=True)
class HarnessConfig:
    name: str
    tone: str
    hook_strength: str
    target_seconds: int
    forbidden_terms: list[str]


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
    def generate(self, keyword: str, category: str, harness: HarnessConfig) -> ScriptPlan:
        scene_count = 5 if harness.target_seconds <= 45 else 7
        duration_ms = int(harness.target_seconds * 1000 / scene_count)
        templates = [
            f"지금 {keyword}, 왜 갑자기 뜨는 걸까요?",
            f"핵심은 세 가지입니다.",
            f"첫째, 사람들이 반응한 포인트가 분명합니다.",
            f"둘째, {category} 흐름과 바로 연결됩니다.",
            f"마지막으로 지금 확인해야 할 부분입니다.",
        ]
        scenes = []
        for index, subtitle in enumerate(templates[:scene_count], start=1):
            cleaned = self._remove_forbidden(subtitle, harness.forbidden_terms)
            scenes.append(
                PlannedScene(
                    index=index,
                    subtitle=cleaned,
                    voice_text=cleaned,
                    image_prompt=f"{category} 주제의 세로형 쇼츠 이미지, 키워드: {keyword}, 장면 {index}",
                    source_type=self._source_type(category, index),
                    motion_type="zoom_in" if index == 1 else "shake" if index == 3 else "none",
                    sound_effect="hit" if index == 1 else "whoosh" if index == 2 else "none",
                    duration_ms=duration_ms,
                )
            )
        return ScriptPlan(keyword=keyword, category=category, title_candidate=f"{keyword} 핵심 정리", scenes=scenes)

    def _remove_forbidden(self, text: str, forbidden_terms: list[str]) -> str:
        for term in forbidden_terms:
            text = text.replace(term, "")
        return text

    def _source_type(self, category: str, index: int) -> str:
        if category == "게임" and index in {2, 3}:
            return "clip_candidate"
        if category in {"뉴스", "이슈"} and index == 1:
            return "reference_image"
        return "ai_image"
```

## Required Harness Repository

Implement `shorts_growth_agent/backend/src/shorts_agent/repositories/harness_repository.py`.

```python
# 대본 하네스 프리셋을 저장하고 조회한다.
from sqlalchemy.orm import Session

from shorts_agent.models import ScriptHarness


class HarnessRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_default_harness(self) -> ScriptHarness:
        harness = ScriptHarness(
            name="정보+후킹형",
            mode="basic",
            system_prompt="빠르고 정확한 한국어 쇼츠 작가로서 첫 3초 후킹과 명확한 정보 전달을 우선한다.",
            output_schema={
                "scene": "number",
                "subtitle": "string",
                "voice_text": "string",
                "image_prompt": "string",
                "source_type": "string",
                "motion_type": "string",
                "sound_effect": "string",
            },
            forbidden_terms=["무조건", "100%", "확정"],
        )
        self.session.add(harness)
        self.session.commit()
        self.session.refresh(harness)
        return harness
```

## Required Harness API

Create a minimal `shorts_growth_agent/backend/src/shorts_agent/api/harnesses.py` with Korean first-line comment and an `APIRouter`.
Provide a simple `GET /harnesses/default` route returning the default harness shape without requiring persistence wiring yet. Keep it deterministic.

## Verification

1. Run `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_script_planner.py -q` after writing tests and before implementation. It must fail with missing `shorts_agent.services.script_planner`.
2. Run the same command after implementation. It must pass with clean output.
3. Run `.\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py -q`. It must pass with clean output.

## Report Contract

Write the full report to `.superpowers/sdd/task-4-report.md`.

Return only this summary to the parent.

- Status: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`.
- Files changed.
- Red test result.
- Green test result.
- Concerns.
