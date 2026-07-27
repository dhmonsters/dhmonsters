# Binary Merge Identity Transfer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 타겟 1개와 배경 1개의 병합 사건만 추출해, 분리 후 두 자식 중 올바른 자식에게 타겟 신분을 전달하고 배경으로 잘못 갈아타지 않는 opt-in shadow 판별기를 만든다.

**Architecture:** 준비 구간은 지역 배경 흐름과 불확실성만 숫자로 압축한다. 병합 사건에서는 부모 박스 중심으로 타겟 상태를 갱신하지 않고, 분리 자식 A/B에 대해 H1과 H2 역할 가설을 비교한다. 실행 결과는 프레임 점수가 아니라 사건 단위 `CORRECT_TRANSFER`, `WRONG_SWITCH`, `SAFE_HOLD` 등으로 채점하며, 대표 사건 게이트를 통과하기 전에는 기존 replay와 `puzzle.py` 선택 경로에 연결하지 않는다.

**Tech Stack:** Python 3.14, 표준 라이브러리 dataclass/enum/statistics/math/json/pathlib, 기존 `Candidate`와 `CandidateEvidence`, pytest, 기존 Studio JSONL trace/score 자료.

## Global Constraints

- 배경 도형끼리는 서로 겹치지 않는다.
- 하나의 물리 병합 사건에는 타겟 1개와 배경 1개만 참여한다.
- 세 개 이상의 검출은 물리 자식이 아니라 중복 검출 또는 오검출로 처리한다.
- 실행 중 GT를 읽지 않는다. GT는 사건 종료 후 채점에만 사용한다.
- 고정 좌표, 고정 방향, 절대 프레임 번호를 규칙에 넣지 않는다.
- 병합 부모 박스 중심으로 타겟 위치나 속도를 갱신하지 않는다.
- 판단 증거가 충돌하거나 부족하면 HOLD한다.
- 전체 주기 정보는 사용 가능할 때만 배경 보조 증거로 쓰며 사건 판별의 필수 조건으로 만들지 않는다.
- 첫 구현은 마우스 출력이 없는 opt-in shadow다.
- 새 외부 의존성을 추가하지 않는다.
- 모든 새 Python 소스 파일 첫 줄에는 역할을 설명하는 한국어 주석을 넣는다.

---

## File Structure

- Create `maple_bot/core/puzzle/binary_merge_identity.py`.
  - 이진 역할 가설, 심판 투표, HOLD 및 신분 전달 결정을 담당하는 순수 도메인 모듈이다.
- Create `maple_bot/core/puzzle/binary_merge_background.py`.
  - 준비 구간의 지역 배경 흐름과 불확실성을 압축하는 순수 관측 모듈이다.
- Create `maple_bot/core/puzzle/binary_merge_shadow.py`.
  - 준비 구간 압축, trace 사건 추출, 분리 자식의 정규화 잔차 계산, 사건 replay와 진단 생성을 담당한다.
- Create `maple_bot/tests/test_binary_merge_identity.py`.
  - 역할 교환 대칭성, 배경·타겟 합의, 모호성 HOLD, 중복 검출 거부를 검증한다.
- Create `maple_bot/tests/test_binary_merge_background.py`.
  - 해상도 독립 배경 흐름, 이상치 강건성, 공백 불확실성을 검증한다.
- Create `maple_bot/tests/test_binary_merge_shadow.py`.
  - 준비 구간 압축, 병합 중심 비사용, 사건 추출, runtime GT 비의존, 사후 GT 채점을 검증한다.
- Modify `maple_bot/core/puzzle/studio_hypothesis_shadow.py` only after Gate 1 passes.
  - opt-in 진단에 사건 결과를 표시하되 기존 선택 결과는 바꾸지 않는다.
- Modify `maple_bot/tests/test_studio_hypothesis_shadow.py` only after Gate 1 passes.
  - opt-out 무변경과 opt-in 진단 추가를 검증한다.
- Create `03_output/2026-07-27_binary_merge_identity_transfer_validation_v1.md` during Task 5.
  - 대표 사건 결과와 확대 여부만 기록한다.

---

### Task 1: Pure Binary Role Hypothesis Resolver

**Files:**
- Create: `maple_bot/core/puzzle/binary_merge_identity.py`
- Test: `maple_bot/tests/test_binary_merge_identity.py`

**Interfaces:**
- Consumes: `core.puzzle.models.Candidate`.
- Produces: `BinaryRoleEvidence`, `BinaryHypothesis`, `BinaryTransferDecision`, `BinaryMergeIdentityResolver.evaluate()`.

