# Studio 100판 공통 가중치 보정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Studio 100판의 겹침 분리 사건에서 판별 가능한 공통 배경 심판 세팅을 교차검증으로 찾고, 값을 잠근 뒤 새 100판을 GT 없이 추적한다.

**Architecture:** 기존 Studio lockstep 하네스와 `binary_merge_shadow` 사건 계보를 유지한다. 후보마다 배경 일치도만 양의 점수로 계산하고 타겟 움직임은 불가능한 점프 제거에만 사용한다. GT는 solver trace가 완성된 뒤 사건 라벨과 보고서 생성에만 사용하며, 90판 보정과 10판 대조를 10번 반복해 평균형, 효율형, 고확률형 세팅을 비교한다.

**Tech Stack:** Python 3.14, 표준 라이브러리 `dataclasses`, `json`, `hashlib`, `itertools`, 기존 OpenCV/NCNN 후보 검출, `openpyxl`, `unittest`/`pytest`, Lie Captcha Studio JavaScript harness.

## Global Constraints

- 고정 목표는 처음 흰색 타겟의 신분을 잃지 않고 끝까지 따라가는 시간축 판별기다.
- 1차 지표는 겹침 후 분리 사건의 타겟 역할 복원 정확도다.
- 타겟 움직임은 물리적으로 불가능한 후보 제거에만 사용한다.
- 특정 좌표, 방향, 프레임 번호, 사건 번호를 규칙에 사용하지 않는다.
- 각 판의 개별 최적값은 런타임에서 사용하지 않는다.
- `SAFE_HOLD`는 오답 전환과 별도로 집계하지만 전체 판 통과에서는 실패다.
- 측정할 수 없는 심판은 0점이 아니라 `None`으로 유지하고 가용 심판끼리 가중치를 다시 정규화한다.
- 실행 중 solver 인터페이스에 GT 행, 정답 좌표, seed를 전달하지 않는다.
- 영상은 기본적으로 저장하지 않고 대표 실패 이미지 최대 4장만 남긴다.
- 수동 파일 수정은 `apply_patch`로 수행하고 관련 테스트를 통과한 논리 단위마다 커밋한다.

---

## 파일 구조

- Create `maple_bot/core/puzzle/background_role.py`.
  배경 심판 벡터, 포화 변환, 결측치 재정규화, 물리 점프 gate, 비대칭 역할 결정을 담당한다.
- Modify `maple_bot/core/puzzle/binary_merge_shadow.py`.
  기존 사건 계보의 두 분리 후보에서 `BackgroundJudgeVector`를 만들고 사건 replay에 심판 원시값을 남긴다.
- Modify `maple_bot/core/puzzle/binary_merge_identity.py`.
  대칭적인 타겟 속도 예측을 제거하고 `background_role` 결정 결과를 기존 `BinaryTransferDecision`으로 변환한다.
- Create `maple_bot/core/puzzle/studio_event_dataset.py`.
  완성된 trace와 별도 GT 파일을 사후 결합해 사건 라벨, 단계별 상한, 판별 행을 생성한다.
- Create `maple_bot/core/puzzle/studio_weight_calibration.py`.
  개별판 성공 영역, 세 공통 프로필, 10겹 교차검증, 프로필 잠금을 담당한다.
- Create `maple_bot/core/puzzle/studio_weight_report.py`.
  사건, 상한, fold, 프로필 비교 결과를 Markdown과 XLSX로 기록한다.
- Modify `maple_bot/core/puzzle/studio_harness.py`.
  보정 실행과 잠금 검증 실행의 결과 경계를 명시하고 solver에 GT를 전달하지 않았음을 기록한다.
- Modify `maple_bot/puzzle.py`.
  보정, 교차검증, 잠금 검증 CLI를 연결한다.
- Modify `maple_bot/tests/test_binary_merge_identity.py`.
  배경 제거 기반 역할 결정 회귀 테스트를 추가한다.
- Create `maple_bot/tests/test_background_role.py`.
  포화, 결측치, 물리 gate, HOLD 규칙을 검증한다.
- Create `maple_bot/tests/test_studio_event_dataset.py`.
  GT 사후 결합과 실패 단계 분리를 검증한다.
- Create `maple_bot/tests/test_studio_weight_calibration.py`.
  개별 성공 영역, 세 프로필, 10겹 분리, 잠금 해시를 검증한다.
- Modify `maple_bot/tests/test_studio_harness.py` and `maple_bot/tests/test_puzzle_target_visual_check.py`.
  GT 비노출과 CLI 연결을 검증한다.
- Generate `maple_bot/assets/puzzle/background_role_profile_v1.json`.
  실제 100판 보정이 성공한 뒤 선택된 공통 프로필을 저장한다.

