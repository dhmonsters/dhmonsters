# 빨코2 7번 복귀 공격 텔레포트와 좌측 추락 복구 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 7번 복귀 뒤 첫 두 공격 텔레포트의 공격 홀드·텔레포트 홀드·간격을 각각 설정하고, 회수 및 좌측 추락 복구의 느린 2층 회수 이동을 안정화한다.

**Architecture:** 기존 `RedNose2RouteRunner`의 공격 텔레포트에 선택적 타이밍 재정의를 추가하고 우측 끝 이동에서 첫 두 번만 이를 사용한다. 마지막 정상 2층 X를 보존하여 일반 추락의 좌·우를 구분하고, 좌측 추락만 우측 끝까지 느린 회수 이동을 수행한다. 기존 좌표계와 미니맵 영역은 변경하지 않는다.

**Tech Stack:** Python 3.14, PyQt6, pytest.

**Spec:** 사용자 승인 대화 및 `03_output/2026-08-29_rednose2-stair7-timing-and-fall-recovery_v1_context-notes.md`.

## Global Constraints

- 첫 번째와 두 번째 공격 텔레포트에 공격 홀드·텔레포트 홀드·완료 후 간격을 각각 둔다.
- 세 번째부터 기존 우측 끝 이동 타이밍을 사용한다.
- 회수 루틴의 느린 이동 간격은 우측 끝 도달 뒤 14/15 접근까지 유지한다.
- 좌측 일반 추락은 7번 복귀 뒤 우측 끝까지만 느리게 회수하고 14/15에는 진입하지 않는다.
- 우측 일반 추락은 7번 복귀 뒤 기존 정상 사냥을 재개한다.
- 2층 정상 사냥 이동은 방향과 무관하게 공격 텔레포트를 유지한다.

---

### Task 1: 타이밍 설정 계약

**Files:**
- Modify: `core/config_adapter.py`
- Modify: `core_ui/rednose2_coordinate_widget.py`
- Test: `tests/test_config_adapter.py`
- Test: `tests/test_rednose2_coordinate_widget.py`

**Interfaces:**
- Consumes: `REDNOSE2_TIMING_DEFAULTS`, 기존 버전 2 설정 병합 방식.
- Produces: 첫 번째·두 번째 공격 텔레포트용 6개 실수 설정값.

- [ ] 새 설정 6개의 기본값·저장·복원 실패 테스트를 작성한다.
- [ ] 관련 테스트를 실행하여 새 키가 없어 실패하는지 확인한다.
- [ ] 기본값과 UI 입력 필드를 최소 구현한다.
- [ ] 관련 테스트를 다시 실행하여 통과를 확인한다.

### Task 2: 첫 두 공격 텔레포트와 느린 14/15 접근

**Files:**
- Modify: `core/navigation/rednose2_runner.py`
- Test: `tests/test_rednose2_timing.py`
- Test: `tests/test_rednose2_collection_stage.py`

**Interfaces:**
- Consumes: Task 1의 6개 타이밍 값과 `floor2_right_edge_teleport_interval_sec`.
- Produces: `_move_floor2_right_edge()`의 첫 두 전용 공격 텔레포트와 14/15까지 이어지는 느린 간격.

- [ ] 첫 두 동작의 공격 홀드·텔레포트 홀드·간격이 독립 적용되는 실패 테스트를 작성한다.
- [ ] 14/15 접근이 우측 끝 느린 간격을 재사용하는 실패 테스트를 작성한다.
- [ ] 테스트를 실행하여 예상 실패를 확인한다.
- [ ] 선택적 공격 타이밍 재정의와 이동 구간 연결을 최소 구현한다.
- [ ] 관련 테스트를 다시 실행하여 통과를 확인한다.

### Task 3: 일반 추락 좌·우 복구 분기

**Files:**
- Modify: `core/navigation/rednose2_runner.py`
- Test: `tests/test_rednose2_recovery_autosell_minimap.py`

**Interfaces:**
- Consumes: 마지막으로 확인된 정상 2층 X, 7번 계단 X, `_move_floor2_right_edge()`.
- Produces: 좌측 추락의 우측 끝 느린 회수와 우측 추락의 기존 정상 복귀.

- [ ] 좌측 추락만 우측 끝 회수를 실행하고 다음 방향을 왼쪽으로 설정하는 실패 테스트를 작성한다.
- [ ] 우측 추락은 우측 끝 회수를 실행하지 않는 실패 테스트를 작성한다.
- [ ] 테스트를 실행하여 예상 실패를 확인한다.
- [ ] 마지막 2층 X 보존과 추락 복구 헬퍼를 최소 구현한다.
- [ ] 관련 테스트를 다시 실행하여 통과를 확인한다.

### Task 4: 회귀 검증과 기록

**Files:**
- Modify: `03_output/2026-08-29_rednose2-stair7-timing-and-fall-recovery_v1_checklist.md`
- Modify: `03_output/2026-08-29_rednose2-stair7-timing-and-fall-recovery_v1_context-notes.md`

**Interfaces:**
- Consumes: Tasks 1~3 구현 결과.
- Produces: 검증 결과와 재개 가능한 작업 기록.

- [ ] 빨코2 관련 테스트 전체를 실행한다.
- [ ] 변경 파일의 구문 검사를 실행한다.
- [ ] 체크리스트와 컨텍스트 기록을 갱신한다.
- [ ] 이번 작업 파일만 의미 단위로 커밋한다.
