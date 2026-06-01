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

## 2026-06-01 — M4 착수 (MinigameSolver 사이드카)

### 사용자 확인
- 비올레타 미출시 → 인터페이스에 자리만 마련(준비중). 현재는 Planet v2(planet)/Lona(옵션) 등록
- 출시되면 VioletaEngine 1파일 추가로 꽂기(도면 5-5 콘센트테스트1)

### 설계 (도면 5-4 계약 + 5-5 격리)
- MinigameSolver 인터페이스: can_handle(type)->bool / solve(screenshot,ctx)->SolveResult
- SolveResult{success, elapsed, note}
- 레지스트리: SolverRegistry — 등록된 엔진 중 can_handle 매칭으로 위임. 새 엔진=등록 1줄
- 사이드카 IPC: 본체3.14 ↔ 거탐3.13. C가 검증한 mmap("LonaHunter_SharedData") 패턴 참고
  - 단 M4 골격에선 IPC 추상화(SidecarChannel)만. 실제 Planet v2 .pyd 연결은 실기 검증 별도

### 이번 M4 범위 (게임 없이 테스트 가능한 골격)
- MinigameSolver 추상 + SolveResult
- SolverRegistry (can_handle 위임, 우선순위)
- StubEngine (테스트용) + PlanetV2Engine 스텁(실코어 연결 지점 표시)
- 실제 .pyd import/mmap/사이드카 프로세스는 실기 환경에서 (TODO 주석으로 연결점 명시)

### 헌법 준수
- 거탐 블랙박스는 인터페이스 뒤 격리. 본체는 can_handle/solve만 호출, 어느 엔진인지 모름

## 2026-06-01 — M4 완료 (MinigameSolver 사이드카 골격)

### 구현됨 (core/minigame/)
- solver.py: SolveResult{success,elapsed,note} + MinigameSolver 추상(can_handle/solve)
- registry.py: SolverRegistry — can_handle 위임, 등록순 우선. solve(type)→없으면 None
- sidecar.py: SolveRequest/SolveReply + SidecarChannel 추상 + InMemoryChannel(큐 Fake)
- planet_engine.py: PlanetV2Engine — 채널로 요청/응답 왕복, timeout시 실패반환(봇 안멈춤). 실코어 연결은 TODO 주석

### 검증
- tests 63 passed 누계 (M1 14 + M2 16 + M3 18 + M4 15: solver4/registry4/sidecar4/planet3)
- ★ 콘센트테스트1(도면5-5) 코드 입증: test_consent_test_add_violeta_no_modification
  비올레타 엔진 register 1줄 추가 → 기존 planet/lona 라우팅 무수정, violeta 처리됨

### 실기 환경에서 할 일 (TODO 명시됨)
- MmapChannel: 실제 3.13 사이드카 프로세스 + mmap(C LonaHunter_SharedData 패턴)
- sidecar_main.py: 3.13 임베드로 Planet_solver __mypyc.cp313.pyd import해 toss 코어 호출
- 사이드카 기동/연결은 M6 Orchestrator 또는 런처가 담당
- 비올레타 출시시 VioletaEngine 1파일 + register 1줄 (골격 검증 완료)

### 결정/주의
- 골격은 channel 주입식 → 게임/드라이버 없이 전 로직 테스트 가능
- screenshot은 현재 미사용(실구현서 공유메모리/핸들로 전달). ctx로 frame_id 전달
- 다음(M5): Acting (Combat/Buff/Potion/JunkSell/Charlie) — Humanizer 두번째 소비처

## 2026-06-01 — M5~M7 연속 진행 방침 (사용자 승인)
- 설계도 탄탄 → M5/M6/M7 연속 진행, 중간 승인 없이. 각 모듈 끝 커밋(롤백지점)
- 단위 TDD는 유지(부품 검증), 실기 통합테스트는 M7 후 한번에
- 자동업데이트: A updater.py + version.json(GitHub Release) 계승 확정. 본체 OK
  - 주의: 거탐 사이드카(.pyd 우구저작물) 배포·버전관리는 M6에서 설계

## 2026-06-01 — M5 착수 (Acting)
### 설계 (도면 5-2 전투결론: A 전반우위)
- combat.py: 게이지물약(A hp_ratio<threshold 방식) + 공격(skill_key, duration/count). Humanizer 경유
- buff.py: 일반/토글 버프 + 모션캔슬 대기(A hold0.8/sleep0.7)
- junk_sell.py: 인벤→상점 템플릿 시퀀스(A) + 탭색구분(C) + 보호목록(B). ※판매로직은 A junk_seller.py 이식+개선
- charlie.py: 찰리중사 교환 시퀀스(C, 구매제외). NPC키→대화→아래15회→키시퀀스, Humanizer+지터
### 서브태스크
- M5-1 Combat(물약+공격) / M5-2 Buff / M5-3 Charlie교환 / M5-4 커밋
- ※ JunkSell은 기존 A junk_seller.py가 동작중이라 M5에선 인터페이스 정리만, 실이식은 M6 통합시

## 2026-06-01 — M5 완료 (Acting)
### 구현됨 (core/acting/)
- combat.py: Combat + PotionRule. 게이지비율 물약(A방식, hp_ratio<threshold, HP/MP독립, 쿨다운) + attack(duration/count). Humanizer 경유
- buff.py: BuffManager + Buff. 주기버프, hold0.8(A 캔슬방지), 키없음=비활성
- charlie.py: CharlieExchange. 교환시퀀스(NPC→NPC→down15→NPC→left→NPC→NPC), repeat=보유//200, 구매제외(사용자지정). Humanizer 경유
### 검증: tests 77 passed 누계 (M1~M5)
### 결정
- JunkSell은 기존 A junk_seller.py가 동작중 → M5 신규구현 생략, M6 통합시 이식+C탭색/B보호목록 보강
- charlie 실교환로직 dis 깊이추적 대신 UI확정 명세로 구현(request_scanner는 파티/교환거절 다른기능 확인)
- 다음(M6): Orchestrator — 이벤트큐 소비+우선순위 상태머신, 모든 모듈 조립, 사이드카 기동, 공유위치 결선

