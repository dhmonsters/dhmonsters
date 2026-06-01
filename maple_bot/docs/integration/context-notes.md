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
