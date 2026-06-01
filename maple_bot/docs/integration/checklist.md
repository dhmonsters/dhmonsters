# DHMONSTERS 통합 구현 체크리스트

> 도면: `docs/2026-06-01_통합아키텍처도면_v1.md` (승인됨 2026-06-01)
> 진행 방식: 모듈 단위. 각 모듈 = 인터페이스 계약 구현 + 테스트 + 커밋.

## 전체 구현 순서 (도면 5-3 기준)
- [x] **M1. Humanizer + InputBackend** ✓ 14 passed (모든 행동의 기반)
- [x] M2. Scanner 프레임워크 + 이벤트큐 ✓ 16 passed
- [x] M3. Navigation (BlockRunner + FloorJudge) ✓ 18 passed
- [x] M4. MinigameSolver 사이드카 (골격) ✓ 15 passed
- [x] M5. Acting (Combat/Buff/Charlie) ✓ 14 passed
- [x] M6. Orchestrator 통합 (조율코어) ✓ 11 passed
- [x] M7. UI 6카테고리 셸 (DESIGN.md 적용) ✓ 8 passed
- [x] M8. 런타임 결선 (BotRuntime — 7모듈 조립) ✓ 4 passed
- [x] M9. config 어댑터 (config.json → RuntimeConfig) ✓ 7 passed

---

## M1. Humanizer + InputBackend (현재)

**목표.** 모든 입력의 단일 통제점. "사람같은 움직임" 대전제의 구조적 구현.
**위치.** `core/humanize/` (신규 패키지)
**계약 (도면 5-4).**
- `InputBackend`: key_down/key_up/press. Interception(주)/SendInput(폴백) 교체가능
- `Humanizer.perform(Intent)`: Intent를 사람같이 변형 후 InputBackend 호출
- `Intent{action, key, base_hold_sec, base_delay, risk_profile}`

### 태스크
- [x] M1-1. `Intent` 데이터클래스 정의 → verify: 필드/타입 단위테스트 ✓ 6 passed
- [x] M1-2. `InputBackend` 추상 인터페이스 + `InterceptionBackend`/`SendInputBackend` 2구현 (A 기존코드 베이스) → verify: 백엔드 자동선택 테스트 ✓ 3 passed
- [x] M1-3. `Humanizer` 변형 로직 (지터/반응시간/불완전성, risk_profile별 분포) → verify: 비균일 통계 테스트 ✓
- [x] M1-4. risk_profile 3종(careful/normal/fast) 파라미터 → verify: careful>fast 딜레이 검증 ✓
- [x] M1-5. 통합 스모크 (백엔드 자동선택→sendinput 폴백, perform 지터 확인) → ✓
- [ ] M1-6. 커밋 ← 진행 중

**성공 기준.** Humanizer.perform(Intent) 호출 시 ①risk_profile에 따라 타이밍 분포가 바뀌고 ②동일 키 연타가 통계적으로 비균일하며 ③백엔드 유무와 무관하게 동작.

---

## M2. Scanner 프레임워크 + 이벤트큐

**목표.** god-loop 해체 토대. C "전용 스캐너 스레드 + 이벤트큐" 패턴.
**위치.** `core/sensing/`
**계약 (도면 5-4).** Scanner.start(event_queue)/stop. Event{type, data, ts}.

### 태스크
- [x] M2-1. Event 데이터클래스 ✓ 4 passed
- [x] M2-2. Scanner 추상 + 스레드 생명주기(예외견고성 포함) ✓ 4 passed
- [x] M2-3. CharScanner (C HSV+면적필터) ✓ 4 passed
- [x] M2-4. AntiMobScanner (B 유형별 다중템플릿) ✓ 4 passed
- [x] M2-5. 커밋 ← 진행 중

**성공 기준.** Scanner를 start하면 독립 스레드가 돌며 감지 시 Event를 큐에 push, stop하면 깔끔히 종료. AntiMobScanner는 config의 유형별 on/off를 따름.

## M3. Navigation (BlockRunner + FloorJudge)

**목표.** 사용자 최대 불만(동선 부자연) 해결. C 데이터기반 동선 + 도착확인 폐루프.
**위치.** `core/navigation/`
**계약 (도면 5-4).** Navigation.set_route(blocks)/step(pos)/is_arrived(). Block{type,target_x,move_type,direction}.

### 태스크
- [x] M3-1. Block 데이터클래스 + dict직렬화 ✓ 7 passed
- [x] M3-2. FloorJudge (Y층판별+도착확인 폐루프) ✓ 6 passed
- [x] M3-3. BlockRunner (walk/teleport 거리폴백, Humanizer 경유, 끼임감지) ✓ 5 passed
- [x] M3-4. 커밋 ← 진행 중

**성공 기준.** target_x로 walk/teleport(>15px) 분기 이동, 3px 이내 도착판정, 모든 키는 Humanizer 경유. FloorJudge가 Y로 현재층·도착여부 판정.

## M4. MinigameSolver 사이드카

**목표.** 거탐 엔진 격리. 새 엔진(비올레타) 꽂기식. 도면 5-5 콘센트테스트1 실현.
**위치.** `core/minigame/`
**계약 (도면 5-4).** can_handle(type)/solve(screenshot,ctx)→SolveResult. 사이드카 IPC 격리.

### 태스크
- [x] M4-1. SolveResult + MinigameSolver 추상 ✓ 4 passed
- [x] M4-2. SolverRegistry (콘센트 격리 입증) ✓ 4 passed
- [x] M4-3. SidecarChannel IPC 추상 + InMemory Fake ✓ 4 passed
- [x] M4-4. PlanetV2Engine (채널왕복+타임아웃안전) ✓ 3 passed
- [x] M4-5. 커밋 ← 진행 중

**성공 기준.** 본체는 registry.solve(type, ...)만 호출하고 어느 엔진인지 모름. 새 엔진 등록 1줄로 추가되며 기존 코드 무수정(콘센트 격리 테스트로 입증).

## M5. Acting

**목표.** 전투/버프/찰리. Humanizer 두번째 소비처. A 전투우위 + C 찰리 + B 보호목록.
**위치.** `core/acting/`

### 태스크
- [x] M5-1. Combat (게이지물약+공격) ✓ 5 passed
- [x] M5-2. BuffManager (주기버프+캔슬대기) ✓ 4 passed
- [x] M5-3. CharlieExchange (교환시퀀스, 구매제외) ✓ 5 passed
- [x] M5-4. 커밋 (JunkSell은 M6 통합시 A junk_seller 이식)

## 헌법 (도면 0번 — 전 모듈 불변)
- 화면인식 + Interception + Humanizer만. 메모리조작(pymem/ReadProcessMemory) 전면 배제
- 모든 행동은 Humanizer 경유. 고정상수 타이밍 직접입력 금지
- 외부 블랙박스(거탐)는 인터페이스 뒤 격리