- [ ] **Step 1: Write failing tests for the public decision contract**

```python
# 이진 병합 신분 전달 판별기의 순수 역할 결정을 검증합니다.
from core.puzzle.binary_merge_identity import (
    BinaryMergeIdentityResolver,
    BinaryRoleEvidence,
    BinaryTransferStatus,
)


def test_agreed_background_and_target_judges_transfer_identity() -> None:
    resolver = BinaryMergeIdentityResolver()
    decision = resolver.evaluate(
        event_id=7,
        child_a=BinaryRoleEvidence(
            candidate_id="a",
            target_motion_residual=0.25,
            background_motion_residual=2.20,
            neighbor_relation_residual=1.80,
            ancestry_residual=0.20,
            shape_residual=0.30,
            yolo_shortfall=0.0,
            uncertainty=0.10,
        ),
        child_b=BinaryRoleEvidence(
            candidate_id="b",
            target_motion_residual=2.10,
            background_motion_residual=0.20,
            neighbor_relation_residual=0.30,
            ancestry_residual=0.25,
            shape_residual=0.35,
            yolo_shortfall=0.0,
            uncertainty=0.10,
        ),
    )
    assert decision.status is BinaryTransferStatus.RESOLVED
    assert decision.target_candidate_id == "a"
    assert decision.background_candidate_id == "b"


def test_conflicting_judges_hold_instead_of_switching() -> None:
    resolver = BinaryMergeIdentityResolver()
    decision = resolver.evaluate(
        event_id=8,
        child_a=BinaryRoleEvidence(
            candidate_id="a",
            target_motion_residual=0.30,
            background_motion_residual=0.40,
            neighbor_relation_residual=0.35,
            ancestry_residual=0.20,
            shape_residual=0.25,
            yolo_shortfall=0.0,
            uncertainty=0.10,
        ),
        child_b=BinaryRoleEvidence(
            candidate_id="b",
            target_motion_residual=1.50,
            background_motion_residual=1.60,
            neighbor_relation_residual=1.40,
            ancestry_residual=0.20,
            shape_residual=0.25,
            yolo_shortfall=0.0,
            uncertainty=0.10,
        ),
    )
    assert decision.status is BinaryTransferStatus.HOLD
    assert decision.target_candidate_id is None
    assert decision.reason == "judge_disagreement"
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe' -m pytest tests\test_binary_merge_identity.py -q -p no:cacheprovider
```

Expected: collection fails because `core.puzzle.binary_merge_identity` does not exist.

- [ ] **Step 3: Implement immutable evidence and decision types**

```python
# 타겟과 배경이 둘로 분리될 때 두 역할 가설을 비교합니다.
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BinaryTransferStatus(str, Enum):
    RESOLVED = "resolved"
    HOLD = "hold"


@dataclass(frozen=True)
class BinaryRoleEvidence:
    candidate_id: str
    target_motion_residual: float
    background_motion_residual: float
    neighbor_relation_residual: float
    ancestry_residual: float
    shape_residual: float
    yolo_shortfall: float
    uncertainty: float


@dataclass(frozen=True)
class BinaryHypothesis:
    name: str
    target_candidate_id: str
    background_candidate_id: str
    target_cost: float
    background_cost: float
    support_groups: tuple[str, ...]

    @property
    def total_cost(self) -> float:
        return self.target_cost + self.background_cost


@dataclass(frozen=True)
class BinaryTransferDecision:
    event_id: int
    status: BinaryTransferStatus
    target_candidate_id: str | None
    background_candidate_id: str | None
    selected_hypothesis: str | None
    normalized_margin: float
    reason: str
    debug: dict[str, object]
```

- [ ] **Step 4: Implement symmetric H1/H2 evaluation**

Implement `BinaryMergeIdentityResolver.evaluate()` with these exact rules.

```python
class BinaryMergeIdentityResolver:
    def evaluate(
        self,
        *,
        event_id: int,
        child_a: BinaryRoleEvidence,
        child_b: BinaryRoleEvidence,
    ) -> BinaryTransferDecision:
        h1 = self._hypothesis("h1", child_a, child_b)
        h2 = self._hypothesis("h2", child_b, child_a)
        best, runner_up = sorted((h1, h2), key=lambda row: row.total_cost)
        scale = max(1.0, abs(best.total_cost), abs(runner_up.total_cost))
        margin = (runner_up.total_cost - best.total_cost) / scale
        required = {"target_motion", "background_motion"}
        if not required.issubset(best.support_groups):
            return self._hold(event_id, margin, "judge_disagreement", h1, h2)
        required_margin = max(0.0, child_a.uncertainty, child_b.uncertainty)
        if margin <= required_margin:
            return self._hold(event_id, margin, "hypothesis_ambiguous", h1, h2)
        return BinaryTransferDecision(
            event_id=event_id,
            status=BinaryTransferStatus.RESOLVED,
            target_candidate_id=best.target_candidate_id,
            background_candidate_id=best.background_candidate_id,
            selected_hypothesis=best.name,
            normalized_margin=margin,
            reason="binary_judges_agree",
            debug={"h1": h1, "h2": h2},
        )
```

