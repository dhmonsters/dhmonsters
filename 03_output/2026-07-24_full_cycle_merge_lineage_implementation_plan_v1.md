# Full-Cycle Merge Lineage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 한 주기 동안 신분이 확인된 배경 도형만 기준점으로 사용하고, 타겟과 배경의 병합을 하나의 사건으로 유지해 분리된 실제 두 자식의 신분을 복원한다.

**Architecture:** 기존 `BackgroundCatalog`가 제공하는 주기와 local lag를 재사용한다. `merge_split_relative.py`는 개별 배경 트랙의 전체 주기 생존 자격, 병합 사건 컨텍스트, 같은 사건의 두 분리 자식, 위상 보정 상대좌표 판정을 담당한다. 기능은 먼저 Studio의 opt-in shadow replay에만 연결하고 대표 1판에서 순개선과 무손실을 확인한 뒤 검증 범위를 늘린다.

**Tech Stack:** Python 3.14, dataclasses, unittest/pytest, 기존 `BackgroundCatalog`, Studio JSONL replay, openpyxl 기반 기존 보고서 경로.

## Global Constraints

- 고정 목표는 “처음 흰색 타겟의 신분을 잃지 않고 끝까지 따라가는 시간축 판별기를 만든다.”이다.
- 실행 중 GT 좌표를 입력으로 사용하지 않는다. GT는 replay 종료 후 채점에만 사용한다.
- 특정 프레임 번호, 화면 좌표, 절대 거리, 고정 회전 방향을 규칙에 넣지 않는다.
- 거리와 여백은 현재 도형의 대표 크기로 정규화한다.
- 전체 주기 생존은 가중치가 아니라 background anchor의 hard gate다.
- anchor 자격이나 자식 계보가 불확실하면 후보를 바꾸지 않고 HOLD한다.
- 첫 구현은 opt-in shadow와 마우스 OFF 상태를 유지한다.
- 대표 1판에서 `improved_frames >= 1`이고 `regressed_frames == 0`일 때만 검증 범위를 확대한다.

---

## File Structure

- Modify `maple_bot/core/vision/transparent_puzzle_engine.py`.
  기존 background catalog의 local lag 선택을 public read-only API로 노출한다.
- Modify `maple_bot/core/puzzle/merge_split_relative.py`.
  전체 주기 anchor 자격, 사건 컨텍스트, 두 자식 계보, 위상 상대좌표 판정을 구현한다.
- Modify `maple_bot/core/puzzle/studio_hypothesis_shadow.py`.
  trace 후보를 catalog에 공급하고 period/lag를 resolver로 전달하며 진단 정보를 기록한다.
- Modify `maple_bot/tests/test_transparent_puzzle_engine.py`.
  local lag public API의 기존 알고리즘 재사용을 검증한다.
- Modify `maple_bot/tests/test_merge_split_relative.py`.
  anchor 생존, 경계 이탈, 사건 ID, 자식 계보와 HOLD를 단위 검증한다.
- Modify `maple_bot/tests/test_studio_hypothesis_shadow.py`.
  runtime GT 없이 주기 학습과 병합 복원이 연결되는지 통합 검증한다.
- Create `03_output/2026-07-24_full_cycle_merge_lineage_validation_v1.md`.
  대표 1판부터 확대 관문까지 실제 수치와 중단 이유를 기록한다.

## Task 1. 기존 catalog의 local lag를 public API로 노출

**Files:**
- Modify: `maple_bot/core/vision/transparent_puzzle_engine.py:125-150`
- Test: `maple_bot/tests/test_transparent_puzzle_engine.py`

**Interfaces:**
- Consumes: `BackgroundCatalog._choose_local_lag(frame_index, period, search)`.
- Produces: `BackgroundCatalog.choose_local_lag(frame_index: int, period: int, local_search: int = 8) -> int`.

- [ ] **Step 1: public API가 기존 local lag를 반환하는 실패 테스트를 작성한다.**

```python
def test_catalog_exposes_measured_local_lag(self):
    catalog = BackgroundCatalog()
    for frame in range(8):
        x = float((frame % 3) * 10)
        catalog.add_frame(frame, [PuzzleCandidate(x, 0.0, 1.0, 20.0, 20.0)])

    self.assertEqual(
        catalog.choose_local_lag(frame_index=7, period=3, local_search=1),
        3,
    )
```

