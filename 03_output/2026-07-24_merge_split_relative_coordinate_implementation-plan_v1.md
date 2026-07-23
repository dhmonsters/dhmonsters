# Merge-Split Relative Coordinate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 타겟 포함 병합 사건을 감지하고, 주변 배경 기준점과의 상대 좌표를 이용해 분리된 자식 중 배경을 제거한 뒤 타겟 신분을 복원한다.

**Architecture:** 순수 상대 좌표 계산, 병합 상태기계, 배경 기준점·계보 resolver를 `merge_split_relative.py`에 격리한다. resolver는 배경 자식과 타겟 도전 경로만 만들고, 확정은 사용자 정의 심판 그룹을 지원하도록 확장한 `PersistentEvidenceQuorum`이 담당한다. 첫 연결은 `studio_hypothesis_shadow.py`의 opt-in replay이며 라이브 `puzzle.py`는 변경하지 않는다.

**Tech Stack:** Python 3.14, 표준 라이브러리 `dataclasses`·`enum`·`math`·`statistics`, 기존 `Candidate`·`CandidateEvidence`, `unittest`, `pytest`.

## Global Constraints

- 실행 중 GT와 정답 좌표를 사용하지 않는다.
- 특정 좌표, 프레임 번호, 화면 방향, 고정 픽셀 거리를 규칙에 넣지 않는다.
- 모든 거리와 면적은 초기 도형 크기 또는 현재 판의 배경 흔들림으로 정규화한다.
- 관측 불가와 경계 잘림은 0점이 아니라 기권으로 처리한다.
- 병합 박스 중심으로 타겟 상태를 갱신하지 않는다.
- 상대 좌표와 local rigid를 독립 표 두 장으로 세지 않는다.
- 새 source 파일의 첫 줄에는 역할을 설명하는 한국어 주석을 둔다.
- 각 작업은 RED 확인, 최소 구현, 관련 회귀검사, 의미 단위 커밋 순서로 끝낸다.
- 기존 staged 변경은 커밋 경로에서 제외한다.

## File Map

- Create `maple_bot/core/puzzle/merge_split_relative.py` — 상대 좌표, 병합 상태, 기준점, 병합 계보와 분리 자식 배정을 담당한다.
- Create `maple_bot/tests/test_merge_split_relative.py` — 순수 기하 불변성, 상태 전환, 기권, 분리 배정을 검증한다.
- Modify `maple_bot/core/puzzle/persistent_evidence_quorum.py` — 기본값을 보존하면서 사용자 정의 support group을 허용한다.
- Modify `maple_bot/tests/test_persistent_evidence_quorum.py` — 사용자 정의 심판 그룹과 필수 주심을 검증한다.
- Modify `maple_bot/core/puzzle/studio_hypothesis_shadow.py:93-343` — opt-in 병합 resolver와 병합 전용 quorum을 replay에 연결하고 진단 detail을 남긴다.
- Modify `maple_bot/tests/test_studio_hypothesis_shadow.py:23-325` — 기본 비활성, opt-in 선택, trace detail을 검증한다.
- Modify `03_output/2026-07-24_merge_split_relative_coordinate_checklist_v1.md` — 작업과 검증 관문 상태를 갱신한다.
- Modify `03_output/2026-07-24_merge_split_relative_coordinate_context-notes_v1.md` — 실제 관측 결과와 채택·폐기 이유를 기록한다.

---

### Task 1: Relative Coordinate Geometry

**Files:**
- Create: `maple_bot/core/puzzle/merge_split_relative.py`
- Create: `maple_bot/tests/test_merge_split_relative.py`

**Interfaces:**
- Produces: `Point`, `RelativeCoordinate`, `relative_coordinate(point, anchor_a, anchor_b)`, `relative_coordinate_residual(current, expected, jitter)`.
- Consumes: 2차원 좌표만 사용하며 detector와 GT에 의존하지 않는다.

- [ ] **Step 1: 평행 이동·회전·확대 불변성 실패 테스트를 작성한다.**