`_hypothesis()` must compare child residuals pairwise. A support group is added only when the assigned role candidate has the lower residual by more than the larger child uncertainty. `shape_residual` and `yolo_shortfall` may increase cost but must never create the required support groups. Required target/background/ancestry residuals must be finite. Optional neighbor, shape or YOLO evidence that is unavailable is skipped rather than converted to a favorable zero.

- [ ] **Step 5: Add symmetry, low-YOLO and ambiguity tests**

Add tests proving the following.

- Swapping A and B swaps candidate IDs but preserves the physical role result.
- A low YOLO score cannot override agreeing target/background motion judges.
- Equal residuals produce HOLD.
- Missing or non-finite residuals produce HOLD with `invalid_evidence`.
- Two identical candidate IDs produce HOLD with `duplicate_candidate_identity`.

- [ ] **Step 6: Run Task 1 tests and commit**

Run:

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe' -m pytest tests\test_binary_merge_identity.py -q -p no:cacheprovider
```

Expected: all Task 1 tests pass.

Commit only the two Task 1 files.

```powershell
git add -- core/puzzle/binary_merge_identity.py tests/test_binary_merge_identity.py
git commit -m "이진 병합 역할 가설 판별기 추가"
```

---

### Task 2: Preparation Background Flow Profile

**Files:**
- Create: `maple_bot/core/puzzle/binary_merge_background.py`
- Test: `maple_bot/tests/test_binary_merge_background.py`

**Interfaces:**
- Consumes: consecutive `Candidate` tuples and `frame_shape`.
- Produces: `BackgroundFlowSample`, `BackgroundFlowProfile`, `build_background_flow_profile()`.

- [ ] **Step 1: Write failing profile tests**

Add tests proving the following.

- Uniformly translating background candidates produce the same normalized median velocity when the board is resized.
- One independently moving outlier does not change the median background flow.
- Empty frames increase uncertainty instead of creating a zero-motion sample.
- A profile with insufficient valid transitions is marked unavailable and does not block later HOLD logic.

Use generated candidates with relative board positions. Do not use coordinates copied from a recorded failure.

- [ ] **Step 2: Run the profile tests and verify RED**

Run the specific new test class with pytest `-k background_flow_profile` and expect attribute or import failures.

- [ ] **Step 3: Implement robust normalized flow samples**

Add these public types and function.

```python
# 준비 구간의 지역 배경 흐름과 불확실성을 압축합니다.
from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from statistics import median

from .models import Candidate


@dataclass(frozen=True)
class BackgroundFlowSample:
    frame_index: int
    dx_ratio: float
    dy_ratio: float
    matched_count: int
    dispersion: float


@dataclass(frozen=True)
class BackgroundFlowProfile:
    velocity_ratio: tuple[float, float] | None
    dispersion: float
    valid_transitions: int
    missing_transitions: int
    reason: str

    @property
    def available(self) -> bool:
        return self.velocity_ratio is not None and self.valid_transitions > 0


def build_background_flow_profile(
    frames: tuple[tuple[int, tuple[Candidate, ...]], ...],
    *,
    frame_shape: tuple[int, int],
) -> BackgroundFlowProfile:
    width = max(1.0, float(frame_shape[1]))
    height = max(1.0, float(frame_shape[0]))
    samples: list[BackgroundFlowSample] = []
    missing = 0
    for (frame_index, previous), (_next_index, current) in zip(frames, frames[1:]):
        matches = _minimum_cost_background_matches(previous, current, frame_shape)
        if not matches:
            missing += 1
            continue
        dx_values = [(right.center[0] - left.center[0]) / width for left, right in matches]
        dy_values = [(right.center[1] - left.center[1]) / height for left, right in matches]
        dx_ratio = median(dx_values)
        dy_ratio = median(dy_values)
        residuals = [
            hypot(dx - dx_ratio, dy - dy_ratio)
            for dx, dy in zip(dx_values, dy_values)
        ]
        samples.append(
            BackgroundFlowSample(
                frame_index=frame_index,
                dx_ratio=dx_ratio,
                dy_ratio=dy_ratio,
                matched_count=len(matches),
                dispersion=median(residuals) if residuals else 0.0,
            )
        )
    if not samples:
        return BackgroundFlowProfile(None, float("inf"), 0, missing, "insufficient_background_motion")
    velocity = (median(row.dx_ratio for row in samples), median(row.dy_ratio for row in samples))
    dispersion = median(row.dispersion for row in samples)
    return BackgroundFlowProfile(velocity, dispersion, len(samples), missing, "available")