- [ ] **Step 2: 테스트가 API 부재로 실패하는지 확인한다.**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_transparent_puzzle_engine.py::TransparentPuzzleEngineTests::test_catalog_exposes_measured_local_lag -q`

Expected: `AttributeError: 'BackgroundCatalog' object has no attribute 'choose_local_lag'`.

- [ ] **Step 3: private 알고리즘을 그대로 호출하는 최소 public wrapper를 추가한다.**

```python
def choose_local_lag(
    self,
    frame_index: int,
    period: int,
    local_search: int = 8,
) -> int:
    return self._choose_local_lag(
        int(frame_index),
        int(period),
        int(local_search),
    )
```

- [ ] **Step 4: catalog 테스트 전체를 통과시킨다.**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_transparent_puzzle_engine.py maple_bot/tests/test_phase_catalog_solver.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 5: Task 1만 커밋한다.**

```powershell
git add -- maple_bot/core/vision/transparent_puzzle_engine.py maple_bot/tests/test_transparent_puzzle_engine.py
git commit --only -m "투명도형 catalog local lag 공개" -- maple_bot/core/vision/transparent_puzzle_engine.py maple_bot/tests/test_transparent_puzzle_engine.py
```

## Task 2. 전체 주기 생존 background anchor 자격 구현

**Files:**
- Modify: `maple_bot/core/puzzle/merge_split_relative.py:40-145`
- Test: `maple_bot/tests/test_merge_split_relative.py:349-456`

**Interfaces:**
- Consumes: 후보의 `frame_index`, `bbox`, `center`, `CandidateEvidence`, 주기와 local lag.
- Produces: `CyclePhaseContext`, 확장된 `BackgroundAnchor`, `BackgroundAnchorManager.track_id_for_candidate()`, `BackgroundAnchorManager.reference_anchor()`.

- [ ] **Step 1: 주기 생존, 경계 이탈, 재진입, loop closure 실패 테스트를 작성한다.**

```python
def test_anchor_requires_full_cycle_survival_and_loop_closure(self):
    module = importlib.import_module("core.puzzle.merge_split_relative")
    manager = module.BackgroundAnchorManager(
        minimum_stable_observations=1,
        minimum_cycle_survival=0.95,
    )
    for frame, x in enumerate((20.0, 30.0, 40.0, 20.0)):
        anchors = manager.update(
            frame_index=frame,
            candidates=(_center_candidate(f"a-{frame}", (x, 40.0)),),
            target_candidate=None,
            evidence={},
            frame_shape=(100, 100),
            stable_scale_px=10.0,
            phase_context=module.CyclePhaseContext(period=3, local_lag=3),
        )

    self.assertEqual(len(anchors), 1)
    self.assertTrue(anchors[0].qualified_cycle)
    self.assertGreaterEqual(anchors[0].cycle_survival, 0.95)
```

```python
def test_anchor_that_leaves_frame_cannot_requalify_on_reentry(self):
    module = importlib.import_module("core.puzzle.merge_split_relative")
    manager = module.BackgroundAnchorManager(minimum_stable_observations=1)
    phase = module.CyclePhaseContext(period=3, local_lag=3)
    manager.update(frame_index=0, candidates=(_center_candidate("a0", (20.0, 40.0)),), target_candidate=None, evidence={}, frame_shape=(100, 100), stable_scale_px=10.0, phase_context=phase)
    manager.update(frame_index=1, candidates=(), target_candidate=None, evidence={}, frame_shape=(100, 100), stable_scale_px=10.0, phase_context=phase)
    manager.update(frame_index=2, candidates=(_center_candidate("a2", (40.0, 40.0)),), target_candidate=None, evidence={}, frame_shape=(100, 100), stable_scale_px=10.0, phase_context=phase)
    anchors = manager.update(frame_index=3, candidates=(_center_candidate("a3", (20.0, 40.0)),), target_candidate=None, evidence={}, frame_shape=(100, 100), stable_scale_px=10.0, phase_context=phase)

    self.assertFalse(any(anchor.qualified_cycle for anchor in anchors))