```python
import importlib
import unittest

from core.puzzle.models import Candidate

def _candidate(candidate_id: str, bbox: tuple[float, float, float, float]) -> Candidate:
    x1, y1, x2, y2 = bbox
    return Candidate(
        candidate_id=candidate_id,
        frame_index=0,
        bbox=bbox,
        center=((x1 + x2) / 2.0, (y1 + y2) / 2.0),
        score=0.8,
        source="raw",
    )

class RelativeCoordinateGeometryTest(unittest.TestCase):
    def test_similarity_transform_preserves_relative_coordinate(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        expected = module.relative_coordinate((4.0, 3.0), (0.0, 0.0), (10.0, 0.0))

        def transform(point: tuple[float, float]) -> tuple[float, float]:
            x, y = point
            return (100.0 - 2.5 * y, 40.0 + 2.5 * x)

        transformed = module.relative_coordinate(
            transform((4.0, 3.0)),
            transform((0.0, 0.0)),
            transform((10.0, 0.0)),
        )
        self.assertAlmostEqual(transformed.u, expected.u)
        self.assertAlmostEqual(transformed.v, expected.v)

    def test_coincident_anchors_abstain(self) -> None:
        module = importlib.import_module("core.puzzle.merge_split_relative")
        self.assertIsNone(module.relative_coordinate((4.0, 3.0), (1.0, 1.0), (1.0, 1.0)))
```

- [ ] **Step 2: 새 테스트가 모듈 부재로 실패하는지 확인한다.**

Run: `python -m pytest tests/test_merge_split_relative.py -q`

Expected: FAIL with `ModuleNotFoundError: core.puzzle.merge_split_relative`.

- [ ] **Step 3: 최소 기하 자료형과 함수를 구현한다.**

```python
# 병합된 투명도형의 배경 상대 좌표와 분리 신분을 복원합니다.
from __future__ import annotations

from dataclasses import dataclass
from math import hypot

Point = tuple[float, float]

@dataclass(frozen=True)
class RelativeCoordinate:
    u: float
    v: float

def relative_coordinate(point: Point, anchor_a: Point, anchor_b: Point) -> RelativeCoordinate | None:
    dx = anchor_b[0] - anchor_a[0]
    dy = anchor_b[1] - anchor_a[1]
    length = hypot(dx, dy)
    if length <= 1e-6:
        return None
    px = point[0] - anchor_a[0]
    py = point[1] - anchor_a[1]
    return RelativeCoordinate(
        u=(px * dx + py * dy) / (length * length),
        v=(dx * py - dy * px) / (length * length),
    )

def relative_coordinate_residual(
    current: RelativeCoordinate,
    expected: RelativeCoordinate,
    jitter: float,
) -> float:
    return hypot(current.u - expected.u, current.v - expected.v) / max(1e-6, jitter)
```

- [ ] **Step 4: 기하 테스트를 통과시킨다.**

Run: `python -m pytest tests/test_merge_split_relative.py -q`

Expected: PASS.

- [ ] **Step 5: Task 1만 커밋한다.**

```powershell
git add -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
git commit --only -m "투명도형 배경 상대좌표 기하 추가" -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
```

---

### Task 2: Merge State Machine

**Files:**
- Modify: `maple_bot/core/puzzle/merge_split_relative.py`
- Modify: `maple_bot/tests/test_merge_split_relative.py`

**Interfaces:**
- Consumes: `Candidate`, 이전 타겟 위치, 초기 안정 면적.
- Produces: `MergeState`, `MergeEvent`, `MergeSplitEventDetector.update`.

- [ ] **Step 1: 부분 병합·완전 병합·분리·hysteresis 실패 테스트를 추가한다.**

```python
def test_detector_transitions_partial_merged_splitting_without_using_pixels(self) -> None:
    module = importlib.import_module("core.puzzle.merge_split_relative")
    detector = module.MergeSplitEventDetector(confirm_observations=2)
    target = _candidate("target", (40.0, 40.0, 60.0, 60.0))
    background = _candidate("background", (56.0, 40.0, 76.0, 60.0))
    merged = _candidate("merged", (40.0, 40.0, 76.0, 60.0))
    split_target = _candidate("split_target", (34.0, 40.0, 54.0, 60.0))
    split_background = _candidate("split_background", (62.0, 40.0, 82.0, 60.0))

    detector.update(target_candidate=target, candidates=(target, background), stable_area=400.0, predicted_target_point=(50.0, 50.0))
    partial = detector.update(target_candidate=target, candidates=(target, background), stable_area=400.0, predicted_target_point=(50.0, 50.0))
    detector.update(target_candidate=None, candidates=(merged,), stable_area=400.0, predicted_target_point=(52.0, 50.0))
    merged_event = detector.update(target_candidate=None, candidates=(merged,), stable_area=400.0, predicted_target_point=(52.0, 50.0))
    detector.update(target_candidate=split_target, candidates=(split_target, split_background), stable_area=400.0, predicted_target_point=(54.0, 50.0))
    split = detector.update(target_candidate=split_target, candidates=(split_target, split_background), stable_area=400.0, predicted_target_point=(54.0, 50.0))

    self.assertEqual(partial.state, module.MergeState.PARTIAL_OVERLAP)
    self.assertEqual(merged_event.state, module.MergeState.MERGED)
    self.assertEqual(split.state, module.MergeState.SPLITTING)
```

