# 전역 키 홀드 정책과 빨코2 설정 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 모든 시간 기반 키 입력에 하향 5% 랜덤을 정확히 한 번 적용하고, 빨코2의 좌표·공격 설정을 접이식 UI에서 조절하며 완료 후 텔포 간격을 현재 체감 속도에 맞춘다.

**Architecture:** 키 홀드 랜덤은 실제 물리 입력 경계에 집중하고 상위 기능에서는 원래 홀드값을 전달한다. `key_down → sleep → key_up`을 직접 소유하는 경로만 해당 루틴에서 한 번 적용한다. 빨코2 시간 설정은 기존 `rednose2_v5`에 병합하고 타이밍 버전으로 기존 시작 기준 간격과 새 완료 기준 간격을 구분한다.

**Tech Stack:** Python 3.14, PyQt6, pytest, Interception 입력 백엔드.

**Spec:** `03_output/2026-08-13_rednose2-global-key-timing-design_v1.md`

## Global Constraints

- 실제 키 홀드만 `round(value * uniform(0.95, 1.0), 4)`를 한 번 적용한다.
- 간격, 쿨다운, 텔포 전 대기, 좌표 폴링에는 랜덤을 적용하지 않는다.
- Interception 실패 시 다른 입력 방식으로 폴백하지 않는다.
- 방향키처럼 좌표 조건까지 유지하는 입력은 고정 홀드 랜덤 대상이 아니다.
- 빨코2 좌표와 빨코3 동선은 변경하지 않는다.
- UTF-8을 유지하며 구형 UI를 연결하지 않는다.
- EXE 빌드, 설치본 생성, 푸시와 배포는 하지 않는다.

---

### Task 1: 물리 입력 경계의 단일 홀드 랜덤

**Files:**
- Modify: `core/interception_backend.py:247-253`
- Modify: `core/input_controller.py:168-178`
- Modify: `core/humanize/backend.py:84-94`
- Test: `tests/test_interception_press_timing.py`
- Test: `tests/test_backend.py`

**Interfaces:**
- Consumes: `core.humanize.timing.down_5(value, rng=None) -> float`.
- Produces: `press(key: str, hold_sec: float)`가 홀드값을 한 번만 하향 랜덤하고 별도 `0.02초` 하한 없이 대기하는 물리 입력 계약.

- [ ] **Step 1: Interception 단일 적용 실패 테스트 작성**

```python
def test_press_randomizes_hold_once_without_twenty_ms_floor(monkeypatch):
    sleeps = []
    monkeypatch.setattr(interception_backend, "down_5", lambda value: 0.0097)
    monkeypatch.setattr(interception_backend.time, "sleep", sleeps.append)
    monkeypatch.setattr(interception_backend, "key_down", lambda key: None)
    monkeypatch.setattr(interception_backend, "key_up", lambda key: None)
    interception_backend.press("x", 0.01)
    assert sleeps == [0.0097]
```

- [ ] **Step 2: RED 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_interception_press_timing.py -q`

Expected: 현재 `0.02` 하한 때문에 `sleeps == [0.02]`로 실패.

- [ ] **Step 3: 물리 입력 경계 최소 구현**

```python
from core.humanize.timing import down_5

def press(key: str, hold_sec: float = 0.05) -> None:
    key_down(key)
    applied_hold = down_5(hold_sec)
    time.sleep(applied_hold)
    key_up(key)
```

`InputController`의 비 Interception 분기와 `SendInputBackend.press()`도 같은 계약을 적용하되, Interception으로 위임할 때는 원값을 넘겨 이중 적용을 막는다.

- [ ] **Step 4: GREEN과 백엔드 회귀 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_interception_press_timing.py tests/test_backend.py -q`

- [ ] **Step 5: 커밋**

```text
fix: 키 홀드 랜덤을 물리 입력 경계로 통일
```

### Task 2: 상위 기능의 이중 랜덤과 시간 간격 랜덤 제거

