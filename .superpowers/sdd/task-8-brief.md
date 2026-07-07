# Task 8 Brief: Performance Snapshot Analysis

## Goal

Add time-series performance cause analysis that prioritizes result data over production facts, then produces cause candidates and next experiment suggestions.

## Global Constraints

- User-facing text and reports should be Korean.
- Work only inside the assigned files under `shorts_growth_agent`, plus write your report file at `.superpowers/sdd/task-8-report.md`.
- Do not touch `maple_bot`, frontend files, or unrelated root files.
- Every new source file must start with a one-line Korean comment explaining its role.
- Follow TDD. Write tests first, run them and observe failure, then implement the minimum code, then rerun tests.
- Do not run `git add` or `git commit`. The parent agent will commit because this workspace blocks the normal Git index.
- Use the existing backend virtual environment command when running tests: `.\.venv\Scripts\python.exe -m pytest ...`.

## Existing Context

The user emphasized that self-improvement should focus on causes inferred from time-based result data. Production facts are included, but lower priority.

## Files To Create

- `shorts_growth_agent/backend/src/shorts_agent/repositories/performance_repository.py`
- `shorts_growth_agent/backend/src/shorts_agent/services/performance_analysis.py`
- `shorts_growth_agent/backend/src/shorts_agent/api/performance.py`
- `shorts_growth_agent/backend/tests/test_performance_analysis.py`

## Required Interfaces

- `PerformanceAnalysisService.analyze(snapshots, production_facts) -> AnalysisResult`.
- Cause candidate fields: `code`, `label`, `probability`, `reason`.

## Required Tests

Create `shorts_growth_agent/backend/tests/test_performance_analysis.py`.

```python
# 시간별 성과 곡선을 먼저 보고 제작 데이터를 보조로 사용한다.
from shorts_agent.services.performance_analysis import PerformanceAnalysisService, PerformancePoint


def test_low_ctr_after_good_impressions_points_to_title_thumbnail():
    snapshots = [
        PerformancePoint(minutes_since_upload=60, views=100, impressions=5000, ctr=0.02, retention_3s=0.7),
        PerformancePoint(minutes_since_upload=360, views=130, impressions=9000, ctr=0.014, retention_3s=0.68),
    ]

    result = PerformanceAnalysisService().analyze(snapshots, {"hook_type": "question"})

    assert result.cause_candidates[0].code == "title_thumbnail_mismatch"


def test_high_ctr_low_three_second_retention_points_to_hook():
    snapshots = [
        PerformancePoint(minutes_since_upload=60, views=600, impressions=5000, ctr=0.12, retention_3s=0.22),
    ]

    result = PerformanceAnalysisService().analyze(snapshots, {"first_scene_motion": "none"})

    assert result.cause_candidates[0].code == "weak_first_three_seconds"
```

## Required Analysis Service

Implement `shorts_growth_agent/backend/src/shorts_agent/services/performance_analysis.py`.

```python
# 시간별 성과 데이터 중심으로 원인 후보를 분석한다.
from dataclasses import dataclass


@dataclass(frozen=True)
class PerformancePoint:
    minutes_since_upload: int
    views: int
    impressions: int
    ctr: float
    retention_3s: float


@dataclass(frozen=True)
class CauseCandidate:
    code: str
    label: str
    probability: float
    reason: str


@dataclass(frozen=True)
class AnalysisResult:
    cause_candidates: list[CauseCandidate]
    next_experiments: list[str]


class PerformanceAnalysisService:
    def analyze(self, snapshots: list[PerformancePoint], production_facts: dict) -> AnalysisResult:
        if not snapshots:
            return AnalysisResult([], ["성과 스냅샷을 먼저 입력합니다."])
        latest = sorted(snapshots, key=lambda item: item.minutes_since_upload)[-1]
        candidates: list[CauseCandidate] = []
        if latest.impressions >= 1000 and latest.ctr < 0.03:
            candidates.append(CauseCandidate(
                "title_thumbnail_mismatch",
                "제목/썸네일 문제 가능성",
                0.78,
                "노출은 충분하지만 클릭률이 낮습니다.",
            ))
        if latest.ctr >= 0.08 and latest.retention_3s < 0.35:
            candidates.append(CauseCandidate(
                "weak_first_three_seconds",
                "첫 3초 후킹 문제 가능성",
                0.82,
                "클릭은 되었지만 초반 유지율이 낮습니다.",
            ))
        if not candidates:
            candidates.append(CauseCandidate(
                "insufficient_signal",
                "추가 데이터 필요",
                0.45,
                "성과 패턴이 아직 명확하지 않습니다.",
            ))
        return AnalysisResult(
            cause_candidates=sorted(candidates, key=lambda item: item.probability, reverse=True),
            next_experiments=self._experiments(candidates, production_facts),
        )

    def _experiments(self, candidates: list[CauseCandidate], production_facts: dict) -> list[str]:
        experiments = []
        for candidate in candidates:
            if candidate.code == "title_thumbnail_mismatch":
                experiments.append("같은 키워드로 제목 첫 12자를 더 직접적으로 바꾼 버전을 비교합니다.")
            if candidate.code == "weak_first_three_seconds":
                experiments.append("첫 장면에 줌인 또는 흔들림 모션과 더 짧은 후킹 문장을 적용합니다.")
        return experiments or ["동일 카테고리 영상 3개 이상과 시간별 성과를 비교합니다."]
```

## Required Performance API

Implement `shorts_growth_agent/backend/src/shorts_agent/api/performance.py`.

```python
# 수동 성과 입력과 회고 리포트 생성을 제공한다.
from fastapi import APIRouter
from pydantic import BaseModel

from shorts_agent.services.performance_analysis import PerformanceAnalysisService, PerformancePoint

router = APIRouter()


class PerformanceAnalysisRequest(BaseModel):
    snapshots: list[PerformancePoint]
    production_facts: dict


@router.post("/performance/analyze")
def analyze_performance(request: PerformanceAnalysisRequest):
    result = PerformanceAnalysisService().analyze(request.snapshots, request.production_facts)
    return {
        "cause_candidates": [candidate.__dict__ for candidate in result.cause_candidates],
        "next_experiments": result.next_experiments,
    }
```

## Required Repository Placeholder

Create `shorts_growth_agent/backend/src/shorts_agent/repositories/performance_repository.py` with a Korean first-line role comment.
Keep it minimal. If you add methods, keep them directly tied to storing/retrieving performance data and do not touch unrelated files.

## Verification

1. Run `cd shorts_growth_agent/backend && .\.venv\Scripts\python.exe -m pytest tests/test_performance_analysis.py -q` after writing tests and before implementation. It must fail with missing `shorts_agent.services.performance_analysis`.
2. Run the same command after implementation. It must pass with clean output.
3. Run `.\.venv\Scripts\python.exe -m pytest tests/test_health.py tests/test_models.py tests/test_trend_scoring.py tests/test_script_planner.py tests/test_subtitle_sync.py tests/test_source_recommender.py tests/test_render_manifest.py tests/test_performance_analysis.py -q`. It must pass with clean output.

## Report Contract

Write the full report to `.superpowers/sdd/task-8-report.md`.

Return only this summary to the parent.

- Status: `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`.
- Files changed.
- Red test result.
- Green test result.
- Concerns.