- [ ] **Step 2: 테스트가 정의되지 않은 상태 자료형 때문에 실패하는지 확인한다.**

Run: `python -m pytest tests/test_merge_split_relative.py -q`

Expected: FAIL with missing `MergeSplitEventDetector`.

- [ ] **Step 3: 정규화된 사건 감지기를 구현한다.**

```python
class MergeState(str, Enum):
    SEPARATE = "SEPARATE"
    PARTIAL_OVERLAP = "PARTIAL_OVERLAP"
    MERGED = "MERGED"
    SPLITTING = "SPLITTING"
    REACQUIRED = "REACQUIRED"

@dataclass(frozen=True)
class MergeEvent:
    event_id: int
    state: MergeState
    reason: str
    overlap_ratio: float
    area_ratio: float
    candidate_count: int

class MergeSplitEventDetector:
    def __init__(self, *, confirm_observations: int = 2) -> None:
        self.confirm_observations = max(1, int(confirm_observations))
        self.reset()

    def reset(self) -> None:
        self.state = MergeState.SEPARATE
        self._pending_state = MergeState.SEPARATE
        self._pending_count = 0
        self._event_id = 0

    def update(
        self,
        *,
        target_candidate: Candidate | None,
        candidates: Sequence[Candidate],
        stable_area: float,
        predicted_target_point: Point | None,
    ) -> MergeEvent:
        area_ratio = max((_candidate_area(row) for row in candidates), default=0.0) / max(
            1.0, stable_area
        )
        overlap_ratio = _largest_target_overlap(target_candidate, candidates)
        stable_scale = max(1.0, stable_area ** 0.5)
        merged_matches_lineage = (
            predicted_target_point is not None
            and len(candidates) == 1
            and _point_to_bbox_distance(predicted_target_point, candidates[0].bbox) / stable_scale <= 0.5
        )
        if (
            self.state in {MergeState.MERGED, MergeState.PARTIAL_OVERLAP}
            and len(candidates) >= 2
            and overlap_ratio == 0.0
        ):
            desired = MergeState.SPLITTING
            reason = "children_reappeared"
        elif target_candidate is None and merged_matches_lineage and area_ratio > 1.25:
            desired = MergeState.MERGED
            reason = "single_expanded_observation"
        elif target_candidate is not None and overlap_ratio > 0.0:
            desired = MergeState.PARTIAL_OVERLAP
            reason = "target_lineage_overlap"
        else:
            desired = MergeState.SEPARATE
            reason = "separate_observations"
        if desired is self.state:
            self._pending_state = desired
            self._pending_count = 0
        elif desired is self._pending_state:
            self._pending_count += 1
        else:
            self._pending_state = desired
            self._pending_count = 1
        if self._pending_count >= self.confirm_observations:
            previous_state = self.state
            self.state = desired
            self._pending_count = 0
            if previous_state is MergeState.SEPARATE and self.state in {
                MergeState.PARTIAL_OVERLAP,
                MergeState.MERGED,
            }:
                self._event_id += 1
        return MergeEvent(
            event_id=self._event_id,
            state=self.state,
            reason=reason,
            overlap_ratio=overlap_ratio,
            area_ratio=area_ratio,
            candidate_count=len(candidates),
        )
```

`_candidate_area`는 bbox 너비와 높이의 곱을 반환한다. `_largest_target_overlap`은 타겟 자신을 제외한 후보와의 교집합을 두 박스 중 작은 면적으로 나눈 최댓값을 반환한다. `_point_to_bbox_distance`는 점이 박스 안이면 0, 밖이면 가장 가까운 박스 경계까지의 거리를 반환한다. 병합 진입은 타겟 계보와 겹친 후보, 후보 수 감소, 안정 면적 대비 병합 면적 증가, 이전 타겟 예측 위치와의 근접성을 함께 사용한다. 부분 병합에서 두 박스가 바로 갈라지는 경우와 완전 병합 뒤 여러 자식이 나타나는 경우를 모두 `SPLITTING`으로 보낸다. 상태 후보가 `confirm_observations`회 연속될 때만 전환한다. 모든 면적·거리 판단은 `stable_area`에서 얻은 크기로 정규화한다. `1.25`와 `0.5`는 픽셀값이 아닌 무차원 비율이며 대표판 결과에 맞춰 조정하지 않는다.

- [ ] **Step 4: 상태기계 테스트와 기존 quorum 테스트를 통과시킨다.**

Run: `python -m pytest tests/test_merge_split_relative.py tests/test_persistent_evidence_quorum.py -q`

Expected: PASS.

- [ ] **Step 5: Task 2만 커밋한다.**