---

### Task 1: 배경 심판 점수 계약

**Files:**
- Create: `maple_bot/core/puzzle/background_role.py`
- Create: `maple_bot/tests/test_background_role.py`

**Interfaces:**
- Produces: `BackgroundJudgeVector`, `BackgroundRoleProfile`, `BackgroundRoleDecision`, `residual_to_similarity()`, `decide_background_role()`.
- Consumes: 두 후보의 배경 심판 원시값과 타겟 중심 기준 물리 이동 비율.

- [ ] **Step 1: 실패 테스트 작성**

```python
# 타겟/배경 분리 역할 판별의 배경 점수 규칙을 검증합니다.
def test_missing_judge_is_renormalized_instead_of_zero():
    profile = BackgroundRoleProfile(
        weights={"flow": 0.5, "neighbor": 0.5},
        saturation={"flow": 1.0, "neighbor": 1.0},
        resolve_margin=0.2,
        physical_jump_limit=3.0,
        yolo_floor=0.4,
        yolo_uncertainty_weight=0.1,
    )
    background = BackgroundJudgeVector("bg", {"flow": 0.9, "neighbor": None}, 1.0, 0.8)
    target = BackgroundJudgeVector("target", {"flow": 0.2, "neighbor": None}, 1.0, 0.8)
    decision = decide_background_role(background, target, profile)
    assert decision.target_candidate_id == "target"
    assert decision.available_weight == 0.5
```

추가 테스트는 다음 네 가지를 포함한다.

- 잔차형 심판이 포화 기준 이상에서 같은 만점으로 변환된다.
- 두 후보 모두 배경 점수가 높거나 점수 차가 작으면 HOLD한다.
- 한 후보의 `target_jump_ratio`가 제한을 넘으면 해당 후보만 타겟 역할에서 제외한다.
- YOLO가 기준 이상이면 추가 보너스가 없고 기준 아래에서만 감점한다.

- [ ] **Step 2: 실패 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_background_role.py -q`

Expected: `ModuleNotFoundError: core.puzzle.background_role`.

- [ ] **Step 3: 최소 구현 작성**

```python
# 겹침 분리 후보가 배경으로 설명되는 정도를 비교합니다.
@dataclass(frozen=True)
class BackgroundJudgeVector:
    candidate_id: str
    values: Mapping[str, float | None]
    target_jump_ratio: float
    detection_quality: float | None

@dataclass(frozen=True)
class BackgroundRoleProfile:
    weights: Mapping[str, float]
    saturation: Mapping[str, float]
    resolve_margin: float
    physical_jump_limit: float
    yolo_floor: float
    yolo_uncertainty_weight: float

@dataclass(frozen=True)
class BackgroundRoleDecision:
    target_candidate_id: str | None
    background_candidate_id: str | None
    status: str
    margin: float
    available_weight: float
    reason: str
    judge_contributions: Mapping[str, float]

def decide_background_role(
    child_a: BackgroundJudgeVector,
    child_b: BackgroundJudgeVector,
    profile: BackgroundRoleProfile,
) -> BackgroundRoleDecision:
    score_a, weight_a, contributions_a = _background_score(child_a, profile)
    score_b, weight_b, contributions_b = _background_score(child_b, profile)
    available_weight = min(weight_a, weight_b)
    if available_weight <= 0.0:
        return _hold("hold_no_background_evidence", available_weight)
    if child_a.target_jump_ratio > profile.physical_jump_limit:
        return _resolve(target=child_b, background=child_a, reason="physical_gate_a")
    if child_b.target_jump_ratio > profile.physical_jump_limit:
        return _resolve(target=child_a, background=child_b, reason="physical_gate_b")
    margin = abs(score_a - score_b)
    quality_shortfall = max(
        _quality_shortfall(child_a.detection_quality, profile.yolo_floor),
        _quality_shortfall(child_b.detection_quality, profile.yolo_floor),
    )
    required_margin = profile.resolve_margin + quality_shortfall * profile.yolo_uncertainty_weight
    if margin <= required_margin:
        return _hold("hold_ambiguous_background", available_weight, margin)
    background, target = (child_a, child_b) if score_a > score_b else (child_b, child_a)
    return _resolve(target=target, background=background, reason="background_elimination")