**Files:**
- Modify: `core/acting/combat.py`
- Modify: `core/acting/buff.py`
- Modify: `core/acting/pet.py`
- Modify: `core/acting/charlie.py`
- Modify: `core/acting/attack_sequence.py`
- Modify: `core/navigation/block_runner.py`
- Modify: `core/navigation/rednose3_runner.py`
- Modify: `core/navigation/world_runner.py`
- Modify: `core/runtime.py`
- Test: `tests/test_direct_action_input.py`
- Test: `tests/test_combat.py`
- Create: `tests/test_global_key_timing.py`

**Interfaces:**
- Consumes: Task 1의 물리 `press(key, raw_hold_sec)` 계약.
- Produces: 상위 기능은 홀드 원값과 고정 간격값을 전달하며, 직접 `key_down/key_up`하는 홀드만 `down_5()`를 호출한다.

- [ ] **Step 1: 기능별 원값 전달 실패 테스트 작성**

```python
def test_combat_passes_raw_attack_and_potion_holds_to_backend():
    backend = RecordingBackend()
    combat = Combat(backend)
    combat.attack("end", hold=0.9)
    combat._press_potion("9", 0.05)
    assert backend.presses == [("end", 0.9), ("9", 0.05)]
```

`tests/test_global_key_timing.py`에 버프 `0.8`, 펫 `0.05`, 찰리 `0.05`, 공격 연속기 각 키 홀드, 블록 텔포 `0.05`, 빨코3 설정 홀드, 월드 액션 홀드와 런타임 채팅 `0.05`가 기록 백엔드에 그대로 도착하는 개별 테스트를 둔다. 같은 파일에서 공격 간격, 버프 간격, 펫 간격, 물약 쿨다운의 다음 실행 시각이 각각 설정 원값과 일치하는지 검사한다.

- [ ] **Step 2: RED 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_global_key_timing.py tests/test_direct_action_input.py tests/test_combat.py -q`

Expected: 기존 `down_5()` 또는 `plus_minus_5()`로 인해 기록된 홀드·간격이 원값과 달라 실패.

- [ ] **Step 3: 상위 랜덤 제거**

```python
self._input.press(skill_key, hold)
self._input.press(key, hold_sec)
self._cur_interval = interval
self._potion_next_allowed[label] = now + rule.cooldown
```

`press()`에 전달하던 `down_5/plus_minus_5`만 제거한다. 간격·쿨다운·대기에 적용하던 랜덤도 제거한다. 사다리 점프처럼 직접 `key_down → sleep → key_up`하는 경로의 홀드 `down_5()`는 유지하고, 그 경로의 `up_delay_sec`는 원값을 사용한다.

- [ ] **Step 4: GREEN과 관련 회귀 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_global_key_timing.py tests/test_direct_action_input.py tests/test_combat.py tests/test_block_runner.py -q`

- [ ] **Step 5: 커밋**

```text
refactor: 상위 입력의 이중 랜덤 제거
```

### Task 3: 빨코2 시간 설정과 기존 설정 마이그레이션

**Files:**
- Modify: `core/config_adapter.py:322-397`
- Test: `tests/test_config_adapter.py`

**Interfaces:**
- Produces: `REDNOSE2_TIMING_DEFAULTS: dict[str, float | int]`.
- Produces: `_merge_rednose2_timing_settings(raw: dict | None) -> dict`.
- Produces: 런타임 빨코2 프로필의 `timing_version=2`, 홀드 `0.30/0.90/0.10`, 완료 후 간격 `0.72/0.90`.

- [ ] **Step 1: 기존 설정과 새 설정의 실패 테스트 작성**

```python
def test_legacy_rednose2_timing_uses_completion_interval_compatibility_defaults():
    data = base_config()
    data["rednose2_v5"] = {
        "floor2_hunt_teleport_interval_sec": 0.4,
        "floor2_right_edge_teleport_interval_sec": 1.8,
    }
    profile = adapt_config(data).rednose2_v5
    assert profile["floor2_hunt_teleport_interval_sec"] == 0.72
    assert profile["floor2_right_edge_teleport_interval_sec"] == 0.90

def test_versioned_rednose2_timing_preserves_saved_values():
    data["rednose2_v5"] = {"timing_version": 2, "attack_hold_sec": 0.77}
    assert adapt_config(data).rednose2_v5["attack_hold_sec"] == 0.77
```