## 2026-06-01 — M6 착수 (Orchestrator)
### 역할 (도면 5-3/5-4)
- 이벤트큐 소비 → 우선순위 판단 → 행동 디스패치 (god-loop 대체, 얇게)
- 상태머신: HUNTING / SAFETY(거탐·방지몹 대응) / SELLING / 우선순위 거탐>방지몹>판매>사냥
- 공유 위치상태: CharScanner char_pos 이벤트 → shared pos → BlockRunner pos_fn 결선
- 안전이벤트시 행동 일괄 pause(Humanizer key_up) → 처리 → 재개
### 설계 핵심
- Orchestrator는 '조율'만. 실제 일은 각 모듈(Nav/Acting/Solver)이. god-loop처럼 로직 안 가짐
- 이벤트 핸들러 등록식(type→handler). 새 이벤트타입=핸들러 1개 추가(콘센트)
### 서브태스크
- M6-1 SharedState(위치/HP/MP 공유) / M6-2 Orchestrator 이벤트루프+우선순위 / M6-3 안전대응(pause/resume) / M6-4 커밋

## 2026-06-01 — M6 완료 (Orchestrator 조율코어)
### 구현됨 (core/orchestrator/)
- shared_state.py: SharedState — 락보호 위치/HP/MP 공유, position_age(노후감지). 스캐너쓰기↔행동읽기 폐루프 매개
- orchestrator.py: Orchestrator — 이벤트큐 1배치 소비, _PRIORITY 우선순위정렬(거탐/방지몹=0 최우선), 안전이벤트→safety모드+on_pause, clear_safety→hunting+on_resume. 핸들러 등록식(on(type,fn))
### 검증: tests 88 passed 누계 (M1~M6: shared5/orch6 + 기존77)
### 핵심: god-loop 대체 입증
- Orchestrator는 로직 없음, 위임만. 우선순위(안전>사냥) 자동. 새 이벤트=핸들러1개(콘센트)
- test_priority_safety_over_normal: 같은배치 사냥+거탐 → 거탐 먼저
### M6 잔여 (실기 통합단계로 이연)
- 실제 모듈 결선(스캐너 start→큐→orch→Nav/Acting 호출)은 화면캡처/게임 의존 → M7 후 실기 통합테스트시
- 사이드카 프로세스 기동(MmapChannel) 동일
- JunkSell A 이식도 이때
### 다음(M7): UI 6카테고리 + DESIGN.md(Linear) 적용. 마지막 모듈

## 2026-06-01 — M7 착수 (UI 6카테고리 셸 + DESIGN.md)
### 사용자 결정: 신규 UI 스켈레톤 + DESIGN.md. 기존 A ui/ 병존(점진이행)
### DESIGN.md(Linear) 토큰
- canvas #010102, surface-1 #0f1011, surface-2 #141516, hairline #23252a
- ink #f7f8f8, ink-subtle #8a8f98, primary(라벤더) #5e6ad2, primary-hover #828fff
- 폰트: Linear Display(=SF Pro Display 폴백), 음수 트래킹. 액센트는 포커스링/CTA만(장식X)
### 설계 (위치 core_ui/ — 기존 ui/ 와 분리)
- theme.py: 토큰 상수 + build_qss() Linear 스타일시트 생성
- shell.py: MainShell — 좌측 6카테고리 내비 + 중앙 스택 + 좌하단 시작/정지 + 우측 로그도크 (도면 4단계 골조)
- 6카테고리 페이지는 플레이스홀더(실연결은 실기 통합단계)
### 테스트: 위젯 생성/구조(QApplication offscreen). 렌더링 육안은 실기
### 서브태스크: M7-1 theme(QSS) / M7-2 MainShell 구조 / M7-3 커밋