```

- [ ] **Step 2: 기존 manager가 주기 자격을 표현하지 못해 실패하는지 확인한다.**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_merge_split_relative.py -k "full_cycle or requalify or loop_closure" -q`

Expected: 새 자료형 또는 인자 부재로 FAIL.

- [ ] **Step 3: 자료형과 내부 트랙 기록을 추가한다.**

```python
@dataclass(frozen=True)
class CyclePhaseContext:
    period: int | None
    local_lag: int | None
    period_score: float | None = None


@dataclass(frozen=True)
class AnchorObservation:
    frame_index: int
    candidate_id: str
    point: Point
    bbox: tuple[float, float, float, float]
    area: float
    aspect: float
    clipped: bool
    merge_like: bool


@dataclass(frozen=True)
class BackgroundAnchor:
    track_id: str
    point: Point
    stable_observations: int
    clipped: bool = False
    candidate_id: str | None = None
    qualified_cycle: bool = False
    cycle_survival: float = 0.0
    loop_residual: float | None = None
    disqualified_reason: str | None = None
```

`BackgroundAnchorManager.update()`에는 하위 호환 기본값을 가진 인자를 추가한다.

```python
def __init__(
    self,
    *,
    minimum_stable_observations: int = 3,
    minimum_cycle_survival: float = 0.95,
    maximum_cycle_gap_ratio: float = 0.05,
    loop_position_tolerance: float = 0.75,
    loop_shape_tolerance: float = 0.25,
) -> None:
    self.minimum_stable_observations = max(1, int(minimum_stable_observations))
    self.minimum_cycle_survival = min(1.0, max(0.0, float(minimum_cycle_survival)))
    self.maximum_cycle_gap_ratio = min(1.0, max(0.0, float(maximum_cycle_gap_ratio)))
    self.loop_position_tolerance = max(0.0, float(loop_position_tolerance))
    self.loop_shape_tolerance = max(0.0, float(loop_shape_tolerance))
    self.reset()


def update(
    self,
    *,
    candidates: Sequence[Candidate],
    target_candidate: Candidate | None,
    evidence: Mapping[str, CandidateEvidence],
    frame_shape: tuple[int, int] | None,
    stable_scale_px: float,
    excluded_candidate_ids: Sequence[str] = (),
    frame_index: int | None = None,
    phase_context: CyclePhaseContext | None = None,
) -> tuple[BackgroundAnchor, ...]:


def track_id_for_candidate(self, candidate_id: str) -> str | None:
    return self._candidate_track_ids.get(str(candidate_id))


def reference_anchor(
    self,
    track_id: str,
    frame_index: int,
) -> BackgroundAnchor | None:
    track = self._tracks.get(str(track_id))
    if track is None:
        return None
    observation = track.observations.get(int(frame_index))
    if observation is None:
        return None
    return BackgroundAnchor(
        track_id=track.track_id,
        point=observation.point,
        stable_observations=len(track.observations),
        clipped=observation.clipped,
        candidate_id=observation.candidate_id,
        qualified_cycle=track.qualified_cycle,
        cycle_survival=track.cycle_survival,
        loop_residual=track.loop_residual,
        disqualified_reason=track.disqualified_reason,
    )
```

내부 트랙은 관찰 사전과 마지막 두 점을 보존한다. 자격은 `period_score / stable_scale_px`, 주기 구간 생존율, 최대 공백 비율, 경계 안전도, 위치 loop residual, 면적과 종횡비 오차를 모두 통과할 때만 부여한다.