```

`values`는 모두 0에서 1 사이의 배경 일치도다. `None`은 제외하고 가용 가중치 합으로 나눈다. 두 후보의 점수 차가 품질 보정된 required margin 이하이면 `hold_ambiguous_background`를 반환한다. 타겟 역할 후보가 `physical_jump_limit`을 넘으면 `hold_physical_gate` 또는 반대 후보 선택을 반환한다. YOLO 품질은 배경 점수에 더하지 않고 required margin만 높인다.

`residual_to_similarity(residual, saturation)`은 값이 없거나 유한하지 않으면 `None`, 잔차가 0이면 1, 잔차가 saturation 이상이면 0, 그 사이는 `1 - residual / saturation`을 반환한다. `_background_score()`는 각 가용 심판의 `value * weight`를 합산하고 가용 가중치 합으로 나눈다. `_hold()`와 `_resolve()`는 위 `BackgroundRoleDecision`의 모든 필드를 채우는 private helper로 구현한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_background_role.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```powershell
git add -- maple_bot/core/puzzle/background_role.py maple_bot/tests/test_background_role.py
git commit -m "배경 역할 심판 점수 계약 추가"
```

### Task 2: 기존 병합 사건에 비대칭 역할 복원 연결

**Files:**
- Modify: `maple_bot/core/puzzle/binary_merge_shadow.py:514-575`
- Modify: `maple_bot/core/puzzle/binary_merge_identity.py:14-214`
- Modify: `maple_bot/tests/test_binary_merge_identity.py`
- Modify: `maple_bot/tests/test_binary_merge_shadow.py`

**Interfaces:**
- Consumes: Task 1의 `BackgroundJudgeVector`와 `decide_background_role()`.
- Produces: 기존 `BinaryTransferDecision`과 사건별 `background_judges` diagnostics.

- [ ] **Step 1: 비대칭 동작 실패 테스트 작성**

```python
def test_background_evidence_resolves_target_without_target_velocity_support():
    left = vector("left", flow=0.95, neighbor=0.9, rigid=0.9)
    right = vector("right", flow=0.2, neighbor=0.1, rigid=0.15)
    decision = resolver.evaluate_background_roles(event_id=7, child_a=left, child_b=right)
    assert decision.target_candidate_id == "right"
    assert decision.background_candidate_id == "left"
```

회귀 테스트는 타겟 속도 예측이 반대 방향이어도 배경 증거가 충분하면 올바른 타겟을 선택하고, 배경 증거가 모호하면 기존 identity를 갱신하지 않는지 확인한다.

- [ ] **Step 2: 실패 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_binary_merge_identity.py tests\test_binary_merge_shadow.py -q`

Expected: 새 메서드 또는 diagnostics 부재로 FAIL.

- [ ] **Step 3: 후보별 심판 벡터 구성**

`build_child_evidence()`의 대칭 `predicted_target` 비용을 역할 선택에서 제거한다. 다음 값으로 `BackgroundJudgeVector`를 만든다.

```python
values = {
    "flow": residual_to_similarity(background_motion_residual, flow_limit),
    "lineage": residual_to_similarity(background_shape_residual, shape_limit),
    "neighbor": residual_to_similarity(neighbor_relation_residual, neighbor_limit),
    "rigid": residual_to_similarity(candidate_evidence.local_rigid_residual, rigid_limit),
    "phase": clamp_optional(candidate_evidence.phase_similarity),
    "texture": clamp_optional(candidate_evidence.texture_bg_score),
}
```

`target_jump_ratio`는 겹침 전 마지막 타겟 중심에서 후보까지의 거리를 최근 도형 대각선과 최근 프레임 간격으로 정규화한다. 이 값은 배경 점수에 더하지 않는다.

`clamp_optional()`은 trace에서 해당 심판이 실제로 계산되지 않았으면 `None`, 계산됐으면 0에서 1로 제한한 값을 반환한다. 기존 `CandidateEvidence` 기본값 0만으로 가용성을 추정하지 않고 trace의 `notes` 또는 명시적 가용 필드를 함께 확인한다. `detection_quality`에는 child의 YOLO 점수를 넣고, floor 이상이면 추가 영향이 없으며 floor 아래 shortfall만 판별 required margin을 높인다.

- [ ] **Step 4: 기존 결정 형식으로 변환**

`BinaryMergeIdentityResolver.evaluate_background_roles()`를 추가하고 `BackgroundRoleDecision`을 `BinaryTransferDecision`으로 변환한다. 기존 `evaluate()`는 회귀 테스트를 위해 유지하되 shadow 실행은 새 메서드만 호출한다.

- [ ] **Step 5: 테스트 통과 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_background_role.py tests\test_binary_merge_identity.py tests\test_binary_merge_shadow.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 6: 커밋**

```powershell
git add -- maple_bot/core/puzzle/binary_merge_identity.py maple_bot/core/puzzle/binary_merge_shadow.py maple_bot/tests/test_binary_merge_identity.py maple_bot/tests/test_binary_merge_shadow.py
git commit -m "병합 분리 신분을 배경 제거 방식으로 복원"
```