```powershell
git add -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
git commit --only -m "투명도형 병합 분리 상태기계 추가" -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
```

---

### Task 3: Background Anchors and Split Assignment

**Files:**
- Modify: `maple_bot/core/puzzle/merge_split_relative.py`
- Modify: `maple_bot/tests/test_merge_split_relative.py`

**Interfaces:**
- Consumes: 현재 후보, `CandidateEvidence`, 타겟 계보 위치, 화면 크기.
- Produces: `BackgroundAnchor`, `RelationFingerprint`, `MergeSplitDecision`, `MergeSplitRelativeResolver.update`.

- [ ] **Step 1: 두 기준점 배경 배정, 한 기준점 보류, 경계 기권 테스트를 작성한다.**

```python
def test_split_assigns_relation_preserving_child_to_background(self) -> None:
    module = importlib.import_module("core.puzzle.merge_split_relative")
    fingerprint = module.RelationFingerprint.from_observations(
        background_point=(5.0, 4.0),
        anchors=(
            module.BackgroundAnchor("a", (0.0, 0.0), 8),
            module.BackgroundAnchor("b", (10.0, 0.0), 8),
        ),
        jitter=0.02,
    )
    decision = module.assign_split_children(
        children=(
            _candidate("background_child", (4.0, 3.0, 6.0, 5.0)),
            _candidate("target_child", (7.0, 7.0, 9.0, 9.0)),
        ),
        anchors=(
            module.BackgroundAnchor("a", (0.0, 0.0), 9),
            module.BackgroundAnchor("b", (10.0, 0.0), 9),
        ),
        fingerprint=fingerprint,
    )
    self.assertEqual(decision.background_candidate_id, "background_child")
    self.assertEqual(decision.target_candidate_id, "target_child")
    self.assertGreater(decision.relative_margin, 0.0)

def test_one_anchor_holds_instead_of_guessing(self) -> None:
    module = importlib.import_module("core.puzzle.merge_split_relative")
    fingerprint = module.RelationFingerprint.from_observations(
        background_point=(5.0, 4.0),
        anchors=(
            module.BackgroundAnchor("a", (0.0, 0.0), 8),
            module.BackgroundAnchor("b", (10.0, 0.0), 8),
        ),
        jitter=0.02,
    )
    decision = module.assign_split_children(
        children=(
            _candidate("child_a", (4.0, 3.0, 6.0, 5.0)),
            _candidate("child_b", (7.0, 7.0, 9.0, 9.0)),
        ),
        anchors=(module.BackgroundAnchor("a", (0.0, 0.0), 9),),
        fingerprint=fingerprint,
        predicted_target_point=(8.0, 8.0),
    )
    self.assertEqual(decision.reason, "insufficient_anchors")
    self.assertIsNone(decision.target_candidate_id)

def test_clipped_anchor_abstains(self) -> None:
    module = importlib.import_module("core.puzzle.merge_split_relative")
    fingerprint = module.RelationFingerprint.from_observations(
        background_point=(5.0, 4.0),
        anchors=(
            module.BackgroundAnchor("a", (0.0, 0.0), 8),
            module.BackgroundAnchor("b", (10.0, 0.0), 8),
        ),
        jitter=0.02,
    )
    decision = module.assign_split_children(
        children=(
            _candidate("child_a", (4.0, 3.0, 6.0, 5.0)),
            _candidate("child_b", (7.0, 7.0, 9.0, 9.0)),
        ),
        anchors=(
            module.BackgroundAnchor("a", (0.0, 0.0), 9, clipped=True),
            module.BackgroundAnchor("b", (10.0, 0.0), 9),
        ),
        fingerprint=fingerprint,
        predicted_target_point=(8.0, 8.0),
    )
    self.assertEqual(decision.reason, "insufficient_anchors")
```

- [ ] **Step 2: 새 테스트가 missing API로 실패하는지 확인한다.**

Run: `python -m pytest tests/test_merge_split_relative.py -q`

Expected: FAIL with missing `RelationFingerprint` or `assign_split_children`.

- [ ] **Step 3: 기준점, fingerprint, 자식 배정 최소 구현을 추가한다.**