- [ ] **Step 2: RED 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_config_adapter.py -q`

- [ ] **Step 3: 최소 병합·검증 구현**

```python
REDNOSE2_TIMING_DEFAULTS = {
    "timing_version": 2,
    "teleport_hold_sec": 0.30,
    "attack_hold_sec": 0.90,
    "floor2_hunt_teleport_interval_sec": 0.72,
    "stair7_right_teleport_hold_sec": 0.10,
    "floor2_right_edge_teleport_interval_sec": 0.90,
}
```

버전 없는 입력은 시간값을 무시하고 호환 기본값을 사용한다. 버전 `2`의 유한 숫자 `0.0~10.0`만 병합한다. 기존 X 좌표 병합과 분리한다.

- [ ] **Step 4: GREEN 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_config_adapter.py -q`

- [ ] **Step 5: 커밋**

```text
feat: 빨코2 완료 후 간격 설정 마이그레이션
```

### Task 4: 빨코2 좌표·공격 접이식 UI

**Files:**
- Modify: `core_ui/rednose2_coordinate_widget.py`
- Modify: `core_ui/pages.py:617-624`
- Test: `tests/test_rednose2_coordinate_widget.py`
- Test: `tests/test_pages.py`

**Interfaces:**
- Consumes: Task 3의 `REDNOSE2_TIMING_DEFAULTS`.
- Produces: `Rednose2CoordinateWidget.set_hunt_ground(name: str) -> None`.
- Produces: `coordinateToggle`, `coordinateContent`, `timingToggle`, `timingContent` object names.
- Produces: `timing_inputs: dict[str, QDoubleSpinBox]`, `save_timing_values()`, `restore_timing_defaults()`.

- [ ] **Step 1: 표시·접기·저장 실패 테스트 작성**

```python
def test_rednose2_sections_start_collapsed_and_toggle_independently(app):
    widget = Rednose2CoordinateWidget(FakeConfig(active="빨코2"))
    assert not widget.coordinate_content.isVisibleTo(widget)
    assert not widget.timing_content.isVisibleTo(widget)
    widget.coordinate_toggle.click()
    assert widget.coordinate_content.isVisibleTo(widget)
    assert not widget.timing_content.isVisibleTo(widget)

def test_rednose2_card_only_shows_for_rednose2(app):
    widget.set_hunt_ground("빨코3")
    assert widget.isHidden()
    widget.set_hunt_ground("rednose2v5")
    assert not widget.isHidden()
```

시간 입력 저장 시 좌표값이 보존되고 좌표 저장 시 시간값이 보존되는 테스트를 추가한다.

- [ ] **Step 2: RED 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_rednose2_coordinate_widget.py tests/test_pages.py -q`

- [ ] **Step 3: 접이식 위젯과 프리셋 신호 연결 구현**

`QPushButton.setCheckable(True)`와 콘텐츠 `QWidget.setVisible(checked)`를 사용한다. `HuntGroundPresetWidget.preset_loaded`를 빨코2 위젯의 `set_hunt_ground`에 연결하고 현재 사냥터 입력란의 `editingFinished`에서도 갱신한다.

```python
spin = QDoubleSpinBox()
spin.setRange(0.0, 10.0)
spin.setDecimals(2)
spin.setSingleStep(0.01)
```

- [ ] **Step 4: GREEN 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_rednose2_coordinate_widget.py tests/test_pages.py -q`

- [ ] **Step 5: 커밋**

```text
feat: 빨코2 좌표와 공격 설정 접기 UI 추가
```

### Task 5: 빨코2 실제 공격 홀드와 완료 후 간격

**Files:**
- Modify: `core/navigation/rednose2_runner.py:469-481, 531-680`
- Test: `tests/test_rednose2_timing.py`
- Test: `tests/test_rednose2_collection_stage.py`

**Interfaces:**
- Consumes: Task 3의 빨코2 시간 프로필.
- Produces: `_teleport_attack(direction: str) -> None`이 공격키 총 홀드에 `down_5()`를 한 번 적용하고 텔포 홀드는 물리 `press()` 경계에 원값을 전달함.
- Produces: 다음 텔포 허용 시각을 동작 완료 후 고정 간격으로 계산.