### Task 3: 사건 단위 GT 사후 데이터셋

**Files:**
- Create: `maple_bot/core/puzzle/studio_event_dataset.py`
- Create: `maple_bot/tests/test_studio_event_dataset.py`

**Interfaces:**
- Consumes: `studio_gt.jsonl`, solver `trace.jsonl`, `extract_binary_merge_events()`.
- Produces: `StudioEventDataset`, `StudioEventRow`, `StageCoverage`.

- [ ] **Step 1: GT 격리와 단계 분리 실패 테스트 작성**

```python
def test_dataset_labels_only_after_trace_events_exist(tmp_path):
    trace = write_trace_with_one_binary_event(tmp_path)
    gt = write_gt_for_target_child(tmp_path, target_id="right")
    dataset = build_studio_event_dataset(gt, trace)
    assert dataset.events[0].true_target_candidate_id == "right"
    assert dataset.coverage.scoreable_events == 1

def test_missing_target_candidate_is_not_selector_failure(tmp_path):
    dataset = build_dataset_without_gt_candidate(tmp_path)
    assert dataset.coverage.target_candidate_missing == 1
    assert dataset.coverage.selector_eligible_events == 0
```

- [ ] **Step 2: 실패 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_studio_event_dataset.py -q`

Expected: 모듈 부재로 FAIL.

- [ ] **Step 3: 데이터 계약 구현**

```python
# Studio trace와 사후 GT를 겹침 사건 단위 학습 행으로 결합합니다.
@dataclass(frozen=True)
class StudioEventRow:
    run_id: str
    event_id: int
    split_frame: int
    child_a: BackgroundJudgeVector
    child_b: BackgroundJudgeVector
    true_target_candidate_id: str
    true_background_candidate_id: str

@dataclass(frozen=True)
class StageCoverage:
    expected_overlap_events: int
    detected_events: int
    paired_events: int
    target_candidate_present: int
    selector_eligible_events: int
    target_candidate_missing: int

@dataclass(frozen=True)
class StudioEventDataset:
    events: tuple[StudioEventRow, ...]
    coverage: StageCoverage
    excluded_reasons: Mapping[str, int]

def build_studio_event_dataset(gt_jsonl: Path, trace_jsonl: Path) -> StudioEventDataset:
    gt_rows = _read_jsonl(gt_jsonl)
    trace_rows = _read_jsonl(trace_jsonl)
    extraction = extract_binary_merge_events(trace_rows)
    expected = _expected_overlap_events(gt_rows)
    labeled, excluded = _label_extracted_events(extraction.events, gt_rows)
    coverage = _stage_coverage(expected, extraction, labeled, excluded)
    return StudioEventDataset(tuple(labeled), coverage, dict(Counter(excluded)))
```

GT 타겟 점이 후보 박스에 포함되면 해당 후보를 정답으로 라벨링한다. 둘 다 포함하거나 둘 다 포함하지 않으면 거리 tie-break를 사용하지 않고 `ambiguous_gt_mapping`으로 제외한다. solver 결정 데이터에는 GT 필드를 복사하지 않는다.

같은 파일에 `_read_jsonl()`, `_expected_overlap_events()`, `_label_extracted_events()`, `_stage_coverage()`를 구현한다. `_expected_overlap_events()`는 연속된 `target_decoy_overlap=True` 구간의 시작을 사건 하나로 센다. `_label_extracted_events()`는 `run_id`와 split frame을 먼저 맞춘 뒤 두 child bbox 포함 여부로만 라벨링한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_studio_event_dataset.py tests\test_studio_validation.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```powershell
git add -- maple_bot/core/puzzle/studio_event_dataset.py maple_bot/tests/test_studio_event_dataset.py
git commit -m "Studio 겹침 사건 사후 GT 데이터셋 추가"
```

### Task 4: 개별판 성공 영역과 세 공통 프로필

**Files:**
- Create: `maple_bot/core/puzzle/studio_weight_calibration.py`
- Create: `maple_bot/tests/test_studio_weight_calibration.py`

**Interfaces:**
- Consumes: `tuple[StudioEventRow, ...]`.
- Produces: `BoardFeasibleRegion`, `CalibrationProfileSet`, `evaluate_setting()`.

- [ ] **Step 1: 세 프로필 선택 실패 테스트 작성**

```python
def test_profiles_are_derived_from_common_success_regions():
    rows = synthetic_three_board_events()
    result = calibrate_profiles(rows, coarse_units=10, refine_step=0.025)
    assert result.average.name == "average"
    assert result.efficient.active_judges <= result.average.active_judges
    assert result.high_probability.wrong_switches == 0
