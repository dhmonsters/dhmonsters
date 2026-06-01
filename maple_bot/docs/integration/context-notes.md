# 통합 구현 컨텍스트 노트

> 구현 중 내린 결정과 그 이유를 계속 append. 다음 세션이 재유도 없이 이어가도록.

## 2026-06-01 — 구현 착수

### 기반 결정 (도면에서 확정)
- 본체 Python 3.14, 거탐 사이드카 3.13 (Planet v2 코어 cp313 ABI)
- 입력 Interception(주) + SendInput(폴백). A `core/interception_backend.py` 재사용
- DESIGN.md(Linear) 설치 완료 (`maple_bot/DESIGN.md`). UI 단계에서만 적용

### M1 설계 결정
- **새 패키지 `core/humanize/`로 시작** (기존 `input_controller.py` 직접개조 아님).
  이유: god-loop 분해는 신규 구조라 깨끗한 인터페이스부터. 기존 코드는 베이스로 참조.
- **기존 자산 재사용**:
  - `core/interception_backend.py`: 이미 enable()/is_active()/key_down/up/press 完. InterceptionBackend가 이걸 래핑
  - `core/input_controller.py`: Win32 SendInput 구현(`_send_key`, `_vk`). SendInputBackend가 이걸 래핑
- **Humanizer가 흡수할 기존 산재 로직**: A `map_navigator._rnd()`, potion `random.uniform(0.03,0.20)`,
  bot_loop의 hold_sec=0.12 등 흩어진 변동값들 → 전부 Humanizer 단일 통제점으로

### 미해결/주의
- Interception 드라이버 이 PC 설치여부 미확인 → SendInput 폴백으로 개발, 실기 검증은 별도
- risk_profile 기본 분포값은 C의 ±10% + 반응시간 150~400ms를 출발점으로, 실측 튜닝 필요
- pymem 등 메모리조작 절대 도입 금지 (헌법)

### 작업트리 상태
- 커밋 c28de47(도면), f6ef309(Interception연동+YOLO폴백+교훈), 42652bc(config경로복원)
- tools/ (pycdc·mingw64·디컴파일러)는 .gitignore 제외, 재사용 가능

## 2026-06-01 — M1 완료 (Humanizer + InputBackend)

### 구현됨
- `core/humanize/intent.py`: Intent 데이터클래스 + RiskProfile(careful/normal/fast). __post_init__ 검증
- `core/humanize/backend.py`: InputBackend 추상 + InterceptionBackend(interception_backend.py 래핑)/SendInputBackend(input_controller _vk/_send_key 재사용) + select_backend(우선순위 자동선택)
- `core/humanize/humanizer.py`: perform(Intent) — 반응지연+hold지터+sloppy불완전성, _PROFILE로 프로파일별 분포, hold 0.03~0.30 클램프

### 검증
- tests/ 14 passed (intent 6, backend 3, humanizer 5)
- 스모크: 이 PC interception 미설치 확인 → sendinput 자동폴백. perform 지터 실측(0.0714/0.0657/0.0468)

### 결정/주의
- 백엔드는 lazy: select_backend가 is_available() 호출 시점에 드라이버 캡처 시도
- _PROFILE 파라미터는 출발점(careful reaction 0.22~0.45 등). 실기 안티밴 데이터로 추후 튜닝
- 다음(M2): Scanner 프레임워크 + 이벤트큐. Humanizer는 M3(Navigation)/M5(Acting)에서 소비됨

## 2026-06-01 — M2 착수 (Scanner 프레임워크 + 이벤트큐)

### 사용자 결정
- 매크로 방지몹 = B 방식 채택 (카테고리4 재확정)
  - B: macro_mob/ 에 몹 유형별 다중 템플릿 (lulu1~2 루루모, rich1~13 리치, monster1~9)
  - config 키: lulumo_enabled / rich_enabled / auto_guard_enabled (유형별 on/off)
  - → AntiMobScanner 는 "유형별 템플릿 세트"를 돌며 감지. A anti_mob 단일방식 대신 B 다중템플릿

### M2 설계
- Event{type, data, ts} 데이터클래스 (도면 5-4)
- Scanner 추상: start(event_queue)/stop, 독립 스레드, 큐에 push만
- 이벤트큐: thread-safe (queue.Queue)
- 첫 구현체: CharScanner(C vision.py HSV 방식 — 카테고리1 채택). AntiMobScanner는 M2 후반 or M5

## 2026-06-01 — M2 완료 (Scanner 프레임워크 + 이벤트큐)