```python
@dataclass(frozen=True)
class BackgroundAnchor:
    track_id: str
    point: Point
    stable_observations: int
    clipped: bool = False

@dataclass(frozen=True)
class RelationFingerprint:
    pair_coordinates: tuple[tuple[str, str, RelativeCoordinate], ...]
    jitter: float

    @classmethod
    def from_observations(
        cls,
        *,
        background_point: Point,
        anchors: Sequence[BackgroundAnchor],
        jitter: float,
    ) -> "RelationFingerprint":
        rows: list[tuple[str, str, RelativeCoordinate]] = []
        for left_index, left in enumerate(anchors):
            for right in anchors[left_index + 1:]:
                coordinate = relative_coordinate(background_point, left.point, right.point)
                if coordinate is not None and not left.clipped and not right.clipped:
                    rows.append((left.track_id, right.track_id, coordinate))
        return cls(pair_coordinates=tuple(rows), jitter=max(1e-6, float(jitter)))

@dataclass(frozen=True)
class MergeSplitDecision:
    state: MergeState
    background_candidate_id: str | None
    target_candidate_id: str | None
    target_point: Point | None
    relative_margin: float | None
    reason: str
    debug: dict[str, object]

class BackgroundAnchorManager:
    def __init__(self, *, minimum_stable_observations: int = 3) -> None:
        self.minimum_stable_observations = max(1, int(minimum_stable_observations))
        self.reset()

    def reset(self) -> None:
        self._tracks: dict[str, BackgroundAnchor] = {}

    def update(
        self,
        *,
        candidates: Sequence[Candidate],
        target_candidate: Candidate | None,
        evidence: Mapping[str, CandidateEvidence],
        frame_shape: tuple[int, int] | None,
        stable_scale_px: float,
    ) -> tuple[BackgroundAnchor, ...]:
        eligible = _eligible_background_candidates(
            candidates=candidates,
            target_candidate=target_candidate,
            evidence=evidence,
            frame_shape=frame_shape,
        )
        self._tracks = _associate_anchor_tracks(
            previous=self._tracks,
            candidates=eligible,
            stable_scale_px=max(1.0, stable_scale_px),
        )
        return tuple(
            anchor
            for anchor in self._tracks.values()
            if anchor.stable_observations >= self.minimum_stable_observations
        )

def assign_split_children(
    *,
    children: Sequence[Candidate],
    anchors: Sequence[BackgroundAnchor],
    fingerprint: RelationFingerprint,
    predicted_target_point: Point,
) -> MergeSplitDecision:
    usable = {anchor.track_id: anchor for anchor in anchors if not anchor.clipped}
    child_residuals: list[tuple[float, Candidate]] = []
    for child in children:
        residuals: list[float] = []
        for left_id, right_id, expected in fingerprint.pair_coordinates:
            if left_id not in usable or right_id not in usable:
                continue
            current = relative_coordinate(
                child.center,
                usable[left_id].point,
                usable[right_id].point,
            )
            if current is not None:
                residuals.append(relative_coordinate_residual(current, expected, fingerprint.jitter))
        if residuals:
            child_residuals.append((float(median(residuals)), child))
    if len(child_residuals) < 2:
        return _hold_decision("insufficient_anchors")
    child_residuals.sort(key=lambda row: row[0])
    background_residual, background = child_residuals[0]
    relative_margin = child_residuals[1][0] - background_residual
    if relative_margin <= 1.0:
        return _hold_decision("ambiguous_relation", relative_margin=relative_margin)
    remaining = [row[1] for row in child_residuals[1:]]
    target = min(remaining, key=lambda row: hypot(
        row.center[0] - predicted_target_point[0],
        row.center[1] - predicted_target_point[1],
    ))
    return MergeSplitDecision(
        state=MergeState.SPLITTING,
        background_candidate_id=background.candidate_id,
        target_candidate_id=target.candidate_id,
        target_point=target.center,
        relative_margin=relative_margin,
        reason="background_relation_assigned",
        debug={"child_residuals": tuple(
            (candidate.candidate_id, residual) for residual, candidate in child_residuals
        )},
    )
```

각 자식의 기준점 쌍별 잔차 중앙값을 계산한다. 가장 낮은 잔차 자식을 배경으로 배정하고, 두 최저 잔차의 차이를 `relative_margin`으로 반환한다. 기준점 쌍이 없거나 차이가 현재 jitter 안이면 `reason="ambiguous_relation"`으로 보류한다.

- [ ] **Step 4: 상태를 포함한 resolver를 구현한다.**