```

Replace the final function body marker during implementation with the following behavior.

- Match consecutive background observations by globally minimizing normalized center displacement after duplicate collapse.
- Exclude the known white target candidate from profile input in the adapter, not inside this pure function.
- Use median matched displacement divided by board width/height.
- Use median absolute deviation of matched displacement as `dispersion`.
- Count frames with no reliable matching as `missing_transitions`.
- Return `reason="insufficient_background_motion"` when no reliable transition exists.
- Implement `_minimum_cost_background_matches()` in the same module as a deterministic one-to-one normalized-distance assignment. Reject assignments whose cost is outside the current frame's median-plus-MAD motion envelope. The helper returns `tuple[tuple[Candidate, Candidate], ...]` and never invents zero-motion matches for missing frames.

- [ ] **Step 4: Add nonperiodic and rotating-flow tests**

Prove that the profile does not require a full period. A monotonic background translation and a slowly changing rotational tangent flow must both produce an available local profile. Full-cycle metadata is not part of this interface.

- [ ] **Step 5: Run Task 1 and Task 2 tests and commit**

Run `test_binary_merge_identity.py` and `test_binary_merge_background.py`. Commit only the new background source and test files.

```powershell
git add -- core/puzzle/binary_merge_background.py tests/test_binary_merge_background.py
git commit -m "준비 구간 지역 배경 흐름 압축 추가"
```

---

### Task 3: Binary Merge Event Snapshot and Child Evidence Adapter

**Files:**
- Create: `maple_bot/core/puzzle/binary_merge_shadow.py`
- Create: `maple_bot/tests/test_binary_merge_shadow.py`
- Reuse without modifying: `maple_bot/core/puzzle/merge_split_relative.py`

**Interfaces:**
- Consumes: Studio trace rows, runtime `TARGET_SELECTION`, `IDENTITY_STATE`, `CANDIDATES`, `EVIDENCE` events.
- Produces: `BinaryPremergeSnapshot`, `BinaryMergeEventWindow`, `extract_binary_merge_events()`, `build_child_evidence()`.

- [ ] **Step 1: Write failing event extraction tests**

```python
# Studio trace에서 타겟과 배경의 이진 병합 사건만 추출하는지 검증합니다.
from core.puzzle.binary_merge_shadow import extract_binary_merge_events


def test_partial_merge_split_becomes_one_binary_event() -> None:
    rows = make_trace_rows_for_separate_overlap_merged_split()
    extraction = extract_binary_merge_events(rows)
    assert len(extraction.events) == 1
    assert extraction.events[0].premerge.target_candidate_id == "target_before"
    assert extraction.events[0].premerge.background_candidate_id == "background_before"
    assert len(extraction.events[0].split_observations) >= 1
    assert len(extraction.events[0].split_observations[0].children) == 2
```

The fixture helper must create generic normalized geometry and runtime target selections. It must not contain GT coordinates.

- [ ] **Step 2: Run event extraction tests and verify RED**

Run `tests/test_binary_merge_shadow.py -k binary_event` and expect import failure.

- [ ] **Step 3: Implement event data types and trace indexing**

```python
# Studio trace에서 이진 병합 사건과 역할 증거를 재구성합니다.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .binary_merge_background import BackgroundFlowProfile
from .binary_merge_identity import BinaryRoleEvidence
from .models import Candidate, CandidateEvidence


@dataclass(frozen=True)
class BinaryPremergeSnapshot:
    frame_index: int
    target_candidate_id: str
    background_candidate_id: str
    target_center: tuple[float, float]
    background_center: tuple[float, float]
    target_bbox: tuple[float, float, float, float]
    background_bbox: tuple[float, float, float, float]
    target_velocity: tuple[float, float]
    background_velocity: tuple[float, float]
    neighbor_relations: tuple[BackgroundRelationSnapshot, ...]


