# DHMONSTERS 통합 구현 체크리스트

> 도면: `docs/2026-06-01_통합아키텍처도면_v1.md` (승인됨 2026-06-01)
> 진행 방식: 모듈 단위. 각 모듈 = 인터페이스 계약 구현 + 테스트 + 커밋.

## 전체 구현 순서 (도면 5-3 기준)
- [x] **M1. Humanizer + InputBackend** ✓ 14 passed (모든 행동의 기반)
- [x] M2. Scanner 프레임워크 + 이벤트큐 ✓ 16 passed
- [ ] M3. Navigation (BlockRunner + FloorJudge)
- [ ] M4. MinigameSolver 사이드카 (Planet v2, 3.13 IPC)
- [ ] M5. Acting (Combat/Buff/Potion/JunkSell/Charlie)
- [ ] M6. Orchestrator 통합
- [ ] M7. UI 6카테고리 (DESIGN.md 적용)

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

## 헌법 (도면 0번 — 전 모듈 불변)
- 화면인식 + Interception + Humanizer만. 메모리조작(pymem/ReadProcessMemory) 전면 배제
- 모든 행동은 Humanizer 경유. 고정상수 타이밍 직접입력 금지
- 외부 블랙박스(거탐)는 인터페이스 뒤 격리