```python
class MergeSplitRelativeResolver:
    def __init__(self) -> None:
        self._event_detector = MergeSplitEventDetector()
        self._anchor_manager = BackgroundAnchorManager()
        self.reset()

    def reset(self) -> None:
        self._event_detector.reset()
        self._anchor_manager.reset()
        self._target_points: list[Point] = []
        self._current_anchors: tuple[BackgroundAnchor, ...] = ()
        self._fingerprint = None

    def update(
        self,
        *,
        incumbent_point: Point | None,
        candidates: Sequence[Candidate],
        evidence: Mapping[str, CandidateEvidence],
        stable_area: float,
        frame_shape: tuple[int, int] | None,
    ) -> MergeSplitDecision:
        nearest = _nearest_candidate(candidates, incumbent_point)
        target_candidate = (
            nearest
            if nearest is not None
            and _candidate_area(nearest) / max(1.0, stable_area) <= 1.25
            else None
        )
        event = self._event_detector.update(
            target_candidate=target_candidate,
            candidates=candidates,
            stable_area=stable_area,
            predicted_target_point=(
                self._predicted_target_point()
                if self._target_points
                else incumbent_point
            ),
        )
        if event.state is MergeState.SEPARATE:
            self._update_target_velocity(target_candidate)
            self._update_background_anchors(candidates, evidence, target_candidate, frame_shape)
            self._prepare_fingerprint(target_candidate, candidates)
            return self._hold("separate", event)
        if event.state is MergeState.PARTIAL_OVERLAP:
            self._freeze_fingerprint_if_available(target_candidate, candidates)
            return self._hold("partial_overlap", event)
        if event.state is MergeState.MERGED:
            self._advance_latent_target()
            return self._hold("merged_identity_hold", event)
        if event.state is MergeState.SPLITTING and self._fingerprint is not None:
            return assign_split_children(
                children=candidates,
                anchors=self._current_anchors,
                fingerprint=self._fingerprint,
                predicted_target_point=self._predicted_target_point(),
            )
        return self._hold("missing_fingerprint", event)
```

생성자는 `MergeSplitEventDetector`, `BackgroundAnchorManager`, 최근 타겟 두 점, 선택된 충돌 배경 fingerprint를 초기화한다. `_eligible_background_candidates`는 경계 후보, 타겟 후보, local rigid상 배경으로 설명되지 않는 후보를 제외한다. `_associate_anchor_tracks`는 이전 기준점의 최근 이동으로 예측한 위치와 현재 후보의 거리를 `stable_scale_px`로 나눠 가장 작은 일대일 배정을 선택하며 허용 범위를 넘으면 새 track ID를 만든다. `_prepare_fingerprint`는 병합 전 여러 프레임의 배경 상대 좌표 중앙값과 중앙절대편차를 저장한다. `SEPARATE`에서만 타겟과 배경 기준점을 갱신한다. `MERGED`에서는 마지막 타겟 속도로 잠재 위치를 예측하지만 병합 중심을 저장하지 않는다. `SPLITTING`에서만 `assign_split_children`을 호출한다. detector 후보 ID가 달라져도 내부 track ID와 공간 경로는 유지된다.

- [ ] **Step 5: 전체 새 모듈 테스트를 통과시킨다.**

Run: `python -m pytest tests/test_merge_split_relative.py -q`

Expected: PASS.

- [ ] **Step 6: Task 3만 커밋한다.**

```powershell
git add -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
git commit --only -m "투명도형 분리 자식 배경관계 판별 추가" -- maple_bot/core/puzzle/merge_split_relative.py maple_bot/tests/test_merge_split_relative.py
```

---

### Task 4: Configurable Persistent Quorum

**Files:**
- Modify: `maple_bot/core/puzzle/persistent_evidence_quorum.py:13-128`
- Modify: `maple_bot/tests/test_persistent_evidence_quorum.py`

**Interfaces:**
- Adds: `support_groups: Sequence[str] = SUPPORT_GROUPS` constructor argument.
- Preserves: 현재 기본 support group과 모든 기존 호출 결과.
- Enables: `background_relative_identity`를 필수 주심으로 쓰는 병합 전용 quorum.

- [ ] **Step 1: 사용자 정의 group과 필수 주심 실패 테스트를 작성한다.**

```python
def test_custom_relative_group_can_be_required_without_changing_defaults(self) -> None:
    module = importlib.import_module("core.puzzle.persistent_evidence_quorum")
    quorum = module.PersistentEvidenceQuorum(
        support_groups=("background_relative_identity", "background_motion"),
        required_groups=2,
        required_observations=3,
        required_positive_groups=("background_relative_identity",),
    )
    for index in range(2):
        selected, debug = quorum.update(
            incumbent_point=(0.0, 0.0),
            challenger_point=(10.0 + index, 0.0),
            stable_scale_px=10.0,
            group_margins={
                "background_relative_identity": 0.8,
                "background_motion": 0.2,
            },
        )
        self.assertFalse(debug["selected"])
    selected, debug = quorum.update(
        incumbent_point=(0.0, 0.0),
        challenger_point=(12.0, 0.0),
        stable_scale_px=10.0,
        group_margins={"background_relative_identity": 0.8, "background_motion": 0.2},
    )
    self.assertTrue(debug["selected"])
```