@dataclass(frozen=True)
class BackgroundRelationSnapshot:
    anchor_candidate_id: str
    anchor_center: tuple[float, float]
    relative_vector_ratio: tuple[float, float]


@dataclass(frozen=True)
class BinarySplitObservation:
    frame_index: int
    children: tuple[Candidate, Candidate]
    context_candidates: tuple[Candidate, ...]


@dataclass(frozen=True)
class BinaryMergeEventWindow:
    event_id: int
    premerge: BinaryPremergeSnapshot
    merge_frame_indices: tuple[int, ...]
    split_frame_indices: tuple[int, ...]
    parent_bboxes: tuple[tuple[float, float, float, float], ...]
    split_observations: tuple[BinarySplitObservation, ...]
    reason: str


@dataclass(frozen=True)
class BinaryEventExtractionDiagnostic:
    frame_index: int
    reason: str
    candidate_count: int


@dataclass(frozen=True)
class BinaryEventExtractionResult:
    events: tuple[BinaryMergeEventWindow, ...]
    diagnostics: tuple[BinaryEventExtractionDiagnostic, ...]
```

`extract_binary_merge_events(rows: Sequence[dict[str, Any]]) -> BinaryEventExtractionResult` uses existing `MergeSplitEventDetector` state semantics rather than duplicating overlap thresholds. Event extraction must use runtime selected points and identity state, never GT. Open an event only when the premerge identity state is `TRACK_CONFIDENT` or a visible white anchor identifies the target. Otherwise emit the diagnostic reason `premerge_identity_untrusted` and do not create a scoreable event. Missing split children, unresolved duplicates and parent-region violations must also remain in `diagnostics` so event-detection failures do not silently disappear from the denominator.

- [ ] **Step 4: Implement physical duplicate collapse and pair validation**

Add `collapse_physical_candidates()` with these rules.

- Cluster candidates that have high mutual box overlap and centers closer than their normalized box scale.
- Keep the highest-score representative only as an observation representative, not as a role winner.
- Remove candidates outside the union of the recent merge parent regions with a scale-normalized tolerance.
- Return a valid pair only when exactly two physical candidates remain.
- Return reason `duplicate_detection_unresolved` otherwise.

- [ ] **Step 5: Implement child evidence calculation without parent-center velocity**

```python
def build_child_evidence(
    *,
    event: BinaryMergeEventWindow,
    child: Candidate,
    other_child: Candidate,
    context_candidates: Sequence[Candidate],
    flow_profile: BackgroundFlowProfile,
    evidence: Mapping[str, CandidateEvidence],
    frame_shape: tuple[int, int],
) -> BinaryRoleEvidence:
    width = max(1.0, float(frame_shape[1]))
    height = max(1.0, float(frame_shape[0]))
    elapsed = max(1, child.frame_index - event.premerge.frame_index)
    predicted_target = (
        event.premerge.target_center[0] + elapsed * event.premerge.target_velocity[0],
        event.premerge.target_center[1] + elapsed * event.premerge.target_velocity[1],
    )
    flow_dx, flow_dy = flow_profile.velocity_ratio or (0.0, 0.0)
    predicted_background = (
        event.premerge.background_center[0] + elapsed * flow_dx * width,
        event.premerge.background_center[1] + elapsed * flow_dy * height,
    )
    scale = max(1.0, _bbox_diagonal(event.premerge.target_bbox), _bbox_diagonal(event.premerge.background_bbox))
    target_residual = _point_distance(child.center, predicted_target) / scale
    background_residual = (
        _point_distance(child.center, predicted_background) / scale
        if flow_profile.available
        else float("nan")
    )
    ancestry_residual = _children_parent_union_residual(event, child, other_child, scale)
    shape_residual = min(
        _bbox_shape_residual(child.bbox, event.premerge.target_bbox),
        _bbox_shape_residual(child.bbox, event.premerge.background_bbox),
    )
    candidate_evidence = evidence.get(child.candidate_id)
    neighbor_residual = _neighbor_relation_residual(
        event.premerge.neighbor_relations,
        assumed_background_child=child,
        context_candidates=context_candidates,
        elapsed=elapsed,
        flow_profile=flow_profile,
        frame_shape=frame_shape,
    )
    yolo_floor = _relative_yolo_floor((child, other_child))
    return BinaryRoleEvidence(
        candidate_id=child.candidate_id,
        target_motion_residual=target_residual,
        background_motion_residual=background_residual,
        neighbor_relation_residual=neighbor_residual,
        ancestry_residual=ancestry_residual,
        shape_residual=shape_residual,
        yolo_shortfall=max(0.0, yolo_floor - child.score),
        uncertainty=max(
            flow_profile.dispersion if flow_profile.available else 1.0,
            ancestry_residual * 0.25,
        ),
    )