```

추가 테스트는 가중치 합이 정확히 1인지, 음수 가중치가 없는지, 개별판 최적값이 최종 runtime profile로 직접 복사되지 않는지 확인한다.

- [ ] **Step 2: 실패 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_studio_weight_calibration.py -q`

Expected: 모듈 부재로 FAIL.

- [ ] **Step 3: 결정론적 simplex 탐색 구현**

```python
# 여러 Studio 판에 공통으로 적용되는 배경 심판 가중치를 탐색합니다.
@dataclass(frozen=True)
class WeightSetting:
    name: str
    weights: Mapping[str, float]
    saturation: Mapping[str, float]
    resolve_margin: float
    physical_jump_limit: float
    yolo_floor: float
    yolo_uncertainty_weight: float

@dataclass(frozen=True)
class SettingScore:
    correct_transfer: int
    wrong_switches: int
    safe_holds: int
    minimum_margin: float
    active_judges: int

@dataclass(frozen=True)
class BoardFeasibleRegion:
    run_id: str
    successful_settings: tuple[WeightSetting, ...]

@dataclass(frozen=True)
class CalibrationProfileSet:
    average: WeightSetting
    efficient: WeightSetting
    high_probability: WeightSetting

def iter_simplex_weights(judge_names: tuple[str, ...], units: int) -> Iterator[dict[str, float]]:
    """Yield non-negative weights whose integer units sum exactly to units."""

def evaluate_setting(rows: Sequence[StudioEventRow], setting: WeightSetting) -> SettingScore:
    """Count correct transfers, wrong switches, holds, and minimum margin."""
```

심판 포화 기준은 90판 학습 구간의 같은 심판 원시값 분포에서 배경 정답 후보의 80% 분위수를 사용하고 fold마다 다시 계산한다. 1차 탐색은 0.1 단위 simplex와 `resolve_margin=(0.05, 0.10, 0.15, 0.20)`을 전부 평가한다. 상위 32개 주변만 가중치 0.025와 margin 0.025 단위로 재탐색한다. 물리 gate는 도형 크기와 시간으로 이미 정규화된 값 `3.0`으로 고정하고, YOLO floor는 학습 fold 후보 점수의 하위 10% 분위수로 정한다. 동률 우선순위는 `correct_transfer` 내림차순, `wrong_switch` 오름차순, `safe_hold` 오름차순, `minimum_margin` 내림차순이다.

- [ ] **Step 4: 프로필 선택 규칙 구현**

- 평균형은 성공 설정들의 가중치 중앙값에 가장 가까운 실제 성공 설정을 선택한다.
- 효율형은 정확도와 오답 전환이 최고값과 같은 설정 중 활성 심판 수가 가장 적고 실행 비용이 낮은 설정을 선택한다.
- 고확률형은 판별 성공 판 수를 최대화한 뒤 최악 사건의 margin이 가장 큰 설정을 선택한다.

- [ ] **Step 5: 테스트 통과 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_studio_weight_calibration.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 6: 커밋**

```powershell
git add -- maple_bot/core/puzzle/studio_weight_calibration.py maple_bot/tests/test_studio_weight_calibration.py
git commit -m "Studio 공통 심판 프로필 탐색 추가"
```

### Task 5: 10겹 교차검증과 선택 규칙

**Files:**
- Modify: `maple_bot/core/puzzle/studio_weight_calibration.py`
- Modify: `maple_bot/tests/test_studio_weight_calibration.py`

**Interfaces:**
- Produces: `FoldResult`, `CrossValidationResult`, `cross_validate_profiles(rows, folds=10)`.

- [ ] **Step 1: 누수 방지 실패 테스트 작성**

```python
def test_each_board_is_held_out_once_and_never_used_in_its_fold_training():
    result = cross_validate_profiles(one_event_per_board(100), folds=10)
    assert sorted(result.held_out_run_ids) == sorted(f"run-{i}" for i in range(100))
    for fold in result.folds:
        assert set(fold.train_run_ids).isdisjoint(fold.test_run_ids)
        assert len(fold.test_run_ids) == 10
```

- [ ] **Step 2: 실패 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_studio_weight_calibration.py -k cross -q`

Expected: 교차검증 API 부재로 FAIL.

- [ ] **Step 3: seed 독립 fold 구현**

run ID를 SHA-256으로 정렬한 뒤 10개 fold에 round-robin 배치한다. Python의 프로세스별 hash 값이나 입력 순서에 의존하지 않는다. 매 fold에서 90판으로 세 프로필을 새로 만들고 숨긴 10판만 평가한다.

```python
@dataclass(frozen=True)
class FoldResult:
    fold_index: int
    train_run_ids: tuple[str, ...]
    test_run_ids: tuple[str, ...]
    profile_scores: Mapping[str, SettingScore]

