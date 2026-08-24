# 빨코2 회수 연속 실행 및 공격시간 설정 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 24번 하강 이후 지정 동작을 수행하고, 일시적인 사다리 복귀 실패가 일반 사냥으로 전환되지 않게 하며, 14/15번과 27번 진입 공격시간을 UI에서 설정한다.

**Architecture:** 진행 중인 회수 단계가 있으면 일반 사냥보다 회수 상태 머신을 먼저 호출한다. 24번 하강 확인 직후 오른쪽 텔레포트 2회를 수행하고 기존 7번 사다리 복귀를 이어간다. 기존 빨코2 타이밍 설정 병합·UI 저장 경로에 공격시간 두 값을 추가한다.

**Tech Stack:** Python 3.14, PySide6, pytest.

**Spec:** 사용자 승인 대화와 `03_output/2026-08-24_rednose2-collection-routine_v1_context-notes.md`.

## Global Constraints

- 체류시간 설정은 추가하지 않는다.
- 27번 마무리 공격 0.5초는 변경하지 않는다.
- 설정 변경은 저장 후 다음 F1 재시작부터 적용한다.
- 기존 미니맵 좌표와 다른 이동 설정은 변경하지 않는다.

---

### Task 1: 회수 단계 보존과 우선 재개

**Files:**
- Modify: `core/navigation/rednose2_runner.py`
- Test: `tests/test_rednose2_collection_stage.py`

**Interfaces:**
- Consumes: `RedNose2RouteRunner._collection_stage`.
- Produces: `_run_rednose_new_v5_once()`가 진행 중인 회수를 일반 사냥보다 먼저 재개하는 동작.

- [x] 사다리 복귀 첫 실패 후 다음 실행에서 일반 복구가 아닌 회수 루틴을 다시 호출하는 실패 테스트를 작성한다.
- [x] 테스트를 실행하여 현재 코드에서 회수 단계가 삭제되는 실패를 확인한다.
- [x] `_collection_stage is not None`이면 `_run_rednose_new_v5_collection()`을 우선 호출하도록 최소 수정한다.
- [x] 24번 진입 중 1층 도착 복구에서도 회수 단계와 타이머를 보존하는 테스트와 구현을 추가한다.
- [x] 선택 테스트를 다시 실행하여 통과를 확인한다.

### Task 2: 24번 하강 후 오른쪽 텔레포트 2회

**Files:**
- Modify: `core/navigation/rednose2_runner.py`
- Test: `tests/test_rednose2_timing.py`

**Interfaces:**
- Consumes: `_drop_from_platform24_to_floor1()` 성공 결과와 `_teleport_once("right")`.
- Produces: `floor1_drop` 성공 뒤 `right`, `right`, `stair7_return` 순서.

- [x] 하강 확인 뒤 사다리 이동 전에 오른쪽 텔레포트가 정확히 2회 호출되는 실패 테스트를 작성한다.
- [x] 테스트를 실행하여 현재 호출 횟수 0으로 실패하는지 확인한다.
- [x] 회수 상태 머신의 `floor1_drop` 성공 지점에 오른쪽 텔레포트 2회를 추가한다.
- [x] 선택 테스트를 다시 실행하여 통과를 확인한다.

### Task 3: 진입 공격 홀드시간 UI 설정

**Files:**
- Modify: `core/config_adapter.py`
- Modify: `core_ui/rednose2_coordinate_widget.py`
- Modify: `core/navigation/rednose2_runner.py`
- Test: `tests/test_config_adapter.py`
- Test: `tests/test_rednose2_coordinate_widget.py`
- Test: `tests/test_rednose2_timing.py`

**Interfaces:**
- Produces: `platform1415_attack_hold_sec: float`, `platform27_entry_attack_hold_sec: float`.
- Consumes: 기존 `rednose2_v5` 설정 저장 및 F1 재로딩 경로.

- [x] 기본값 0.50초, 저장값 병합, UI 저장, 런타임 사용에 대한 실패 테스트를 작성한다.
- [x] 테스트를 실행하여 새 설정 키 부재로 실패하는지 확인한다.
- [x] 타이밍 기본값과 UI 입력 두 항목을 추가하고 기존 설정 보존을 위해 타이밍 설정 버전 2를 유지한다.
- [x] 14/15번에서 16번 진입 전 공격과 27번 진입 후 공격이 각각 새 설정을 사용하도록 연결한다.
- [x] 선택 테스트를 다시 실행하여 통과를 확인한다.

### Task 4: 검증과 커밋

**Files:**
- Modify: `03_output/2026-08-24_rednose2-collection-continuation_v1_checklist.md`
- Modify: `03_output/2026-08-24_rednose2-collection-continuation_v1_context-notes.md`

- [x] 빨코2 관련 전체 테스트를 실행한다.
- [x] 변경한 Python 파일을 `py_compile`로 검사한다.
- [x] 변경 내용을 요구사항과 대조하고 문서에 검증 결과를 기록한다.
- [x] 관련 파일만 스테이징하고 의미 단위 커밋을 생성한다.