```

Replace the body marker with calculations using only these sources.

- Target motion residual uses the premerge target state propagated across the elapsed timestamps or frame indices. It must never use a parent bbox center as a target observation.
- Background motion residual uses premerge background state and the local flow profile.
- Neighbor relation residual matches premerge nearby anchors to current context candidates using the local background-flow prediction, then compares the assumed background child's normalized relative vectors. Missing or ambiguous anchors leave the judge unavailable rather than assigning zero residual.
- Ancestry residual measures whether both children jointly explain the recent parent union.
- Shape residual compares each role's premerge size with scale normalization.
- YOLO shortfall uses the current candidate score distribution. Scores above the relative reliability floor receive no additional bonus.
- Implement `_bbox_diagonal()`, `_point_distance()`, `_children_parent_union_residual()`, `_bbox_shape_residual()`, `_neighbor_relation_residual()` and `_relative_yolo_floor()` as pure scale-normalized helpers in `binary_merge_shadow.py`. `_relative_yolo_floor()` returns the median score of the physical child pair, so the weaker child may receive a shortfall while the stronger child receives no extra bonus.

- [ ] **Step 6: Add tests for the two physical detection cases**

Test both supported cases.

- Two overlapping boxes remain separately detectable through the event.
- One expanded parent box remains during MERGED and two children later return.
- The first split observation is ambiguous, remains HOLD, and a later split observation resolves without changing event ID.
- Nearby background anchors preserve the background child's relative relation while the target child breaks it.

Also verify that changing the parent center does not change target motion residual or the final role decision.

- [ ] **Step 7: Run Task 3 tests and commit**

Run `test_binary_merge_identity.py`, `test_binary_merge_background.py` and `test_binary_merge_shadow.py`. Commit the new shadow source and test only.

```powershell
git add -- core/puzzle/binary_merge_shadow.py tests/test_binary_merge_shadow.py
git commit -m "이진 병합 사건 추출과 자식 증거 계산 추가"
```

---

### Task 4: Event-Only Replay and Post-Hoc GT Scoring

**Files:**
- Modify: `maple_bot/core/puzzle/binary_merge_shadow.py`
- Modify: `maple_bot/tests/test_binary_merge_shadow.py`

**Interfaces:**
- Consumes: trace JSONL and optional score JSONL.
- Produces: `BinaryEventReplay`, `BinaryEventScore`, `replay_binary_merge_events()`, `score_binary_merge_events()`.

- [ ] **Step 1: Write failing runtime-GT separation tests**

Create one trace fixture and two score fixtures with different GT target children. Assert that `replay_binary_merge_events(trace_path)` returns byte-for-byte equivalent runtime decisions for both scoring runs. Only `score_binary_merge_events()` may produce different correctness labels.

- [ ] **Step 2: Run the separation test and verify RED**

Run the focused test and expect missing replay/scoring interfaces.

- [ ] **Step 3: Implement event replay results**

```python
class BinaryEventOutcome(str, Enum):
    CORRECT_TRANSFER = "correct_transfer"
    WRONG_SWITCH = "wrong_switch"
    SAFE_HOLD = "safe_hold"
    LATE_RECOVERY = "late_recovery"
    TARGET_NOT_IN_CANDIDATES = "target_not_in_candidates"
    EVENT_DETECTION_FAILURE = "event_detection_failure"
    DUPLICATE_DETECTION_UNRESOLVED = "duplicate_detection_unresolved"


@dataclass(frozen=True)
class BinaryEventReplay:
    event_id: int
    premerge_frame: int
    split_frame: int | None
    decision_frame: int | None
    split_observations_evaluated: int
    selected_target_candidate_id: str | None
    selected_background_candidate_id: str | None
    decision_reason: str
    hold: bool
    diagnostics: dict[str, object]