@dataclass(frozen=True)
class CrossValidationResult:
    folds: tuple[FoldResult, ...]
    selected_profile_name: str
    final_profile: WeightSetting

    @property
    def held_out_run_ids(self) -> tuple[str, ...]:
        return tuple(run_id for fold in self.folds for run_id in fold.test_run_ids)
```

- [ ] **Step 4: 최종 프로필 선택 구현**

세 프로필의 fold 합산 결과를 1차 지표 순서대로 비교한다. 겹침 복원 성공 수가 같으면 잘못된 전환, HOLD, 최소 margin, 계산 비용 순으로 결정한다. 선택된 종류를 전체 100판으로 다시 보정해 최종 잠금 후보를 만든다.

- [ ] **Step 5: 테스트 통과 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_studio_weight_calibration.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 6: 커밋**

```powershell
git add -- maple_bot/core/puzzle/studio_weight_calibration.py maple_bot/tests/test_studio_weight_calibration.py
git commit -m "Studio 100판 10겹 교차검증 추가"
```

### Task 6: 프로필 잠금과 GT 비노출 경계

**Files:**
- Modify: `maple_bot/core/puzzle/studio_weight_calibration.py`
- Modify: `maple_bot/core/puzzle/studio_harness.py`
- Modify: `maple_bot/tests/test_studio_harness.py`
- Modify: `maple_bot/tests/test_studio_weight_calibration.py`

**Interfaces:**
- Produces: `write_locked_profile()`, `load_locked_profile()`, `LockedProfile`.
- Guarantees: solver runtime에는 frame만 전달되고 GT payload는 scorer가 실행될 때까지 전달되지 않는다.

- [ ] **Step 1: 잠금 해시와 GT 비노출 실패 테스트 작성**

```python
def test_locked_profile_rejects_modified_payload(tmp_path):
    path = write_locked_profile(
        tmp_path / "profile.json",
        sample_profile(),
        calibration_digest="training-digest",
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["weights"]["flow"] = 0.99
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="profile hash mismatch"):
        load_locked_profile(path)

def test_runtime_factory_never_receives_gt_payload():
    assert set(runtime_factory_calls[0]) == {
        "output_root", "capture_window_title", "frame_grabber", "fps",
        "mouse_enabled", "visual_check_mode", "record_video"
    }
```

- [ ] **Step 2: 실패 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_studio_harness.py tests\test_studio_weight_calibration.py -q`

Expected: 잠금 API 부재로 FAIL.

- [ ] **Step 3: canonical JSON과 해시 구현**

설정 payload는 `schema_version`, `profile_name`, `weights`, `saturation`, `resolve_margin`, `physical_jump_limit`, `yolo_floor`, `yolo_uncertainty_weight`, `calibration_digest`를 가진다. 위 payload를 key 정렬, UTF-8, 공백 없는 JSON으로 직렬화해 SHA-256을 계산하고 바깥 envelope의 `profile_sha256`에 저장한다.

```python
@dataclass(frozen=True)
class LockedProfile:
    setting: WeightSetting
    calibration_digest: str
    profile_sha256: str

def write_locked_profile(path: Path, setting: WeightSetting, calibration_digest: str) -> Path:
    payload = _profile_payload(setting, calibration_digest)
    digest = sha256(_canonical_json(payload)).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"profile_sha256": digest, "payload": payload}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

def load_locked_profile(path: Path) -> LockedProfile:
    envelope = json.loads(path.read_text(encoding="utf-8"))
    actual = sha256(_canonical_json(envelope["payload"])).hexdigest()
    if actual != envelope["profile_sha256"]:
        raise ValueError("profile hash mismatch")
    return _locked_profile_from_payload(envelope["payload"], actual)
```

- [ ] **Step 4: GT 경계 테스트 고정**

기존 lockstep에서 harness가 run boundary를 확인하기 위해 GT payload를 보유하는 것은 허용한다. 단 `runtime_factory`, `runtime.start`, `runtime.pump_once`, `BackgroundRoleProfile`에는 GT 객체나 target 좌표를 전달하지 않는다. scoring은 runtime 종료 뒤 `build_studio_event_dataset()`에서만 시작한다.

- [ ] **Step 5: 테스트 통과 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_studio_harness.py tests\test_studio_weight_calibration.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 6: 커밋**

```powershell
git add -- maple_bot/core/puzzle/studio_harness.py maple_bot/core/puzzle/studio_weight_calibration.py maple_bot/tests/test_studio_harness.py maple_bot/tests/test_studio_weight_calibration.py
git commit -m "Studio 잠금 프로필과 GT 비노출 경계 추가"
```