- [ ] **Step 2: 기존 구현이 custom group을 무시해 실패하는지 확인한다.**

Run: `python -m pytest tests/test_persistent_evidence_quorum.py -q`

Expected: FAIL at constructor argument or `support_missing`.

- [ ] **Step 3: 인스턴스별 support group을 최소 변경으로 구현한다.**

```python
def __init__(
    self,
    *,
    required_groups: int = 3,
    required_observations: int = 3,
    max_prediction_error_scales: float = 1.5,
    support_groups: Sequence[str] = SUPPORT_GROUPS,
    required_positive_groups: Sequence[str] = (),
) -> None:
    self.support_groups = tuple(dict.fromkeys(str(group) for group in support_groups))
    self.required_positive_groups = tuple(
        str(group) for group in required_positive_groups if str(group) in self.support_groups
    )
```

`support_missing`, observed margin filtering, `_positive_groups`가 모듈 상수 대신 `self.support_groups`를 사용하게 바꾼다. 기본 인자는 기존 상수이므로 현재 Studio 결과는 변하지 않아야 한다.

- [ ] **Step 4: 새 테스트와 기존 14개 관련 테스트를 통과시킨다.**

Run: `python -m pytest tests/test_persistent_evidence_quorum.py tests/test_studio_hypothesis_shadow.py -q`

Expected: PASS with no existing assertion changes.

- [ ] **Step 5: Task 4만 커밋한다.**

```powershell
git add -- maple_bot/core/puzzle/persistent_evidence_quorum.py maple_bot/tests/test_persistent_evidence_quorum.py
git commit --only -m "투명도형 지속 정족수 심판그룹 확장" -- maple_bot/core/puzzle/persistent_evidence_quorum.py maple_bot/tests/test_persistent_evidence_quorum.py
```

---

### Task 5: Studio Shadow Integration

**Files:**
- Modify: `maple_bot/core/puzzle/studio_hypothesis_shadow.py:93-343`
- Modify: `maple_bot/tests/test_studio_hypothesis_shadow.py:23-325`

**Interfaces:**
- Adds: `merge_split_relative: bool = False` to replay public functions.
- Adds detail key: `merge_split_relative` containing state, reason, anchors, child residuals and quorum result.
- Preserves: option false일 때 기존 replay point, source, counters.

- [ ] **Step 1: 기본 비활성과 opt-in 분리 복원 실패 테스트를 작성한다.**

```python
def test_merge_split_relative_is_opt_in_and_reports_child_assignment(self) -> None:
    baseline = replay_hypothesis_selection_details(score_path, trace_path)
    enabled = replay_hypothesis_selection_details(
        score_path,
        trace_path,
        merge_split_relative=True,
    )
    self.assertNotIn("merge_split_relative", baseline[0] | {})
    self.assertIn("merge_split_relative", enabled[-1])
    self.assertIn(enabled[-1]["merge_split_relative"]["state"], {
        "SEPARATE", "PARTIAL_OVERLAP", "MERGED", "SPLITTING", "REACQUIRED",
    })
```

테스트 fixture에는 타겟과 배경이 부분 겹침, 병합, 두 자식 분리를 거치는 최소 trace를 넣는다. GT는 score에만 존재하고 resolver 입력에는 전달하지 않는다.

- [ ] **Step 2: 새 인자 부재로 실패하는지 확인한다.**

Run: `python -m pytest tests/test_studio_hypothesis_shadow.py -q`

Expected: FAIL with unexpected keyword `merge_split_relative`.

- [ ] **Step 3: opt-in resolver와 병합 전용 quorum을 생성한다.**

```python
merge_resolver = MergeSplitRelativeResolver() if merge_split_relative else None
merge_quorum = (
    PersistentEvidenceQuorum(
        support_groups=(
            "background_relative_identity",
            "background_motion",
            "anchor_shape_identity",
        ),
        required_groups=2,
        required_observations=3,
        required_positive_groups=("background_relative_identity",),
    )
    if merge_split_relative else None
)
```

- [ ] **Step 4: replay loop에서 resolver 도전 경로를 quorum으로 확인한다.**

resolver가 `target_point`를 반환한 경우에만 후보 evidence에서 background motion과 anchor shape 보조 margin을 계산한다. `relative_margin`을 `background_relative_identity`로 전달한다. local rigid는 resolver 내부 배경 배정 확인에만 사용하고 별도 support group으로 세지 않는다.

quorum이 확정하기 전에는 기존 `baseline_replay_point`를 유지한다. 확정 시 source를 `merge_split_relative`로 기록한다.

- [ ] **Step 5: detail 진단값을 추가한다.**