- [ ] **Step 4: 기존 anchor 테스트와 새 주기 테스트를 모두 통과시킨다.**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_merge_split_relative.py -k "BackgroundAnchorManager or full_cycle or loop_closure" -q`

Expected: 모든 선택 테스트 PASS.

- [ ] **Step 5: Task 2만 커밋한다.**

```powershell
git add -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
git commit --only -m "투명도형 전체 주기 배경 기준점 추가" -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
```

## Task 3. 병합 사건 ID와 참가자 계보를 한 사건으로 고정

**Files:**
- Modify: `maple_bot/core/puzzle/merge_split_relative.py:275-455`
- Test: `maple_bot/tests/test_merge_split_relative.py:83-348`

**Interfaces:**
- Consumes: 신뢰 가능한 incumbent, collision 후보의 안정 track ID, qualified 주변 anchor ID.
- Produces: `MergeEventContext`, 한 번만 증가하는 `event_id`, 사건 종료 전 고정된 참가자.

- [ ] **Step 1: 부분 겹침, 완전 병합, 분리, 재획득이 같은 event ID를 유지하는 실패 테스트를 작성한다.**

```python
def test_one_merge_lifecycle_keeps_one_event_id(self):
    module = importlib.import_module("core.puzzle.merge_split_relative")
    detector = module.MergeSplitEventDetector(confirm_observations=1)
    target = _center_candidate("target", (40.0, 50.0), size=10.0)
    background = _center_candidate("background", (46.0, 50.0), size=10.0)
    partial = detector.update(target_candidate=target, candidates=(target, background), stable_area=100.0, predicted_target_point=target.center)
    merged_box = _center_candidate("merged", (45.0, 50.0), size=15.0)
    merged = detector.update(target_candidate=None, candidates=(merged_box,), stable_area=100.0, predicted_target_point=(42.0, 50.0))
    split = detector.update(target_candidate=None, candidates=(target, background), stable_area=100.0, predicted_target_point=(44.0, 50.0))

    self.assertEqual({partial.event_id, merged.event_id, split.event_id}, {1})
```

- [ ] **Step 2: 현재 detector가 상태 전환마다 event ID를 올려 실패하는지 확인한다.**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_merge_split_relative.py -k "one_merge_lifecycle" -q`

Expected: event ID 집합이 `{1}`이 아니어서 FAIL.

- [ ] **Step 3: 사건 컨텍스트를 추가하고 event ID 증가 지점을 사건 개방 시점으로 제한한다.**

```python
@dataclass
class MergeEventContext:
    event_id: int
    target_candidate_id: str
    background_track_id: str
    anchor_track_ids: tuple[str, ...]
    premerge_target_point: Point
    premerge_target_bbox: tuple[float, float, float, float]
    premerge_background_bbox: tuple[float, float, float, float]
    merge_bbox: tuple[float, float, float, float] | None
    opened_frame: int
    last_frame: int
```

`MergeSplitEventDetector._set_state()`는 `SEPARATE` 또는 종료 상태에서 `PARTIAL_OVERLAP`/`MERGED`로 처음 진입할 때만 `event_id`를 증가시킨다. `PARTIAL_OVERLAP -> MERGED -> SPLITTING -> REACQUIRED`는 동일 ID를 유지한다.

- [ ] **Step 4: 사건 상태기계 테스트 전체를 통과시킨다.**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_merge_split_relative.py -k "MergeSplitEventDetector or one_merge_lifecycle" -q`

Expected: 모든 선택 테스트 PASS.

- [ ] **Step 5: Task 3만 커밋한다.**

```powershell
git add -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
git commit --only -m "투명도형 병합 사건 계보 고정" -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
```

## Task 4. 같은 사건의 실제 분리 자식 두 개만 선별

**Files:**
- Modify: `maple_bot/core/puzzle/merge_split_relative.py:170-270,403-560`
- Test: `maple_bot/tests/test_merge_split_relative.py:457-650`

**Interfaces:**
- Consumes: `MergeEventContext`, 병합 박스, 병합 전 두 참가자 박스, 현재 후보.
- Produces: `SplitChildPair`, `select_split_child_pair()`.

- [ ] **Step 1: 먼 방해 후보와 새로 들어온 후보를 제외하고 실제 두 자식만 반환하는 실패 테스트를 작성한다.**

```python
def test_split_pair_contains_only_event_descendants(self):
    module = importlib.import_module("core.puzzle.merge_split_relative")
    context = module.MergeEventContext(
        event_id=1,
        target_candidate_id="target-before-merge",
        background_track_id="background-track",
        anchor_track_ids=("anchor-a", "anchor-b"),
        premerge_target_point=(35.0, 45.0),
        premerge_target_bbox=(30.0, 40.0, 40.0, 50.0),
        premerge_background_bbox=(38.0, 40.0, 48.0, 50.0),
        merge_bbox=(30.0, 40.0, 48.0, 50.0),
        opened_frame=12,
        last_frame=14,
    )
    pair = module.select_split_child_pair(
        context=context,
        candidates=(
            _candidate("target-child", (32.0, 40.0, 42.0, 50.0)),
            _candidate("background-child", (40.0, 40.0, 50.0, 50.0)),
            _candidate("near-distractor", (24.0, 36.0, 34.0, 46.0)),
            _candidate("far-distractor", (80.0, 80.0, 90.0, 90.0)),
        ),
        predicted_target_point=(38.0, 45.0),
        stable_scale_px=10.0,
    )

    self.assertEqual(
        {candidate.candidate_id for candidate in pair.children},
        {"target-child", "background-child"},
    )