### Task 7: Markdown·Excel 판별 보고서

**Files:**
- Create: `maple_bot/core/puzzle/studio_weight_report.py`
- Create: `maple_bot/tests/test_studio_weight_report.py`

**Interfaces:**
- Consumes: `StudioEventDataset`, `CrossValidationResult`, `LockedProfile`.
- Produces: `calibration_report.md`, `calibration_report.xlsx`.

- [ ] **Step 1: 보고서 실패 테스트 작성**

```python
def test_report_has_event_and_fold_sheets(tmp_path):
    result = write_calibration_report(tmp_path, sample_bundle())
    workbook = load_workbook(result.xlsx_path, read_only=True)
    assert workbook.sheetnames == ["요약", "단계별상한", "겹침사건", "교차검증", "프로필비교"]
```

- [ ] **Step 2: 실패 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_studio_weight_report.py -q`

Expected: 모듈 부재로 FAIL.

- [ ] **Step 3: 보고서 구현**

요약에는 겹침 복원 성공률, 잘못된 전환, HOLD, 전체 판 통과율, 선택 프로필, 해시를 기록한다. 단계별상한에는 사건 감지, pair, 정답 후보 포함, selector eligible 수를 기록한다. 겹침사건에는 후보별 심판 원시값과 기여율을 기록한다. 성공 영상은 생성하지 않고 기존 validation 이미지 정책대로 대표 실패 최대 4장만 연결한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_studio_weight_report.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```powershell
git add -- maple_bot/core/puzzle/studio_weight_report.py maple_bot/tests/test_studio_weight_report.py
git commit -m "Studio 공통 가중치 검증 보고서 추가"
```

### Task 8: puzzle.py 보정·잠금 검증 CLI 연결

**Files:**
- Modify: `maple_bot/puzzle.py:39-79, 290-337`
- Modify: `maple_bot/tests/test_puzzle_target_visual_check.py`

**Interfaces:**
- Produces CLI:
  `--studio-calibrate-background-role`, `--studio-validate-locked-profile`, `--studio-profile`.
- Reuses: `--studio-runs`, `--studio-run-frames`, `--studio-seed`, `--studio-root`, `--output-root`.

- [ ] **Step 1: CLI 실패 테스트 작성**

```python
def test_calibration_cli_runs_harness_then_posthoc_calibration():
    exit_code = puzzle.run_gui([
        "--studio-calibrate-background-role",
        "--studio-runs", "1",
        "--studio-seed", "calibration-smoke-v1",
        "--output-root", str(output_root),
    ])
    assert exit_code == 0
    assert calls == ["harness", "event_dataset", "cross_validation", "report"]
```

잠금 검증 테스트는 `cross_validation`과 profile write가 호출되지 않고 지정된 profile read와 사후 score만 호출되는지 확인한다.

- [ ] **Step 2: 실패 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_puzzle_target_visual_check.py -k "calibrat or locked" -q`

Expected: 새 argument 부재로 FAIL.

- [ ] **Step 3: CLI 순서 구현**

보정 모드는 `run_studio_harness → build_studio_event_dataset → cross_validate_profiles → write_locked_profile → write_calibration_report` 순서로 실행한다. 잠금 모드는 시작 전에 profile 해시를 검증하고 `run_studio_harness → build_studio_event_dataset → evaluate_setting(dataset.events, locked.setting) → write_calibration_report`만 실행한다.

- [ ] **Step 4: 테스트 통과 확인**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_puzzle_target_visual_check.py tests\test_studio_harness.py tests\test_studio_event_dataset.py tests\test_studio_weight_calibration.py tests\test_studio_weight_report.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 5: 커밋**

```powershell
git add -- maple_bot/puzzle.py maple_bot/tests/test_puzzle_target_visual_check.py
git commit -m "puzzle.py에 Studio 공통 가중치 검증 연결"
```

### Task 9: 단계적 실제 검증과 최종 프로필 생성

**Files:**
- Generate: `maple_bot/assets/puzzle/background_role_profile_v1.json`
- Update: `03_output/2026-07-27_studio_100board_weight_calibration_checklist_v1.md`
- Update: `03_output/2026-07-27_studio_100board_weight_calibration_context-notes_v1.md`
- Generate: `03_output/2026-07-27_studio_100board_weight_calibration_validation_v1.md`

**Interfaces:**
- Consumes: 완성된 CLI와 Studio.
- Produces: 잠긴 공통 프로필과 단계별 검증 보고서.