### 구현됨 (core/sensing/)
- event.py: Event{type,data,ts} 자동 타임스탬프 + type 검증
- scanner.py: Scanner 추상 — 독립 스레드(start/stop/is_running), scan_once 예외 삼킴(견고성), None반환시 push안함
- char_scanner.py: find_char_in_hsv 순수함수(inRange→contour→면적필터→moments, C vision.py 방식) + CharScanner. set_hsv 오버라이드
- antimob_scanner.py: match_any_template(B 다중템플릿) + AntiMobScanner. enabled_types로 유형별 on/off

### 검증
- tests 30 passed 누계 (M1 14 + M2 16: event4/scanner4/char4/antimob4)

### 디버깅 기록 (read-errors 원칙)
- AntiMob 테스트 2개 실패 → 추측않고 실제 점수 출력으로 진단
- 원인: 균일색(분산0) 템플릿이 TM_CCOEFF_NORMED에서 모든 위치 1.0 (정규화 분모0). 코드 아닌 테스트 픽스처 문제
- 수정: 텍스처(랜덤) 패치 + 노이즈 배경으로 픽스처 현실화 → 통과. 실제 몬스터 템플릿은 텍스처 있어 무문제

### 결정/주의
- B 방식 확정: macro_mob 유형별(lulu/rich/monster) 다중템플릿, config lulumo/rich/auto_guard_enabled로 on/off
- Scanner는 capture를 callable로 주입받음(테스트 용이, screen_reader 의존 역전)
- 다음(M3): Navigation BlockRunner — C routine_runner 스키마 + 도착확인 폐루프. Humanizer(M1) 소비 시작

## 2026-06-01 — M3 착수 (Navigation: BlockRunner + FloorJudge)

### 설계 (도면 5-2 동선 결론 + C 코드 기반)
- Block 데이터클래스: type(move/attack/ladder/jump) + 필드. C routine_runner 스키마 채택
  - move: target_x, move_type(walk/teleport), direction
  - attack: skill_key, attack_mode(duration/count), attack_value, direction
  - ladder: ladder_x, y_top, y_bot, exit_side
- BlockRunner: 블록 시퀀스 순차 실행. 모든 입력은 Humanizer(M1) 경유 ★첫 소비
  - C CoordScriptRunner 검증값: TOLERANCE=3px(도착판정), TELEPORT_MIN_DIST=15px(거리>15 텔포, 이하 walk 폴백)
- FloorJudge: Y좌표로 층 판별 + is_arrived 도착확인 폐루프 (A "2초 무조건 등반" 문제 해결)
  - 현재위치 콜백 주입(공유 위치상태, CharScanner가 갱신)

### A 대비 개선점 (사용자 불만 해결)
- A: walk+밧줄만, 도착확인 없음, 이중엔진 경합 → C 방식 단일엔진+텔포+폐루프로

## 2026-06-01 — M3 완료 (Navigation: BlockRunner + FloorJudge)

### 구현됨 (core/navigation/)
- block.py: Block 데이터클래스(move/attack/ladder/jump) + from_dict/to_dict(config 직렬화, 전방호환)
- floor_judge.py: Floor + FloorJudge.floor_at(Y층판별)/is_arrived(목표층 ±tol 도착확인). A "2초 무조건등반→오판정" 해결
- block_runner.py: BlockRunner — TOLERANCE=3 폐루프 + TELEPORT_MIN_DIST=15 거리폴백(>15 텔포, 이하 walk). ★M1 Humanizer 첫 소비. 끼임감지(5회 미변화→포기)

### 검증
- tests 48 passed 누계 (M1 14 + M2 16 + M3 18: block7/floor6/runner5)

### 핵심: 헌법 준수 입증
- test_all_input_goes_through_humanizer: runner가 _backend 직접 안 들고 humanizer만 경유 → 모든 입력 단일통제점 통과 확인

### 디버깅 기록
- BlockRunner 테스트 1개 실패 → 진단: 픽스처 MovingChar가 pos()호출=이동이라 시작거리10/speed10이면 첫 체크에서 즉시 도착(입력0). 코드정상, 픽스처를 거리12/speed5로 수정

### 결정/주의
- attack/ladder/jump 블록은 run_block에서 아직 pass(move만 구현). M5 Acting/후속에서 채움
- BlockRunner는 pos_fn 콜백 주입(CharScanner 공유위치와 결합은 M6 Orchestrator에서)
- 다음(M4): MinigameSolver 사이드카 (Planet v2 3.13 + mmap IPC) — 기술리스크 최대 구간