## 2026-06-01 — M7 완료 (UI 6카테고리 셸 + DESIGN.md)
### 구현됨 (core_ui/)
- theme.py: DESIGN.md(Linear) 토큰 1:1(canvas#010102/primary#5e6ad2/surface#0f1011/hairline#23252a) + build_qss()
- shell.py: MainShell — 좌측6내비(라벤더 좌보더 선택표시)+중앙스택+좌하단 시작/정지(라벤더CTA)+우측 로그도크. 6카테고리 페이지(플레이스홀더)
### 검증: tests 96 passed 누계 (M1~M7: theme3/shell5 + 기존88)
### 육안검증: offscreen 렌더→PNG. 레이아웃·near-black·라벤더액센트·로그도크 전부 도면4단계 골조 일치 확인(한글□는 offscreen폰트, 실기정상)
### 결정: 기존 ui/(A 10탭) 병존. 6카테고리 페이지 실내용은 실기 통합단계에서 채움
### ★ 7개 모듈 단위구현 완료. 다음은 실기 통합테스트(실제 게임 결선)

## 2026-06-01 — M8 착수 (런타임 결선 BotRuntime)
### 목표: 7모듈을 실제로 묶어 한 틱이 도는 파이프라인. 게임없이 Fake(가짜 캡처/백엔드)로 검증
### 설계 (core/runtime.py)
- BotRuntime: 조립 책임. 의존성 주입(screen_capture, input_backend, config)
  - Humanizer(backend) / CharScanner+AntiMobScanner(capture) → 이벤트큐
  - Orchestrator(큐, on_pause=행동정지, on_resume) + 핸들러 결선
  - BlockRunner(humanizer, pos_fn=state.get_position) / Combat / Buff
  - SolverRegistry(PlanetV2Engine)
- tick(): 스캐너 1회 수동 펌프(테스트) or 스레드(실기). orch.process_pending → 모드별 행동
  - hunting: 현재구역 순찰(BlockRunner) + 공격/버프
  - safety: 거탐 풀이(registry.solve) → clear_safety
- start()/stop(): 스캐너 스레드 + 메인루프
### 검증: Fake capture(노란블록 위치) + RecordingBackend → 위치갱신·이동·거탐대응 한틱 확인
### 이게 실기 테스트의 골격. 실기는 Fake자리에 실제 screen/interception 주입만

## 2026-06-01 — M8 완료 (런타임 결선 BotRuntime)
### 구현됨 (core/runtime.py)
- BotRuntime: 7모듈 조립. 의존성 주입(screen_capture/input_backend/sidecar_channel)
  - Humanizer ← backend / CharScanner+AntiMobScanner → event_queue
  - Orchestrator(큐, on_pause=방향키해제) + BlockRunner(pos_fn=state.get_position) + Combat + Buff
  - SolverRegistry(PlanetV2Engine, 같은 사이드카 채널)
- pump_scanners_once(테스트)/start_scanners(실기 스레드)
- hunting_tick: 순찰이동+공격+버프 / safety_tick: registry.solve→성공시 clear_safety
### 검증: tests 100 passed 누계 (M1~M8). Fake capture(노란블록)+RecordingBackend로 위치흐름·사냥틱·거탐대응 한틱 검증
### 디버깅: safety 테스트 실패 → runtime과 가짜사이드카가 다른 채널 봄. channel 주입식으로 수정(2초 타임아웃도 해소)
### ★ 실기 통합 잔여 디테일 (다음 세션)
- lie/transparent 이벤트 → minigame_type "planet"/"lona" 매핑 (현재 runtime은 cfg.minigame_type 고정)
- config.json → RuntimeConfig 매핑 어댑터 (미니맵region/floors/route/buffs/antimob)
- MmapChannel 실구현 + 3.13 사이드카 프로세스 기동 + Planet_solver .pyd
- 실제 screen(mss)+InterceptionBackend 주입, start_scanners 스레드 메인루프
- JunkSell A 이식, UI 6페이지 실위젯, main.py 진입점 신구조 연결

## 2026-06-01 — M9 완료 (config 어댑터)
### 구현됨 (core/config_adapter.py)
- to_runtime_config(config.json dict) → RuntimeConfig
  - minimap → minimap_region(left/top/width/height)
  - recovery.hp_potion/mp_potion → PotionRule(threshold %→비율, cooldown)
  - attack.normal_buffs/toggle_buffs → Buff(활성+키 있는것만)
  - zones → Floor(Y범위), floor_hunt.route → Block
  - attack.key → attack_key
### 검증: tests 107 passed 누계 (M1~M9). 실제 config.json 스모크 통과
### E2E 스모크: 실제 config → 어댑터 → BotRuntime 조립 성공
  (minimap 13/136/256×104, floors1, buffs3, ctrl, hp=pgup0.65/mp=pgdn)
### ★ 순수코드로 가능한 결선 전부 완료. 남은건 100% 실기:
  - MmapChannel + 3.13 사이드카 + Planet v2 .pyd (실바이너리)
  - 실 mss캡처 + InterceptionBackend 주입 + start_scanners 메인루프 (실드라이버/게임)
  - lie/transparent→planet/lona 이벤트매핑, UI 6페이지 실위젯, main.py 진입점
  - JunkSell A이식, 실게임 사냥 검증

## 2026-06-01 — ★중요 방향전환: 거탐 = exe 통째 방식 (사용자 확인)
### 결정 배경
- 우구에게서 Planet v2를 "exe 통째로만" 받음. .pyd 단독/호출법은 못 받음
- → .pyd import 방식 폐기. 3.13 사이드카 불필요. Python 3.13 설치 불필요
### 새 방식: ExternalProcessEngine (B·C 실제 방식)
- Planet v2.exe(우구)를 본체가 옆에 띄워둠. exe가 자체적으로 화면보고 거탐 감지+풀이(독립)
- 본체는 거탐 감지시 "내 사냥만 일시정지→재개". exe와 직접 통신 안함(느슨)
- M4 MinigameSolver 인터페이스 뒤에 ExternalProcessEngine 끼움(콘센트 격리 그대로 작동)
  - can_handle("planet") / solve(): exe 살아있는지 확인 + 사냥 pause 유지하며 거탐화면 사라질때까지 대기
  - SidecarChannel/PlanetV2Engine(mmap)는 미사용으로 보존(나중 .pyd 받으면 부활 가능)
### 사용자 준비물 (간소화 최종)
1. Interception 드라이버: 하드키바인딩_꼭설치.bat + 재부팅 + pip install interception-python (진행중)
2. Planet v2.exe 경로 확보 (봇과 함께 둘 폴더)
3. 테스트계정+게임 1920x1080/100%/단일모니터
### 다음 세션 실기 작업
1. ExternalProcessEngine 구현(exe 기동/종료 관리 + 거탐화면 감지로 pause/resume)
2. 실 mss + InterceptionBackend 주입 BotRuntime
3. main.py 신구조 진입점 + UI 6페이지 결선
4. JunkSell A이식, 실게임 검증

## 2026-06-01 — ★중대 정정: 거탐 = ncnn 자체 재구현 (exe 옆에 띄우기 폐기)
### 게으른 후퇴 정정
- 직전 "exe 통째로만 받음 → exe 옆에 띄우기"는 잘못된 회피. 사용자 질책 정당
- 우리는 이미 Planet_solver.exe에서 .pyd+모델+글루 전부 추출해둠. 원래계획(자체구현) 유효
### dis로 확정한 거탐 정체 (core/detector.pyc)
- ncnn YOLO (HyungYolo 클래스, Vulkan GPU). 투명도형을 신경망으로 감지
- 모델: assets/hyung_m1.param + m1_a~d.bin(4개 앙상블) + hyung_m2.param/.bin
  - m2 = 4클래스(convsigmoid 0=4), m1 = 1클래스(0=1) 앙상블
  - YOLOv8 anchor-free DFL 헤드: REG_MAX=16, IMGSZ=320, 출력노드 "out2", 입력 "in0"
- 전처리: _letterbox(패딩114) → ncnn.Mat.from_pixels(BGR2RGB) → substract_mean_normalize(인자없음=0~255 그대로?) → extract
- _decode: DFL softmax 박스회귀 + argmax 클래스 + 중심오프셋0.5, stride 그리드
- _nms: IoU NMS, 1e-09 0나눔방지
### ★ secure_loader 발견 (왜 exe 그대로는 안되나)
- core/secure_loader.pyc: fetch_secure_code(hwid,session_token)로 우구서버서 AESGCM 암호코드 받아 exec 주입
- 디버거감지(_is_debugger_attached) 있음. 핵심 일부가 서버의존
- → BUT 거탐 추론 자체는 detector.py(ncnn)에 다 있음. secure_loader는 macro(사냥)쪽 보호. 거탐 추론은 우회가능
### 결정: ncnn 모델로 자체 거탐 재구현 (사용자 지정)
- 모델 복사 완료: models/transparent/ (hyung_m1.param+a~d.bin, hyung_m2.param+bin, ~30MB)
- ncnn pip 설치 완료 (1.0.20260526)
- detector dis 보관: tools/_decompiled_planet/ (참조용)
### M10 구현
- core/minigame/transparent_yolo.py: HyungYolo 재현(ncnn Net, letterbox/decode/nms)
- core/minigame/self_transparent_engine.py: MinigameSolver 구현 → registry 등록(planet 대체)
- 검증: 실제 모델 로드 + 더미입력 추론 self-test (detector.py가 하던 그 self-test)

## 2026-06-01 — M10 완료 (자체 거탐 엔진 — ncnn 재현)
### 구현됨 (core/minigame/)
- transparent_yolo.py: HyungYolo(ncnn) + M1Ensemble 재현. detector.py dis 명세대로
  - letterbox(패딩114)→Mat.from_pixels(BGR2RGB)→substract_mean_normalize([],[1/255]*3)→extract("out2")
  - out2 실제 shape (10,10,68)=단일헤드 stride32. DFL디코드(REG_MAX16,softmax) + sigmoid분류 + NMS + 경계클램프
  - detect_center(): 최고점수 도형 중심 (커서 추적용)
- self_transparent_engine.py: SelfTransparentEngine(MinigameSolver). can_handle(planet/transparent)
  - solve(): board_capture_fn으로 게임판→도형추적→move_cursor_fn(주입식,입력계층경유). 8프레임 연속미검출=완료
### 검증: tests 111 passed 누계 (M1~M10). ★실모델 로드+추론 18~23ms 입증(secure_loader 우회)
### read-errors 디버깅
- 첫 추론 score 9.77(raw)/박스 음수 → out2 실shape (10,10,68) 확인 → transpose오류+sigmoid누락 발견 → 수정
- 단일헤드(멀티스케일 아님) 확정. 추측 아닌 실텐서 확인
### ★ 모델 배포 (중요)
- models/transparent/ (hyung_m1.param+a~d.bin, hyung_m2.param+bin, ~30MB) = .gitignore 제외
- 설치 파일(Inno Setup)에 동봉 필요. build.bat add-data 또는 installer.iss Files 섹션에 추가
- 이건 우구 학습 가중치 → 재배포 권리는 사용자가 "확보됨" 확인한 범위
### 거탐 결론 확정
- secure_loader(서버 AESGCM 코드주입)는 macro(사냥)쪽 보호. 거탐 추론은 detector.py ncnn에 전부 → 자체구현 성공
- PlanetV2Engine(사이드카/서버의존) 폐기, SelfTransparentEngine 채택. 3.13 사이드카 불필요
- registry 등록은 실기 결선시(BotRuntime에 capture/move 주입). 비올레타도 동일 패턴 추가

## 2026-06-01 — 거탐 런타임 결선 + 모델 동봉
### BotRuntime 거탐 교체
- runtime.py: PlanetV2Engine(서버의존) → SelfTransparentEngine(자체 ncnn) 등록
- RuntimeConfig에 transparent_models_dir/board_region/transparent_use_gpu 추가
- _capture_board(board_region 캡처) + _move_cursor(백엔드 move_to 있으면=실기 Interception 마우스)
- safety_tick: registry.solve("planet") → SelfTransparentEngine이 도형추적 풀이
### 빌드 설정 (build.bat)
- --add-data "models;models" (거탐 가중치 동봉) + --collect-all ncnn + --hidden-import ncnn
- --collect-submodules core / core_ui (신규 8패키지 자동포함: humanize/sensing/navigation/minigame/acting/orchestrator)
- installer.iss는 SourceDir\* recursesubdirs라 models 자동 포함(수정불요)
### 검증: tests 111 passed. runtime safety 테스트 Fake엔진으로 교체(실ncnn 30초→1.3초)
### 실기 잔여 (게임 필수)
- board_region(거탐 게임판 영역) 실측 설정, 실 mss+Interception 주입
- main.py 신구조 진입점, UI 6페이지 실위젯, JunkSell A이식
- ★실게임 거탐 정확도 검증 (자체모델이 실투명도형 잡는지) — 가장 중요

## 2026-06-01 — interception 백엔드 활성화 (실행 환경)
- 증상: 봇 실행시 "No module named 'interception'" → sendinput 폴백
- 원인: 패키지가 Python 3.13에 설치됨(그냥 pip install). 봇은 3.14로 실행 → 버전 불일치
- 해결: py -3.14 -m pip install interception-python → 3.14에 설치 → "드라이버 활성화 - 스텔스 입력" 확인
- ★규칙: 봇용 패키지는 반드시 `py -3.14 -m pip install` (그냥 pip는 PATH상 3.13에 깔릴 수 있음)
- 현재 select_backend() → interception 정상 선택됨

## 2026-06-01 — UI 6페이지 실위젯 (config 편집 폼)
### 구현됨 (core_ui/)
- widgets.py: _Field 베이스 + CheckField/TextField/IntField/ComboField. config 양방향 바인딩(로드+변경시 set+save 자동). DESIGN.md spacing 토큰
- pages.py: build_pages(config) → 6 카테고리 페이지. 각 config 실키 매핑(공격키/물약/거탐/방지몹/픽업 등). QScrollArea 래핑
- shell.py: MainShell(config=None) — config 있으면 build_pages, 없으면 플레이스홀더(테스트 호환)
- run_integrated.py: ConfigManager 로드 → shell(config=cm). build_runtime이 (rt,rc,cm) 반환
### 검증: tests 123 passed 누계. 실 config 렌더 확인 — 전투페이지 ctrl/350/HP65 pgup/MP50 pgdn 바인딩
### 동작: 페이지 입력 변경 → 즉시 config.json 저장(cm.set+save). 플레이스홀더→실설정폼 완성
### 남은 UI: 미니맵 영역 드래그 설정, 좌표 캡처 버튼 등 인터랙티브 위젯은 실기 연동 필요

## 2026-06-01 — 거탐 감지 스캐너 메인루프 결선
### 구현됨
- core/sensing/lie_scanner.py: LieScanner — 타이틀 템플릿 매칭(transparent_shape_title.png, 임계0.65)으로 거탐 출현 감지 → "lie" 이벤트. C MinigameWatcher 방식(_on_appear 1회발행 + _on_disappear 리셋 → 재출현시 재발행). 중복 방지
- runtime.py: RuntimeConfig에 lie_enabled/lie_title_template/lie_threshold/lie_detect_region 추가. lie_scanner 초기화(템플릿 파일 존재시). pump/start/stop_scanners 3곳 모두 포함
### 흐름 완성 (코드 입증)
- LieScanner "lie" → 이벤트큐 → Orchestrator(우선순위0, safety모드+on_pause로 사냥정지) → safety_tick(SelfTransparentEngine.solve 자체ncnn 풀이) → 성공시 clear_safety → 사냥재개
- 스모크: 실 타이틀 템플릿 화면에 심으니 감지→safety 전환 확인
### 검증: tests 127 passed 누계 (LieScanner +4)
### 실기 잔여 (게임 필수)
- lie_detect_region: 타이틀 탐색영역 좁히면 빠름(현재 전체화면). 실측 권장
- board_region: 거탐 게임판 영역(SelfTransparentEngine이 추적할). 실측 필수
- 실게임: 거탐 떴을때 실제 감지율 + 자체모델 풀이 정확도 검증

## 2026-06-01 — 순찰 완성 + JunkSell 이식
### 순찰 (core/navigation/patrol.py)
- Patrol+PatrolZone: 경계 도달시 방향전환 + 랜덤마진(A _update_direction/_pick_target 재현)
- runtime hunting_tick: 위치→patrol.next_direction→target_x로 walk블록+공격. config_adapter 첫zone 경계 매핑
### JunkSell (core/acting/junk_seller.py)
- JunkSeller: A core/junk_seller.sell_junk 위임(검증된 인벤→상점 템플릿판매) + B 보호목록(is_protected 부분매칭)
- config settings2.junk_sell.protect_items 에서 보호목록 로드
- runtime junk_config(ConfigManager 주입)시 활성. run_integrated에서 rc.junk_config=cm
- ※ A sell_junk는 기타탭 일괄판매라 아이템단위 필터없음 → 보호목록은 슬롯단위 판매확장시 적용(실기 확장지점)
### 검증: tests 137 passed 누계 (patrol5 + junk5)
### 남은 실기: 자동판매 주기타이머+안전지대이동(게임필요), 순찰 다층 확장(층간 이동)

## 2026-06-01 — 누락 기능 점검 + 이식 (펫/텔레그램/유저감지/자동응답)
### 점검 결과: 핵심 사냥루프는 완성됐으나 부가기능 6개 누락 발견 → 코드가능 5개 이식
### 이식됨
- core/acting/pet.py: PetFeeder 주기 펫먹이(Humanizer). hunting_tick에 pet.tick 결선
- core/notify/telegram.py: TelegramNotifier(requests POST, 예외삼킴=봇안멈춤). 토큰/chatid/enabled
- core/sensing/user_scanner.py: UserScanner HSV 빨강(타유저) 감지 + appear패턴
- runtime: pet/telegram/user_scanner 결선 + user_detected 핸들러(텔레그램알림+자동응답 enter)
- config_adapter: recovery.pet_food / settings1.lie_detector.tg_* / settings1.user_detected 매핑
### 검증: tests 149 passed. 실config 결선 스모크 — pet/telegram/junk/lie/patrol 전부 확인
### 남은 누락 (코드)
- 몬스터 감지(YOLO): A detector.py 래핑 필요 (현재 위치만, 몬스터 유무 판정 미연결)
- 채널변경(C ChannelFinder): 복잡+좌표 일부 실측 → 실기
- 자동응답 채팅 메시지 입력: enter만 누름, 실제 텍스트입력은 백엔드 문자열 입력 확장 필요
### 남은 실기: board_region/lie_detect_region 실측, 자동판매 안전지대이동, 다층순찰, 실게임 검증

## 2026-06-01 — ★ 코드 이식 완료 선언 (게임 실측 제외)
### 결정
- 몬스터 YOLO: A 학습데이터 없음 → 모델 생길때까지 보류(YOLO캡처 도구로 데이터 모은 뒤)
- 자동응답 텍스트입력: 진행 안 함(사용자 결정)
### → 게임 실측 제외, 코드로 옮길 수 있는 것 전부 완료
### 신구조 최종 (tests 149 passed, 커밋 60+)
- core/humanize (M1) / sensing (M2,거탐,유저) / navigation (M3,순찰) / minigame (M4,자체ncnn거탐)
  / acting (M5,전투/버프/펫/찰리/판매) / orchestrator (M6) / notify (텔레그램) / runtime (결선) / core_ui (UI6페이지)
- 진입점 run_integrated.py: ConfigManager→어댑터→실캡처/interception→BotRuntime→UI
- 동작: 시작→순찰사냥+공격+버프+펫+물약 / 거탐 감지→자체ncnn풀이→재개 / 유저감지→텔레그램+자동응답 / 잡템판매
### 남은 것 = 100% 게임 실측 (코드 아님)
- board_region(거탐 게임판) / lie_detect_region(타이틀 탐색영역) 실측
- 자동판매 안전지대 이동 좌표, 다층순찰 층간 밧줄 이동(좌표)
- 채널변경 ChannelFinder(C 복잡로직+좌표)
- 몬스터 YOLO 학습데이터 수집→모델
- 실게임 종합 검증(감지율/거탐정확도/안티밴)
### config.json은 로컬 설정값(UI편집/실행갱신) → 커밋 보류(이전 관례)

## 2026-06-01 — 사냥 영역(B training 방식) 추가 — 누락 정정
### 사용자 지적: A에 없다고 사냥영역 생략한 것 오류. B는 training 영역 안에서만 감지(전체화면 느림)
### B 설계 (config.ini 확정, Themida라 코드는 못보지만 키로 역추론)
- training_x/y/w/h: 사냥 영역 절대 사각형 (이 안에서만 닉네임/몬스터 감지)
- atk_x/y_min/max: 닉네임 위치 기준 공격 테두리(상대 오프셋)
- monster_accuracy: 영역내 템플릿 임계
### 이식
- config: attack.hunt_area{x,y,w,h} + atk_x/y_min/max + monster_accuracy
- pages.py 1번: 사냥영역 드래그버튼(미니맵 패턴) + hunt_area 필드 + atk테두리 필드 + 몬스터임계
- RuntimeConfig.hunt_area_region + adapter 매핑(w>0이면 region, 아니면 None=전체화면)
### 검증: tests 155 passed. 4버튼(미니맵/사냥영역/몬스터/닉네임) 렌더 확인
### TODO 실기: 몬스터 감지가 hunt_area_region 안에서만 동작하도록 결선(YOLO데이터 생기면). 닉네임주변 테두리 공격 로직

## 2026-06-02 — 몬스터 감지(OpenCV, B 메커니즘) 구현
### B 메커니즘 (Themida 봉인 → config 역추론으로 확정)
- training 영역 안만 캡처(전체화면 느림) → 닉네임 템플릿으로 본인 위치 → atk_x/y_min/max 오프셋 박스 → 박스 안 monster1~9 매칭(0.94) → 있으면 공격
- C는 몬스터 감지 없음(좌표스크립트 난사) 확인 / A detector.py matchTemplate가 유일 코드베이스
### 구현 (core/sensing/monster_vision.py)
- load_template(한글경로 fromfile+imdecode) / find_template_pos(닉네임 위치) / attack_box(닉네임+오프셋) / monsters_in_box(박스ROI만 다중템플릿 매칭, B방식)
- runtime: hunt_mode=="image"시 _monster_in_range()(닉네임→박스→몬스터) True일때만 공격. key모드는 무조건
- config_adapter: hunt_mode/name_template/monster_templates(단일+folder glob)/atk오프셋/monster_accuracy 매핑
### 검증: tests 161 passed (monster_vision 6). 스모크 — 닉네임박스 안 몬스터 감지→공격 동작
### read-errors: 스모크 첫 실패 → 닉네임 위에 몬스터 겹쳐그린 픽스처 문제(코드정상), 비겹침 재확인 통과
### 남은 실기: YOLO데이터 모이면 image모드를 YOLO로 교체가능(monster_vision은 OpenCV 폴백 유지). 실게임 닉네임/몬스터 템플릿 품질 검증

## 2026-06-02 — 동선 좌표 설정 = 블록 빌더 (BlockEditor)
### 버그 정정: coord_mode 콤보 off/on → absolute/relative (config 정의 일치. 좌표 기준점이지 on/off 아님)
### 좌표 동선의 실체: floor_hunt.route = Block 리스트(C routine_runner 스키마). M3 Block 그대로
### 구현 (core_ui/block_editor.py)
- BlockEditor: route 블록 리스트 편집. add_block(move/attack/ladder/jump)/remove_row/set_field/row_count
- 행별 타입 필드(move:target_x+walk/teleport, attack:skill_key, ladder:ladder_x) + ✕삭제. config 즉시저장
- Block.from_dict 검증 통과분만 저장
- _page에 extras 인자 추가 → 동선페이지에 BlockEditor 끼움
### 검증: tests 166 passed (block_editor 5). 렌더 — move/attack 블록 행 확인
### 좌표 동선 사용법: 동선·이동 탭 → 블록추가(이동/공격) → 각 X좌표·스킬키 입력 → 위→아래 순서로 BlockRunner 실행
### 남은: 블록 X좌표를 스크린샷/미니맵 클릭으로 찍는 픽커(현재 숫자입력), 블록 순서 드래그, 녹화

## 2026-06-02 — 블록 X좌표 미니맵 클릭 픽커
### 구현
- shot_selector.py: display_to_point(클릭 역배율 환산) + ClickPointPicker(이미지 클릭→점 좌표, 십자마커)
- block_editor.py: move 블록 행에 📍 버튼 → 미니맵 영역 캡처 → 클릭 → 미니맵 상대 X를 target_x로 set
### 검증: tests 169 passed (click_picker 3). 동선페이지 move블록 📍버튼 확인
### 좌표 동선 완전 사용법: 동선탭 → 이동블록 추가 → 📍 클릭 → 미니맵에서 목표지점 클릭 → X자동입력 → 공격블록 추가 → 반복

## 2026-06-02 — move 블록 구간 왕복(시작/끝/횟수) + 용어정정
### 용어 정정: 몬스터 감지는 "닉네임 박스"가 아니라 "공격 박스(atk 오프셋 범위)" 안에서. 닉네임은 위치기준일뿐
### move 블록 = 구간 왕복 (사용자 결정: 시작~끝 N회 왕복)
- Block에 start_x/end_x/sweeps 추가. start_x<end_x면 구간모드(아니면 단일 target_x 호환)
- BlockRunner.run_sweep(start,end,sweeps): 끝→시작 = 1왕복, sweeps회 반복. run_block이 구간모드 분기
- block_editor move행: 시작X(📍)+끝X(📍)+왕복횟수+walk/teleport. _pick_x(field) 일반화로 시작/끝 둘다 미니맵클릭
### 검증: tests 170 passed (block_runner sweep 추가). 렌더 — 시작/끝/왕복 필드 확인
### 좌표동선 사용: 이동블록→시작📍클릭→끝📍클릭→왕복횟수→공격블록. 위→아래 순서 실행

## 2026-06-02 — 공격범위 박스 픽커(기존범위 미리보기 + 드래그)
### 사용자 요청: 스크린샷 드래그로 공격범위 설정, 기존 범위 테두리 표시
### 구현
- shot_selector: rect_to_offsets/offsets_to_rect(앵커 기준 박스↔오프셋 환산) + _Canvas initial_rect(점선 미리보기)+anchor(십자) 표시 + Selector initial_rect/anchor 인자
- pages.py: _make_attack_box_picker — 전체캡처, 화면중앙=앵커, 기존 atk오프셋→미리보기박스, 드래그→rect_to_offsets→atk 4키 저장
- 공격범위 4필드 연결·인식→전투 탭 이동 + 🎯박스픽커 버튼(위치 직관화)
### 검증: tests 173 passed (attack_box_picker 3). 전투페이지 렌더 — 박스버튼+오프셋필드 확인
### 사용: 전투탭 🎯버튼 → 스샷에 기존범위 점선+중앙 앵커십자 → 캐릭 주변 공격범위 드래그 → atk오프셋 자동저장
### 주의: 앵커=화면중앙 가정(실제 캐릭은 닉네임 위치). 실기서 닉네임 기준과 차이나면 보정 필요

## 2026-06-02 — 공격범위 설정에 닉네임/몬스터 감지 오버레이
### 사용자 요청: 공격박스 설정시 기존범위+닉네임+인식몬스터 박스로 표시
### 구현
- monster_vision.monster_boxes_in_box: 박스 안 몬스터 위치 박스 리스트(원본좌표, 근접중복제거)
- shot_selector _Canvas.overlays: [(QRect,color,label)] 표시(드래그무관 항상). Selector overlays(원본→표시 환산)
- pages _make_attack_box_picker: 캡처후 닉네임 감지(골드박스, 그 위치를 실앵커로)+몬스터 감지(빨강박스) → overlays
  - 닉네임 감지되면 앵커=닉네임위치(화면중앙 아님). apply 오프셋도 name_anchor 기준
### 색: 기존범위=라벤더점선, 닉네임=골드#cba258, 몬스터=빨강#f04452, 앵커=초록십자
### 검증: tests 174 passed. 렌더 — 4종 표시 동시 확인
### 효과: 실제 닉네임/몬스터가 어디 잡히는지 보면서 공격범위 드래그 가능 (실측 정확도↑)

## 2026-06-02 — 사다리 블록 좌표 체크(시작/끝 미니맵 클릭)
### B 사다리 구조: ladder_sx(시작X)/sy(아래Y)/ty(위Y) 3좌표 — 어느 사다리를 어디서타 어디까지
### 구현
- block_editor _pick_x 일반화: y_field 주면 X+Y 둘다 set(사다리 발판 높이)
- 사다리 행: X + 아래Y + 📍시작(ladder_x+y_bot) + 위Y + 📍끝(ladder_x+y_top) + exit_side(내릴방향)
- 미니맵에서 사다리 아래발판 클릭(시작) → 위발판 클릭(끝) → x/y_bot/y_top 자동
### 검증: tests 174 passed. 렌더 — 사다리 X/아래Y/시작/위Y/끝/방향 확인
### 사다리 체크법: 동선탭 사다리블록 추가 → 📍시작(미니맵 아래발판 클릭) → 📍끝(위발판 클릭) → 방향
### 남은: BlockRunner ladder 실행(현재 move만, ladder는 pass) — 실기 결선시

## 2026-06-02 — move 구간 한번에 긋기(라인 드래그)
### 사용자 요청: 시작/끝 따로 찍기 귀찮음 → 한번 드래그로 시작→끝 직선 색상표시
### 구현
- shot_selector: LinePointPicker + _LineCanvas — 드래그로 시작(초록원)→끝(빨강원) 라벤더 직선. line_picked(sx,sy,ex,ey)
- block_editor: move 행 📍시작/📍끝 2버튼 → 📏구간긋기 1버튼. _pick_line: 미니맵 드래그→start_x/end_x 동시set(좌→우 정규화)
### 검증: tests 176 passed (line_picker 2). 라인 직선 렌더 + move 구간긋기 버튼 확인
### 사용: move블록 📏구간긋기 → 미니맵에서 시작점부터 끝점까지 한번 드래그 → 시작/끝 X 자동

## 2026-06-02 — UI/UX 3대 결함 수정 (오프스크린 렌더로 실증 진단)
### 진단 (실제 PNG 렌더 확인)
- **한글 전부 □(tofu)**: 번들 Inter 폰트에 한글 글리프 없음. Latin만 정상.
- **창 리사이즈 무반응 + 내용 잘림**: 사이드바/로그도크 setFixedWidth → 중앙만 찌부러져 내용이 도크 밑으로 깔림. 최소 창크기 없음.
- **블록 행 가로 오버플로우**: 한 행 위젯 과다 → 하단 가로 스크롤.
### 수정
- theme.py: 본문폰트 Inter→**Pretendard**(한글판 Inter, 사용자제공 1.3.9). 가변폰트 1개(PretendardVariable.ttf)만 동봉. 등록명 'Pretendard Variable'. setFamilies로 맑은고딕 폴백. 정적 Regular/SemiBold는 중복이라 제외.
- shell.py: 사이드바 208~248, 로그도크 220~380 (min/max), 창 최소 1024x640.
- block_editor.py: QVBoxLayout→**QListWidget InternalMove**로 드래그 재정렬. dict참조 아닌 인덱스API 유지(set_field/remove_row), 드롭시 _on_rows_moved가 UserRole 순서로 self._route 재구성. move_row(src,dst) 추가. ≡ 핸들 + 안내문. 위젯 폭 축소(1024폭서 teleport콤보까지 안잘림), 📏이모지 제거(오프스크린 비표시 → "긋기" 텍스트).
### 검증: tests 178 passed (block_editor move_row 2). 1024 최소폭 렌더 무잘림, 한글 정상, 드래그핸들 표시 확인.

## 2026-06-02 — 좌우 이동 키다운 유지 모델 (C _walk_to_x 대조 확인 후 결선)
### 검증
- C 원본 coord_script_runner.pyc dis: `_walk_to_x`=pyautogui.keyDown+time.sleep+_xy폴링+_release_move_keys(keyUp). **방향키 누른 채 유지→도착시 뗌**.
- 우리 기존 _exec_move: action="key" press(0.08s)를 틱당 반복 = **탭 연타(틀림)**. + Humanizer move_dir/hold는 key_down만이고 key_up 경로 없음(누수 버그).
### 사용자 확정 모델
좌우 이동키는 항상 keyDown 유지. 뗌은 ①방향 전환 ②제자리 공격 둘뿐. 그 외 유지.
### 구현
- Humanizer: 상태 `_held` + hold_dir(같은방향 no-op유지 / 다른방향 key_up후 key_down) / release_dir(멱등) / held_dir.
- BlockRunner._exec_move: tap→**hold_dir(direction)**. 도착해도 안 뗌(유지). 텔포 facing도 hold_dir로(누수 해결), space는 perform.
- runtime.hunting_tick: **이동 XOR 제자리공격**으로 재구성. attacking이면 release_dir→attack, 아니면 순찰 hold_dir. ※key모드는 항상 attacking→제자리 사냥(이동 안함). image모드는 박스내 몬스터 있을때만 멈춰 공격, 없으면 이동.
- _on_safety_pause: 직접 key_up→**release_dir**+up키 해제로 통일(상태 동기화).
### 검증: tests 183 passed (humanizer hold/release 3, block_runner hold 2, runtime attack-release 1).

## 2026-06-02 — 사다리 층이동 + 구간 3모드 (B/C 층이동 로직 대조)
### B/C 확인
- B(planet) maps_planet/*.py = **메모리 기반**(memory_reader, 정규화 y≤-0.77) → 헌법위반, 채택불가. 사다리개념만 동일(우+아래hold→탑승감지→↑).
- C(MapleHunter) routine_runner.pyc dis 분석 = **비전 기반**(_curr_x/_curr_y), 채택. 전체 사다리 로직 확보.
### C 사다리 메커니즘 (dis 확인)
- routine_blocks 스키마: ladder{x,y_top,y_bot,direction(up/down),exit_side}, move{x,method}, patrol{x_start,x_end,attack_hold_sec}.
- _do_ladder: 사다리X로 _do_move→좌표인식(실패스킵)→케이스. Case1 같은층(|y-y_bot|≤2)=↑등반, Case2 위층(y<y_top+2)=점프하강, Case3=점프잡기.
- _climb_ladder_up_until: keyDown('up')홀드→0.05s폴링 y≤y_top+2 도달(30s타임아웃).
- _jump_grab_ladder: keyDown(side)→|x-ladder_x|≤4(5s)→press(jump)→0.05→keyDown('up')→0.5매달림→keyUp(side)→y_top까지등반.
- _descend_ladder_jump: keyDown('down')1초+좌우+점프.
### 우리 구현
- Block: move에 mode(count/infinite/pass), ladder에 ladder_dir(up/down) 추가 + 검증.
- Humanizer: hold/release/release_all (좌우 외 ↑↓ 유지키, _held_keys set).
- BlockRunner: 상수 LADDER_X_TOL=4,Y_ARRIVE_TOL=2,SAME_LEVEL_TOL=2,HANG=0.5,DESCEND=1.0. sleep_fn/stop_fn/poll 주입. run_block ladder/jump 분기. move 모드: pass=_exec_move(end_x), infinite=run_sweep(infinite,stop_fn까지), count=sweeps. _do_ladder/_climb_up_until/_jump_grab/_descend_ladder/_do_jump 구현(전부 Humanizer hold/release 경유).
- BlockEditor: 2줄 카드(오버플로우 해결) — 윗줄 타입·모드/dir·옵션·✕, 아랫줄 좌표+긋기. move mode콤보, ladder dir콤보 노출.
### 검증: tests 188 passed (ladder 3, move모드 2). LadderWorld(키홀드 반응 물리)로 등반/점프잡기/하강 검증. 1024폭 무오버플로우 렌더 확인.
### 미결: 전체 route(사다리포함) 실행을 봇 루프에 결선 — 현재 hunting_tick은 patrol/route[0] max_steps=1 틱모델. 사다리는 블로킹(최대 35s)이라 floor-hunt route 전용 실행경로 필요(다음).

## 2026-06-02 — 고정 타이밍 랜덤화 (사람같은 움직임)
- 요청: 0.5초 매달림 등 고정 수치 전부 ±0.05 소수점 둘째자리 랜덤.
- Humanizer.jitter_sec(base, spread=0.05) = round(max(0, base+uniform(-spread,spread)), 2). sleep_jittered도 추가.
- BlockRunner._jsleep(base)=self._sleep(self._h.jitter_sec(base))로 모든 고정 sleep 교체: 매달림0.5/하강1.0/점프후0.05/하강후0.1/폴링0.05.
- perform 경로(공격·텔포·점프 키홀드)는 기존 hold_jitter(0.8~1.4배)로 이미 랜덤이라 유지.
- 검증: tests 190 passed (jitter 범위/음수방지/비고정 2개).

## 2026-06-02 — 지터를 크기 적응형으로
- 0.05 같은 작은 값에 ±0.05는 0~0.10으로 과함(0/2배 위험).
- jitter_sec: base≥0.1 → ±0.05 둘째자리 / base<0.1(폴링 0.05 등) → ±0.005 넷째자리.
- 검증: tests 191 (작은값 0.045~0.055 넷째자리 테스트 추가).

## 2026-06-02 — 밧줄 좌우 랜덤(grab_side)
- Block.grab_side: auto(가까운쪽=C방식)/left/right/random. ladder 검증 추가.
- Humanizer.random_side()=rng.choice(left/right).
- BlockRunner._grab_side(block,char_x)로 _jump_grab side 결정.
- BlockEditor 사다리 윗줄에 grab_side 콤보.
- 검증: tests 194 (random_side, grab_side fixed/random 3개).