```

- [ ] **Step 2: 현재 local radius 방식이 세 후보를 남겨 실패하는지 확인한다.**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_merge_split_relative.py -k "event_descendants" -q`

Expected: `select_split_child_pair` 부재 또는 잘못된 후보 쌍으로 FAIL.

- [ ] **Step 3: 자식 쌍 자료형과 pair scoring을 구현한다.**

```python
@dataclass(frozen=True)
class SplitChildPair:
    children: tuple[Candidate, Candidate]
    union_residual: float
    ancestry_residual: float
    score_margin: float


def select_split_child_pair(
    *,
    context: MergeEventContext,
    candidates: Sequence[Candidate],
    predicted_target_point: Point,
    stable_scale_px: float,
) -> SplitChildPair | None:
```

모든 후보 쌍에 대해 다음 무차원 비용을 계산한다.

```python
pair_cost = (
    union_residual
    + 0.75 * ancestry_shape_residual
    + 0.50 * merge_region_residual
    + 0.25 * predicted_target_residual
)
```

최상위 두 pair의 차이가 최소 margin보다 작으면 `None`을 반환해 HOLD한다. 방향과 좌표는 비용에 넣지 않는다.

- [ ] **Step 4: resolver가 `assign_split_children()`에 전체 local 후보가 아니라 선택된 두 자식만 전달하도록 수정하고 테스트한다.**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_merge_split_relative.py -k "split_pair or split_assignment or restores_non_background" -q`

Expected: 모든 선택 테스트 PASS.

- [ ] **Step 5: Task 4만 커밋한다.**

```powershell
git add -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
git commit --only -m "투명도형 병합 분리 자식 계보 선별" -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
```

## Task 5. 위상 보정 상대좌표와 HOLD 판정 연결

**Files:**
- Modify: `maple_bot/core/puzzle/merge_split_relative.py:130-270,403-590`
- Test: `maple_bot/tests/test_merge_split_relative.py`

**Interfaces:**
- Consumes: collision background track의 `frame_index - local_lag` 관찰, 현재 qualified anchor, `SplitChildPair`.
- Produces: phase-conditioned `RelationFingerprint`, anchor quorum, 구체적인 HOLD 이유.

- [ ] **Step 1: raw 거리는 달라도 같은 위상 관계를 보존한 자식을 배경으로 고르는 실패 테스트를 작성한다.**

```python
def test_phase_conditioned_relation_survives_global_distortion(self):
    module = importlib.import_module("core.puzzle.merge_split_relative")
    reference_anchors = (
        module.BackgroundAnchor("a", (10.0, 10.0), 20, qualified_cycle=True),
        module.BackgroundAnchor("b", (30.0, 10.0), 20, qualified_cycle=True),
    )
    current_anchors = (
        module.BackgroundAnchor("a", (20.0, 20.0), 21, qualified_cycle=True),
        module.BackgroundAnchor("b", (60.0, 20.0), 21, qualified_cycle=True),
    )
    fingerprint = module.RelationFingerprint.from_observations(
        background_point=(20.0, 14.0),
        anchors=reference_anchors,
        jitter=0.05,
    )
    decision = module.assign_split_children(
        children=(
            _center_candidate("background-child", (40.0, 28.0)),
            _center_candidate("target-child", (48.0, 34.0)),
        ),
        anchors=current_anchors,
        fingerprint=fingerprint,
        predicted_target_point=(48.0, 34.0),
    )

    self.assertEqual(decision.background_candidate_id, "background-child")
    self.assertEqual(decision.target_candidate_id, "target-child")
