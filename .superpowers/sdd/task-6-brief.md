# Task 6 Brief: Source Recommendation And Scene Assets

## Goal

Add source recommendation logic for scene assets, with adapter seams for AI images and meme libraries while keeping clip candidates user-review gated.

## Global Constraints

- User-facing text and reports should be Korean.
- Work only inside the assigned files under `shorts_growth_agent`, plus write your report file at `.superpowers/sdd/task-6-report.md`.
- Do not touch `maple_bot`, frontend files, or unrelated root files.
- Every new source file must start with a one-line Korean comment explaining its role.
- Follow TDD. Write tests first, run them and observe failure, then implement the minimum code, then rerun tests.
- Do not run `git add` or `git commit`. The parent agent will commit because this workspace blocks the normal Git index.
- Use the existing backend virtual environment command when running tests: `.\.venv\Scripts\python.exe -m pytest ...`.

## Existing Context

Task 4 scene plans include `source_type` hints such as `ai_image` and `clip_candidate`.
This task turns those hints into user-review-aware source recommendations.

## Files To Create

- `shorts_growth_agent/backend/src/shorts_agent/adapters/image.py`
- `shorts_growth_agent/backend/src/shorts_agent/adapters/meme.py`
- `shorts_growth_agent/backend/src/shorts_agent/services/source_recommender.py`
- `shorts_growth_agent/backend/tests/test_source_recommender.py`

## Required Interfaces

- `SourceRecommender.recommend(category: str, scene_index: int, source_hint: str) -> SourceRecommendation`.
- Source types: `ai_image`, `meme`, `clip_candidate`, `reference_image`, `uploaded_file`.

## Required Tests

Create `shorts_growth_agent/backend/tests/test_source_recommender.py`.

```python
# 카테고리별 우선순위와 장면 힌트로 소스 타입을 추천한다.
from shorts_agent.services.source_recommender import SourceRecommender


def test_game_clip_hint_recommends_clip_candidate():
    result = SourceRecommender().recommend("게임", 2, "clip_candidate")

    assert result.source_type == "clip_candidate"
    assert result.requires_user_review is True


def test_info_category_defaults_to_ai_image():
    result = SourceRecommender().recommend("정보형", 1, "ai_image")

    assert result.source_type == "ai_image"
    assert result.requires_user_review is False
```

## Required Image Adapter

Implement `shorts_growth_agent/backend/src/shorts_agent/adapters/image.py`.

```python
# 이미지 생성 엔진을 교체 가능하게 감싸는 어댑터를 정의한다.
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ImageResult:
    path: Path
    prompt: str


class ImageAdapter:
    def generate(self, prompt: str, output_path: Path) -> ImageResult:
        raise NotImplementedError
```

## Required Meme Adapter

Implement `shorts_growth_agent/backend/src/shorts_agent/adapters/meme.py`.

```python
# 밈 MCP 또는 로컬 밈 라이브러리 연결을 위한 어댑터를 정의한다.
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MemeAsset:
    path: Path
    tags: list[str]
    source: str


class MemeAdapter:
    def search(self, query: str, limit: int = 10) -> list[MemeAsset]:
        return []
```

## Required Source Recommender

Implement `shorts_growth_agent/backend/src/shorts_agent/services/source_recommender.py`.

```python
# 장면별 이미지, 밈, 클립 후보 소스 타입을 추천한다.
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRecommendation:
    source_type: str
    reason: str
    requires_user_review: bool


class SourceRecommender:
    def recommend(self, category: str, scene_index: int, source_hint: str) -> SourceRecommendation:
        if source_hint == "clip_candidate":
            return SourceRecommendation(
                source_type="clip_candidate",
                reason="실제 장면이 있으면 이해가 빠른 장면입니다. 사용자가 구간과 사용 가능 여부를 확인해야 합니다.",
                requires_user_review=True,
            )
        if category in {"뉴스", "이슈"} and scene_index == 1:
            return SourceRecommendation("reference_image", "첫 장면은 실제 자료 이미지가 신뢰감을 줍니다.", True)
        if category == "게임" and scene_index >= 3:
            return SourceRecommendation("meme", "반응 장면에는 밈 이미지가 리듬을 만듭니다.", False)
        return SourceRecommendation("ai_image", "기본 장면은 AI 이미지로 안정적으로 구성합니다.", False)
```

## Verification

1. Run `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_source_recommender.py -q` after writing tests and before implementation. It must fail with missing `shorts_agent.services.source_recommender`.
2. Run the same command after implementation. It must pass with clean output.
3. Run `.\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py tests/test_subtitle_sync.py tests/test_source_recommender.py -q`. It must pass with clean output.

## Report Contract

Write the full report to `.superpowers/sdd/task-6-report.md`.

Return only this summary to the parent.

- Status: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`.
- Files changed.
- Red test result.
- Green test result.
- Concerns.