- [ ] **Step 1: 총 홀드와 완료 후 간격 실패 테스트 작성**

```python
def test_teleport_attack_uses_randomized_total_attack_hold_once(monkeypatch):
    monkeypatch.setattr(rednose2_runner, "down_5", lambda value: 0.855 if value == 0.9 else value)
    runner._teleport_attack("right")
    assert attack_down_to_up_duration == pytest.approx(0.855)
    assert teleport_press == ("x", 0.3)

def test_next_teleport_interval_starts_after_action_completion():
    runner = make_timed_runner(positions=[(60, 62), (72, 62), (84, 62), (101, 62)])
    runner._move_to_target_v5(101, attack=True, interval_sec=0.72)
    assert second_action_started - first_action_finished >= 0.72
```

- [ ] **Step 2: RED 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_rednose2_timing.py tests/test_rednose2_collection_stage.py -q`

- [ ] **Step 3: 최소 시간 계산 구현**

```python
attack_hold = down_5(float(self._profile.get("attack_hold_sec", 0.9)))
started_at = time.monotonic()
h.hold_action(attack_key)
try:
    self._sleep(float(self._profile.get("attack_to_teleport_sec", 0.5)))
    h.press_action(teleport_key, float(self._profile.get("teleport_hold_sec", 0.3)))
    remaining = attack_hold - (time.monotonic() - started_at)
    if remaining > 0:
        self._sleep(remaining)
finally:
    h.release_action(attack_key)
```

`_move_to_target_v5()`에서는 액션 반환 후의 `time.monotonic()`에 고정 `interval_sec`를 더한다. 텔포 전 대기와 간격에 있던 `down_5()`는 제거한다. 7번 전용 우측 텔포 홀드는 원값을 `press_action()`에 전달한다.

- [ ] **Step 4: GREEN과 빨코2 회귀 확인**

Run: `python -m pytest -p no:cacheprovider tests/test_rednose2_timing.py tests/test_rednose2_collection_stage.py tests/test_floor_hunt_runner.py -q`

- [ ] **Step 5: 커밋**

```text
fix: 빨코2 텔포 간격을 동작 완료 기준으로 적용
```

### Task 6: 통합 검증과 작업 기록

**Files:**
- Modify: `03_output/2026-08-13_rednose2-global-key-timing-checklist_v1.md`
- Modify: `03_output/2026-08-13_rednose2-global-key-timing-context-notes_v1.md`

**Interfaces:**
- Consumes: Tasks 1~5의 코드와 테스트.
- Produces: 재현 가능한 검증 결과와 남은 기존 실패 기록.

- [ ] **Step 1: 관련 테스트 통합 실행**

Run: `python -m pytest -p no:cacheprovider tests/test_interception_press_timing.py tests/test_backend.py tests/test_global_key_timing.py tests/test_direct_action_input.py tests/test_combat.py tests/test_block_runner.py tests/test_config_adapter.py tests/test_rednose2_coordinate_widget.py tests/test_pages.py tests/test_rednose2_timing.py tests/test_rednose2_collection_stage.py -q`

- [ ] **Step 2: 정적 검사**

Run: `python -m compileall -q core core_ui tests`

Run: `git diff --check`

수정 파일을 strict UTF-8로 디코딩해 BOM과 손상 여부를 확인한다.

- [ ] **Step 3: 전체 테스트 시도**

Run: `python -m pytest -p no:cacheprovider -q`

기존 `tests/test_humanizer.py`, `tests/test_intent.py`의 제거된 `RiskProfile` 수집 오류 등 현재 브랜치 이전 실패는 별도로 기록하고 이번 변경으로 새로 발생한 실패만 수정한다.

- [ ] **Step 4: 체크리스트와 작업 메모 갱신**

관련 테스트 통과 수, 전체 테스트 상태, 경고, 변경 제외 범위와 실제 커밋을 기록한다.

- [ ] **Step 5: 문서 커밋**

```text
docs: 전역 키 홀드와 빨코2 설정 검증 기록
```