```

- [ ] **Step 2: qualified anchor가 부족하거나 anchor들이 다른 답을 내면 HOLD하는 테스트를 작성하고 실패를 확인한다.**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_merge_split_relative.py -k "phase_conditioned or qualified_quorum" -q`

Expected: qualified hard gate 부재로 FAIL.

- [ ] **Step 3: fingerprint 생성 시 collision 참가자를 anchor 쌍에서 제외하고 같은 위상 관찰만 사용한다.**

```python
reference_frame = current_frame - phase_context.local_lag
reference_background = anchor_manager.reference_anchor(
    context.background_track_id,
    reference_frame,
)
reference_anchors = tuple(
    anchor_manager.reference_anchor(track_id, reference_frame)
    for track_id in context.anchor_track_ids
)
```

`assign_split_children()`는 `qualified_cycle=True`인 anchor만 사용한다. 유효 anchor pair가 없으면 `insufficient_cycle_anchors`, 상대좌표 margin이 작으면 `ambiguous_phase_relation`, 같은 사건의 자식 pair가 없으면 `missing_split_pair`로 HOLD한다.

- [ ] **Step 4: merge-relative 테스트 전체를 통과시킨다.**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_merge_split_relative.py -q`

Expected: 전체 PASS.

- [ ] **Step 5: Task 5만 커밋한다.**

```powershell
git add -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
git commit --only -m "투명도형 위상 상대좌표 신분 복원" -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
```

## Task 6. Studio shadow에 period/lag와 진단 로그 연결

**Files:**
- Modify: `maple_bot/core/puzzle/studio_hypothesis_shadow.py:107-380`
- Test: `maple_bot/tests/test_studio_hypothesis_shadow.py:344-525`

**Interfaces:**
- Consumes: `BackgroundCatalog`, white anchor 종료, frame candidate sets.
- Produces: 매 프레임 `CyclePhaseContext`, `merge_split_relative` 진단 필드.

- [ ] **Step 1: white anchor 구간의 후보 반복으로 period를 추정하고 GT 없이 resolver에 전달하는 통합 실패 테스트를 작성한다.**

```python
def test_merge_split_shadow_reports_cycle_phase_without_runtime_gt(self):
    with TemporaryDirectory(prefix="studio-cycle-lineage-") as tmp:
        root = Path(tmp)
        score_path = root / "score.jsonl"
        trace_path = root / "trace.jsonl"
        scores: list[dict[str, object]] = []
        trace: list[dict[str, object]] = [
            {
                "type": "SESSION_START",
                "frame_index": None,
                "payload": {"board_roi": {"w": 120, "h": 100}},
            }
        ]
        for frame in range(10):
            phase = frame % 3
            anchor_a = (20.0 + phase * 2.0, 20.0)
            anchor_b = (80.0 + phase * 2.0, 20.0)
            background = (48.0 + phase * 2.0, 50.0)
            target = (
                (60.0, 50.0)
                if frame < 6
                else (58.0 + float(frame - 6), 50.0)
            )
            candidates = [
                _trace_candidate(f"anchor-a-{frame}", anchor_a),
                _trace_candidate(f"anchor-b-{frame}", anchor_b),
                _trace_candidate(f"background-{frame}", background),
                _trace_candidate(f"target-{frame}", target),
            ]
            scores.append(
                {
                    "solver_frame_index": frame,
                    "target_x": target[0],
                    "target_y": target[1],
                }
            )
            trace.append(
                {
                    "type": "CANDIDATES",
                    "frame_index": frame,
                    "payload": {"candidates": candidates},
                }
            )
            if frame < 6:
                trace.append(
                    {
                        "type": "TEMPORAL_SELECTOR",
                        "frame_index": frame,
                        "payload": {
                            "debug": {
                                "kinematic_wide_beam_debug": {
                                    "reason": "white_anchor",
                                    "point": [target[0], target[1]],
                                }
                            }
                        },
                    }
                )
            trace.extend(
                [
                    {
                        "type": "EVIDENCE",
                        "frame_index": frame,
                        "payload": {
                            "evidence": [
                                {
                                    "candidate_id": row["candidate_id"],
                                    "bg_score": (
                                        0.1
                                        if row["candidate_id"].startswith("target-")
                                        else 0.8
                                    ),
                                }
                                for row in candidates
                            ]
                        },
                    },
                    {
                        "type": "TARGET_SELECTION",
                        "frame_index": frame,
                        "payload": {
                            "point": [target[0], target[1]],
                            "source": "recorded",
                        },
                    },
                ]
            )
        _write_jsonl(score_path, scores)
        _write_jsonl(trace_path, trace)

        details = replay_hypothesis_selection_details(
            score_path,
            trace_path,
            merge_split_relative=True,
        )

        phased = [
            row["merge_split_relative"]
            for row in details
            if row["merge_split_relative"].get("period") is not None
        ]
        self.assertTrue(phased)
        self.assertEqual(phased[-1]["period"], 3)
        self.assertEqual(phased[-1]["local_lag"], 3)
        self.assertGreaterEqual(phased[-1]["qualified_anchor_count"], 2)
        self.assertNotIn("target_point", phased[-1]["cycle_input"])