def replay_binary_merge_events(
    trace_jsonl: str | Path,
) -> tuple[BinaryEventReplay, ...]:
    rows = _read_jsonl(Path(trace_jsonl))
    frame_shape = _board_frame_shape(rows)
    profile = _profile_from_preparation_rows(rows, frame_shape)
    extraction = extract_binary_merge_events(rows)
    resolver = BinaryMergeIdentityResolver()
    replays: list[BinaryEventReplay] = []
    for event in extraction.events:
        decisions: list[tuple[int, BinaryTransferDecision]] = []
        for observation in event.split_observations:
            child_a, child_b = observation.children
            evidence = _evidence_for_frame(rows, observation.frame_index)
            role_a = build_child_evidence(
                event=event,
                child=child_a,
                other_child=child_b,
                context_candidates=observation.context_candidates,
                flow_profile=profile,
                evidence=evidence,
                frame_shape=frame_shape,
            )
            role_b = build_child_evidence(
                event=event,
                child=child_b,
                other_child=child_a,
                context_candidates=observation.context_candidates,
                flow_profile=profile,
                evidence=evidence,
                frame_shape=frame_shape,
            )
            decision = resolver.evaluate(event_id=event.event_id, child_a=role_a, child_b=role_b)
            decisions.append((observation.frame_index, decision))
            if decision.status is BinaryTransferStatus.RESOLVED:
                break
        replays.append(_event_replay_from_decisions(event, decisions))
    return tuple(replays)
```

The replay function must never accept a score or GT path. Implement `_read_jsonl()`, `_board_frame_shape()`, `_profile_from_preparation_rows()`, `_evidence_for_frame()` and `_event_replay_from_decisions()` in this module. Each helper consumes trace data only. `_event_replay_from_decisions()` records the first split frame, the resolving frame if present and the number of split observations evaluated. It returns HOLD when all available split observations remain ambiguous. Extraction diagnostics are converted into replay rows with no selected IDs so `EVENT_DETECTION_FAILURE` and `DUPLICATE_DETECTION_UNRESOLVED` remain scoreable outcomes.

- [ ] **Step 4: Implement post-hoc event scoring**

```python
@dataclass(frozen=True)
class BinaryEventScore:
    event_id: int
    outcome: BinaryEventOutcome
    target_candidate_id: str | None
    selected_candidate_id: str | None
    recovery_delay_ratio: float | None
    reason: str


def score_binary_merge_events(
    replays: Sequence[BinaryEventReplay],
    score_jsonl: str | Path,
    trace_jsonl: str | Path,
) -> tuple[BinaryEventScore, ...]:
    score_rows = _read_jsonl(Path(score_jsonl))
    trace_rows = _read_jsonl(Path(trace_jsonl))
    candidate_rows = _candidate_rows_by_frame(trace_rows)
    results: list[BinaryEventScore] = []
    for replay in replays:
        scoring_frame = replay.decision_frame or replay.split_frame
        target_point = _aligned_target_point(score_rows, scoring_frame)
        target_candidate_id = _target_child_id(target_point, scoring_frame, candidate_rows)
        results.append(_score_one_event(replay, target_candidate_id))
    return tuple(results)
```

GT association happens only here. Implement `_candidate_rows_by_frame()`, `_aligned_target_point()`, `_target_child_id()` and `_score_one_event()` as scoring-only helpers. The correct split child is the physical candidate whose center or box contains the aligned GT target after separation. If neither child covers the GT target, report `TARGET_NOT_IN_CANDIDATES` rather than blaming the selector. Compute `recovery_delay_ratio` as the zero-based resolving observation index divided by `max(1, split_observations_evaluated - 1)` so it does not depend on absolute frame rate.

- [ ] **Step 5: Add event metric summary and compact Markdown renderer**

Add `BinaryEventSummary` with counts for all outcomes, total events, resolved events, wrong switches and median normalized recovery delay. The Markdown renderer must include each event's H1/H2 judge contributions and HOLD reason. It must not render all successful frames.

- [ ] **Step 6: Run Task 4 tests and commit**

Run all three binary merge test files. Commit only Task 4 source and test changes.

```powershell
git add -- core/puzzle/binary_merge_shadow.py tests/test_binary_merge_shadow.py
git commit -m "이진 병합 사건 replay와 사후 채점 추가"
```

---

### Task 5: One Representative Event Gate

**Files:**
- Modify: `maple_bot/core/puzzle/binary_merge_shadow.py`
- Modify: `maple_bot/tests/test_binary_merge_shadow.py`
- Create: `03_output/2026-07-27_binary_merge_identity_transfer_validation_v1.md`

**Interfaces:**
- Consumes: the existing representative trace and score files documented in `2026-07-24_full_cycle_merge_lineage_validation_v1.md`.
- Produces: one event-only validation report and an explicit stop/expand verdict.

- [ ] **Step 1: Add a CLI dry-run test**

Add a test invoking the module with these arguments.

```text
python -m core.puzzle.binary_merge_shadow --trace C:\Users\PC\Desktop\02_work\05_AI\03_output\2026-07-20_studio_hypothesis_live_validation_v1\20260720_143934_studio\sessions\2026-07-20_transparent_puzzle_sessions\20260720_143937_001\trace.jsonl --score C:\Users\PC\Desktop\02_work\05_AI\03_output\2026-07-20_studio_hypothesis_live_validation_v1\20260720_143934_studio\validation_partial\score.jsonl --output C:\Users\PC\Desktop\02_work\05_AI\03_output\2026-07-27_binary_merge_identity_transfer_validation_v1\representative_event_001 --event-limit 1
```

Assert that the output contains one event, no mouse action field, a runtime decision, post-hoc score and judge diagnostics.

- [ ] **Step 2: Implement the CLI without video output**

The CLI must write only these files.

- `binary_merge_events.jsonl` with one row per event.
- `binary_merge_validation.md` with summary and judge contributions.

Do not create a video. Create at most two diagnostic images only when the event fails, and only if an existing board video can be decoded without adding dependencies.

- [ ] **Step 3: Run the complete focused test suite**

Run:

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe' -m pytest tests\test_binary_merge_identity.py tests\test_binary_merge_background.py tests\test_binary_merge_shadow.py tests\test_merge_split_relative.py tests\test_studio_hypothesis_shadow.py -q -p no:cacheprovider
```