```python
details.append({
    "frame_index": frame_index,
    "recorded_point": recorded_point,
    "replay_point": replay_point,
    "recorded_passed": recorded_passed,
    "replay_passed": replay_passed,
    "merge_split_relative": {
        **merge_decision.debug,
        "state": merge_decision.state.value,
        "reason": merge_decision.reason,
        "background_candidate_id": merge_decision.background_candidate_id,
        "target_candidate_id": merge_decision.target_candidate_id,
        "relative_margin": merge_decision.relative_margin,
        "quorum": dict(merge_quorum_debug),
    },
})
```

- [ ] **Step 6: 통합 테스트와 기존 관련 테스트를 통과시킨다.**

Run: `python -m pytest tests/test_merge_split_relative.py tests/test_persistent_evidence_quorum.py tests/test_studio_hypothesis_shadow.py -q`

Expected: PASS.

- [ ] **Step 7: Task 5만 커밋한다.**

```powershell
git add -- maple_bot/core/puzzle/studio_hypothesis_shadow.py maple_bot/tests/test_studio_hypothesis_shadow.py
git commit --only -m "Studio 병합 분리 상대좌표 shadow 연결" -- maple_bot/core/puzzle/studio_hypothesis_shadow.py maple_bot/tests/test_studio_hypothesis_shadow.py
```

---

### Task 6: Representative Replay and Expansion Gates

**Files:**
- Modify: `03_output/2026-07-24_merge_split_relative_coordinate_checklist_v1.md`
- Modify: `03_output/2026-07-24_merge_split_relative_coordinate_context-notes_v1.md`

**Interfaces:**
- Consumes: 기존 Studio score·trace와 opt-in replay detail.
- Produces: 사건 단위 baseline/new 비교, 채택 또는 폐기 결정.

- [ ] **Step 1: 대표 실패판 하나만 baseline과 new로 replay한다.**

Run: 프로젝트 Python으로 `replay_hypothesis_selection_details`를 동일한 width 24, branch 5, diverse top 12, challenge 3, max step 60 설정에서 각각 `merge_split_relative=False/True`로 실행한다.

Expected: 분리 사건마다 `state`, 기준점 수, 배경 자식, 타겟 도전 자식, 상대 잔차, quorum 판정을 출력한다.

- [ ] **Step 2: 사전 채택 조건을 적용한다.**

채택 조건은 대표 실패판의 분리 후 적중 증가, 기존 정답 회귀 0, 정답 후보의 후보군 포함, 상대 좌표 근거 설명 가능이다. 하나라도 실패하면 추가 seed를 실행하지 않고 책임 모듈을 기록한다.

- [ ] **Step 3: 통과한 경우에만 성공 보존판과 혼합 3판으로 확대한다.**

Expected: 각 단계 A/B 회귀 0. 실패 시 다음 단계 중단.

- [ ] **Step 4: 통과한 경우에만 정식 seed 10판을 실행한다.**

Expected: 현재 기준 1135/1500보다 개선되고 A/B 회귀 0.

- [ ] **Step 5: 두 16GT 회귀를 실행한다.**

Run: `python -m pytest tests/test_gt_free_family_selector.py tests/test_transparent_family_selector_runtime.py -q`

Expected: GT 비참조 selector 16/16, 런타임 selector 16/16.

- [ ] **Step 6: 새 무작위 Studio 검증은 1판부터 확대한다.**

새 1판이 기존 선택을 망가뜨리지 않을 때만 3판, 다시 통과할 때만 10판으로 확대한다. 저장 영상은 실패 대표 자료만 보존하고 성공 중간 자료는 보고서 수치만 남긴다.

- [ ] **Step 7: 체크리스트와 맥락 기록을 갱신한다.**

변경한 규칙, 개선·회귀 수, 실패 책임, 다음 관문을 기록한다. 좌표나 특정 프레임 정답을 런타임 규칙으로 옮기지 않는다.

- [ ] **Step 8: 검증 문서만 커밋한다.**

```powershell
git add -- 03_output/2026-07-24_merge_split_relative_coordinate_checklist_v1.md 03_output/2026-07-24_merge_split_relative_coordinate_context-notes_v1.md
git commit --only -m "투명도형 병합 분리 shadow 검증 기록" -- 03_output/2026-07-24_merge_split_relative_coordinate_checklist_v1.md 03_output/2026-07-24_merge_split_relative_coordinate_context-notes_v1.md
```

## Completion Boundary

이 계획의 완료 조건은 새 resolver가 Studio shadow에서 사건 단위 개선과 회귀 0을 달성하고 두 16GT 기준을 유지하는 것이다. 새 무작위 판 관문을 통과하기 전에는 `puzzle.py`, `planet_live.py`, 마우스 제어를 수정하지 않는다.