```

테스트 trace는 배경 후보가 3프레임 주기로 반복되고 white anchor가 준비 구간에만 존재하도록 만든다. `score.jsonl`은 결과 채점에만 제공하고 period 입력에는 사용하지 않는다.

- [ ] **Step 2: 현재 shadow에 catalog phase가 없어 실패하는지 확인한다.**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_studio_hypothesis_shadow.py -k "cycle_phase_without_runtime_gt" -q`

Expected: `period` 또는 `qualified_anchor_count` 필드 부재로 FAIL.

- [ ] **Step 3: replay loop에 catalog 수집과 phase context 생성을 추가한다.**

```python
catalog = BackgroundCatalog()
catalog_period: int | None = None
catalog_period_score: float | None = None
was_white = False
```

white anchor와 가장 가까운 후보는 준비 구간 catalog에서 제외한다. white anchor가 사라지는 전환에서 `estimate_period()`를 한 번 호출하고, 이후 프레임마다 `choose_local_lag()`로 local lag를 구한다.

```python
catalog_candidates = list(candidates)
if anchor is not None and catalog_candidates:
    white_candidate = min(
        catalog_candidates,
        key=lambda candidate: _distance(candidate.center, anchor),
    )
    catalog_candidates = [
        candidate
        for candidate in catalog_candidates
        if candidate.candidate_id != white_candidate.candidate_id
    ]
catalog.add_frame(
    frame_index,
    [
        PuzzleCandidate(
            cx=candidate.center[0],
            cy=candidate.center[1],
            score=candidate.score,
            w=max(1.0, candidate.bbox[2] - candidate.bbox[0]),
            h=max(1.0, candidate.bbox[3] - candidate.bbox[1]),
        )
        for candidate in catalog_candidates
    ],
)

if anchor is not None:
    was_white = True
elif was_white and catalog_period is None:
    search = min(24, max(2, frame_index - 2))
    catalog_period, catalog_period_score = catalog.estimate_period(
        prep_end=frame_index,
        min_lag=max(2, frame_index - search),
        max_lag=frame_index,
    )
    was_white = False
```

```python
phase_context = CyclePhaseContext(
    period=catalog_period,
    local_lag=(
        catalog.choose_local_lag(frame_index, catalog_period)
        if catalog_period is not None else None
    ),
    period_score=catalog_period_score,
)
```

`merge_resolver.update()`에 다음 값을 전달한다.

```python
merge_decision = merge_resolver.update(
    frame_index=frame_index,
    incumbent_point=replay_point,
    candidates=candidates,
    evidence=evidence,
    stable_area=_stable_target_area(
        candidates,
        incumbent_point=replay_point,
        anchor_shapes=anchor_shapes,
    ),
    frame_shape=frame_shape,
    phase_context=phase_context,
    identity_state=identity_state,
)
```

- [ ] **Step 4: 상세 로그에 사건과 anchor 탈락 이유를 기록하고 통합 테스트를 통과시킨다.**