Expected: all existing and new tests pass.

- [ ] **Step 4: Run exactly one representative merge event**

Use the documented representative trace and score paths. Run with `--event-limit 1`. Do not run a second event during this step.

- [ ] **Step 5: Apply the Gate 1 decision**

Pass only when all conditions hold.

- One physical binary merge event is detected.
- No target decision is made while the event is merged.
- The correct split child receives target identity.
- Wrong switch count is zero.
- Runtime replay output is unchanged when GT score input is altered in tests.

If any condition fails, stop expansion. Record the failing stage as event detection, candidate normalization, background judge, target judge, ancestry, ambiguity or candidate absence. Do not tune several thresholds at once.

- [ ] **Step 6: Write and commit the validation result**

Update the validation document with exact counts and paths. Commit code/test changes separately from the result document so the experiment is reversible.

```powershell
git add -- core/puzzle/binary_merge_shadow.py tests/test_binary_merge_shadow.py
git commit -m "이진 병합 대표 사건 검증 명령 추가"
git add -- ..\03_output\2026-07-27_binary_merge_identity_transfer_validation_v1.md
git commit -m "이진 병합 대표 사건 검증 결과 기록"
```

---

### Task 6: Conditional Opt-In Studio Diagnostics

**Precondition:** Execute this task only if Gate 1 passes. If Gate 1 fails, leave this task unchecked and do not modify existing replay code.

**Files:**
- Modify: `maple_bot/core/puzzle/studio_hypothesis_shadow.py:652-685`
- Modify: `maple_bot/tests/test_studio_hypothesis_shadow.py`

**Interfaces:**
- Consumes: `BinaryEventReplay` diagnostics.
- Produces: optional `binary_merge_identity` detail block in Studio shadow rows.

- [ ] **Step 1: Write an opt-in isolation test**

Run the same synthetic trace with `binary_merge_identity=False` and `True`. Assert the false path is exactly unchanged. Assert the true path adds diagnostics but does not alter `replay_point` or `replay_source` yet.

- [ ] **Step 2: Add a keyword-only opt-in parameter**

Add `binary_merge_identity: bool = False` to `replay_hypothesis_selection()` and `replay_hypothesis_selection_details()`. Instantiate the event shadow only when true.

- [ ] **Step 3: Attach diagnostics without selection authority**

Add a `binary_merge_identity` detail block containing event ID, state, H1/H2 costs, support groups, decision status, selected target ID and HOLD reason. Do not modify the selected point in this task.

- [ ] **Step 4: Run the focused and regression tests**

Run all five test files from Task 5. Verify opt-out results remain unchanged.

- [ ] **Step 5: Commit the conditional integration**

```powershell
git add -- core/puzzle/studio_hypothesis_shadow.py tests/test_studio_hypothesis_shadow.py
git commit -m "Studio에 이진 병합 shadow 진단 연결"
```

---

## Final Review and Expansion Rules

- Each task receives a spec review and code-quality review before the next task starts.
- Parent environment reruns the exact focused tests after every worker commit.
- Gate 1 failure stops execution before Task 6.
- Gate 1 success permits same-session event expansion, then seed 3, then seed 10.
- Actual `puzzle.py` target selection authority is a separate future design and is not granted by this plan.
- No successful-event videos are retained. Failed-event evidence is capped at two images and one compact report.