- [ ] **Step 1: 전체 관련 회귀 테스트 실행**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests\test_background_role.py tests\test_binary_merge_background.py tests\test_binary_merge_candidates.py tests\test_binary_merge_identity.py tests\test_binary_merge_shadow.py tests\test_studio_event_dataset.py tests\test_studio_weight_calibration.py tests\test_studio_weight_report.py tests\test_studio_harness.py tests\test_studio_validation.py tests\test_puzzle_target_visual_check.py -q`

Expected: 모든 테스트 PASS.

- [ ] **Step 2: 1판 계약 smoke 실행**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe puzzle.py --studio-calibrate-background-role --studio-root "C:\Users\PC\Desktop\02_work\05_AI\.claude\worktrees\video-file-analysis-7e6ee6\lie_captcha_studio" --studio-runs 1 --studio-run-frames 150 --studio-seed calibration-smoke-v1 --output-root "C:\Users\PC\Desktop\02_work\05_AI\maple_bot\03_output\2026-07-27_studio_calibration_smoke_v1"`

진행 조건은 GT와 trace 프레임 누락 0건, solver 입력 GT 필드 0건, 보고서 생성 성공이다. 랜덤판에 겹침 사건이 없으면 실패로 보지 않고 최대 세 개의 고정 smoke seed까지 시도해 scoreable 사건 하나를 확보한다. 세 seed 모두 사건이 없으면 Studio 사건 생성 분포를 먼저 점검한다.

- [ ] **Step 3: 10판 상한 gate 실행**

Run: 위 명령에서 `--studio-runs 10 --studio-seed calibration-gate10-v1`을 사용한다.

진행 조건은 GT가 겹침으로 표시한 사건의 감지율, pair 생성률, 정답 후보 포함률이 각각 100%이며 selector eligible 사건이 하나 이상인 것이다. 하나라도 미달하면 100판 탐색을 실행하지 않고 실패 단계를 수정한다.

- [ ] **Step 4: 100판 보정 실행**

Run: 위 명령에서 `--studio-runs 100 --studio-seed calibration-train100-v1`을 사용한다.

교차검증에서 평균형, 효율형, 고확률형을 같은 fold로 비교한다. 1차 지표가 가장 높은 프로필을 선택하고 동률 규칙을 적용해 `background_role_profile_v1.json`을 생성한다.

- [ ] **Step 5: 새 1판과 10판 잠금 검증**

Run: `C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe puzzle.py --studio-validate-locked-profile --studio-profile "C:\Users\PC\Desktop\02_work\05_AI\maple_bot\assets\puzzle\background_role_profile_v1.json" --studio-root "C:\Users\PC\Desktop\02_work\05_AI\.claude\worktrees\video-file-analysis-7e6ee6\lie_captcha_studio" --studio-runs 1 --studio-run-frames 150 --studio-seed locked-smoke-v1 --output-root "C:\Users\PC\Desktop\02_work\05_AI\maple_bot\03_output\2026-07-27_studio_locked_validation_v1"`

1판에서 파이프라인 계약이 통과하면 `--studio-runs 10 --studio-seed locked-gate10-v1`로 확대한다. 10판에서 잘못된 전환, 후보 누락, 사건 계보 누락이 하나라도 있으면 100판을 실행하지 않는다.

- [ ] **Step 6: 새 100판 최종 잠금 검증**

Run: 위 잠금 명령에서 `--studio-runs 100 --studio-seed locked-final100-v1`을 사용한다.

성공 기준은 겹침 역할 복원 100%, 잘못된 전환 0건, `SAFE_HOLD`로 인한 전체판 실패 0건, 전체 추적 100/100, 후보 생성 실패 0건이다. 미달 시 가중치를 즉시 다시 보정하지 않고 단계별 실패 분류를 validation 문서에 기록한다.

- [ ] **Step 7: 검증 문서와 프로필 커밋**

```powershell
git add -- maple_bot/assets/puzzle/background_role_profile_v1.json 03_output/2026-07-27_studio_100board_weight_calibration_checklist_v1.md 03_output/2026-07-27_studio_100board_weight_calibration_context-notes_v1.md 03_output/2026-07-27_studio_100board_weight_calibration_validation_v1.md
git commit -m "Studio 100판 공통 가중치 검증 결과 기록"
```

## 최종 중단 규칙

- 1판에서 계약이 깨지면 10판을 실행하지 않는다.
- 10판에서 사건 감지, pair, 정답 후보 포함 상한이 100%가 아니면 100판 가중치 탐색을 실행하지 않는다.
- 교차검증 대조 성능이 보정 성능보다 낮으면 프로필을 잠그지 않는다.
- 잠금 10판에서 잘못된 전환이 발생하면 잠금 100판을 실행하지 않는다.
- 최종 100판 실패는 가중치 문제로 단정하지 않고 후보 생성, 사건 계보, 관찰 신호, selector 순으로 분류한다.