```python
detail["merge_split_relative"] = {
    **merge_decision.debug,
    "state": merge_decision.state.name,
    "reason": merge_decision.reason,
    "period": phase_context.period,
    "local_lag": phase_context.local_lag,
    "qualified_anchor_count": merge_decision.debug.get("qualified_anchor_count", 0),
}
```

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_studio_hypothesis_shadow.py maple_bot/tests/test_merge_split_relative.py maple_bot/tests/test_transparent_puzzle_engine.py -q`

Expected: 전체 PASS.

- [ ] **Step 5: Task 6만 커밋한다.**

```powershell
git add -- maple_bot/core/puzzle/studio_hypothesis_shadow.py maple_bot/tests/test_studio_hypothesis_shadow.py
git commit --only -m "Studio 전체 주기 병합 계보 shadow 연결" -- maple_bot/core/puzzle/studio_hypothesis_shadow.py maple_bot/tests/test_studio_hypothesis_shadow.py
```

## Task 7. 대표 1판 검증과 확대 관문 판정

**Files:**
- Create: `03_output/2026-07-24_full_cycle_merge_lineage_validation_v1.md`
- Modify only if a general failure cause is proven: files from Tasks 1-6 and their matching tests.

**Interfaces:**
- Consumes: `2026-07-20_studio_hypothesis_live_validation_v1`의 한 세션, 기존 baseline, 새 opt-in shadow.
- Produces: baseline/replay/개선/손실, 사건별 실패 분류, 확대 또는 중단 판정.

- [ ] **Step 1: 관련 회귀 테스트를 먼저 실행한다.**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest maple_bot/tests/test_transparent_puzzle_engine.py maple_bot/tests/test_merge_split_relative.py maple_bot/tests/test_studio_hypothesis_shadow.py -q`

Expected: 전체 PASS.

- [ ] **Step 2: 대표 세션 한 개만 처음부터 끝까지 replay한다.**

Input session: `03_output/2026-07-20_studio_hypothesis_live_validation_v1/20260720_143934_studio/sessions/2026-07-20_transparent_puzzle_sessions/20260720_143937_001`

실행은 `replay_hypothesis_selection_details(score.jsonl, trace.jsonl, merge_split_relative=True)`를 사용한다. 프레임 일부만 잘라 재생하지 않는다.

Expected gate: `improved_frames >= 1`, `regressed_frames == 0`.

- [ ] **Step 3: 기대값을 만족하지 않으면 횟수를 늘리지 않고 한 단계의 원인만 분류한다.**

분류 값은 다음 중 하나다.

```text
period_unavailable
cycle_anchor_unqualified
event_not_opened
event_reopened
split_pair_missing
phase_relation_ambiguous
quorum_blocked
candidate_oracle_gap
```

분류 뒤 일반 규칙으로 수정할 수 있을 때만 대응 테스트를 먼저 추가한다. 특정 프레임, 좌표, 방향을 조건으로 쓰지 않는다.

- [ ] **Step 4: 대표 1판을 통과하면 보존판 1개, 혼합 3개, seed 10개 순으로 확대한다.**

각 관문은 이전 관문의 손실 0을 유지해야 한다. 실패하면 즉시 직전 관문으로 돌아가며 대량 영상을 새로 생성하지 않는다.

- [ ] **Step 5: 16GT와 새 랜덤판 검증 전후를 문서에 기록한다.**

16GT는 runtime GT 없이 16/16을 유지해야 한다. 새 랜덤판은 1개, 3개, 10개 순으로 확대하며 마우스 OFF와 표적 시각화 ON을 유지한다.

- [ ] **Step 6: 검증 문서만 별도 커밋한다.**

```powershell
git add -- 03_output/2026-07-24_full_cycle_merge_lineage_validation_v1.md
git commit --only -m "투명도형 전체 주기 병합 계보 검증 기록" -- 03_output/2026-07-24_full_cycle_merge_lineage_validation_v1.md
```

## Final Verification

- [ ] `git diff --check`가 통과한다.
- [ ] 관련 세 테스트 파일이 모두 통과한다.
- [ ] 대표 1판 결과가 `improved_frames >= 1`, `regressed_frames == 0`을 만족하거나, 확대하지 않은 명확한 실패 분류가 문서에 기록된다.
- [ ] runtime 입력에서 GT가 참조되지 않았음을 테스트와 로그로 확인한다.
- [ ] 기능은 여전히 opt-in shadow이고 마우스 제어는 OFF다.
- [ ] 성공 실험의 불필요한 대용량 영상은 만들지 않고, 실패 대표 이미지와 요약 문서만 남긴다.
