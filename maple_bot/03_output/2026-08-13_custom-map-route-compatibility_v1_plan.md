# 사용자 맵 동선 호환 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 배포 기본 맵 3개는 유지하면서 설치 후 생성한 사용자 맵과 기존 이동 블럭을 보존·실행한다.

**Architecture:** 설정 로드 단계는 필수 맵을 추가만 하고 사용자 프리셋은 삭제하지 않는다. 런타임 러너 선택은 빨코2·빨코3 전용 러너를 최우선으로 유지하고, 일반 맵의 신규 `route_steps`는 `RouteStateRunner`, 구형 `route`는 `FloorHuntRunner`로 분리한다.

**Tech Stack:** Python 3.14, PyQt6, pytest.

**Spec:** `03_output/2026-08-13_movement-block-no-motion-diagnosis_v1_context-notes.md`

## 전역 제약

- 배포 기본 프리셋은 `초급 수련장`, `빨코2`, `빨코3`이다.
- 사용자가 저장한 다른 프리셋 이름과 활성 선택은 보존한다.
- 빨코2와 빨코3은 일반 동선 실행기와 동시에 실행하지 않는다.
- 사용자 설정 파일을 자동 복원하거나 덮어쓰지 않는다.
- EXE 빌드와 배포는 수행하지 않는다.

---

### Task 1: 사용자 프리셋 보존

**Files:**
- Create: `tests/test_config_manager_presets.py`
- Modify: `core/config_manager.py`

**Interfaces:**
- Consumes: `_ensure_required_presets(data: dict) -> bool`
- Produces: 사용자 프리셋과 유효한 활성 맵을 보존하면서 필수 프리셋을 보충하는 설정 로드 동작.

- [ ] 사용자 프리셋과 활성 맵이 유지되는 실패 테스트를 작성한다.
- [ ] 별칭 프리셋이 빨코 이름으로 합쳐지는 충돌 방지 테스트를 작성한다.
- [ ] 테스트가 사용자 프리셋 삭제와 활성 맵 강제 변경으로 실패하는지 확인한다.
- [ ] 허용 목록 기반 삭제를 제거하고 활성 맵이 실제 프리셋에 있을 때 보존한다.
- [ ] 설정 테스트를 통과시킨다.

### Task 2: 일반 구형 이동 블럭 실행 복원

**Files:**
- Modify: `tests/test_runtime.py`
- Modify: `core/runtime.py`

**Interfaces:**
- Consumes: `FloorHuntRunner(block_runner, get_blocks, is_active, idle_sleep=0.1)`
- Produces: 일반 맵의 `route`를 순서대로 실행하는 전용 스레드 러너.

- [ ] 일반 구형 route가 `FloorHuntRunner`를 선택하는 실패 테스트를 작성한다.
- [ ] 빨코2·빨코3은 각각 전용 러너를 계속 선택하는 테스트를 작성한다.
- [ ] 테스트가 `LegacyRouteGuard` 선택 때문에 실패하는지 확인한다.
- [ ] 일반 route 전용 분기만 `FloorHuntRunner`로 교체한다.
- [ ] 런타임 및 컨트롤러 스레드 테스트를 통과시킨다.

### Task 3: 통합 검증과 기록

**Files:**
- Modify: `03_output/2026-08-13_custom-map-route-compatibility_v1_checklist.md`
- Modify: `03_output/2026-08-13_custom-map-route-compatibility_v1_context-notes.md`

**Interfaces:**
- Consumes: Task 1과 Task 2의 테스트 결과.
- Produces: 검증 결과와 다음 작업자가 재현 가능한 인수인계 기록.

- [ ] 관련 설정·프리셋·런타임·블럭·컨트롤러 테스트를 실행한다.
- [ ] `core`, `core_ui`, `run_integrated.py` 컴파일 검사를 실행한다.
- [ ] 변경 파일의 UTF-8과 `git diff --check`를 확인한다.
- [ ] 코드와 테스트를 의미 단위로 커밋한다.
