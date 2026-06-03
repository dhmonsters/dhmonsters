# 블록 루트 기반 층별 사냥 완성 설계

**작성일:** 2026-06-03
**상태:** 승인됨(설계) → 구현 계획 단계

## 배경 / 문제

통합 빌드에서 "층별 사냥"이 옛 A/B/C의 "층 Y범위 입력 → 자동 순환" 방식에서
"블록을 직접 그려 경로를 짜는" 방식으로 바뀌었으나, 다음 결함이 남음.

1. **루트 모드가 이동만 하고 공격을 안 함** — `run_route`는 이동/사다리만 실행하고,
   `hunting_tick`은 루트 모드에서 공격을 건너뜀. `run_block`에 attack 처리도 없음.
   → 루트를 켜도 돌아다니기만 하고 때리지 않음.
2. **복귀(낙하 시 층 복귀) 미작동** — `_recover_if_needed`/`build_graph`/`expected_floor`
   코드는 있으나 층 Y범위(`zones`) 입력 UI가 없어 `FloorJudge`에 데이터가 안 들어감.
3. **죽은 토글** — "층별 사냥 사용"(`floor_hunt.enabled`)이 `RuntimeConfig`에 매핑되지
   않아 아무 동작도 안 함. "커스텀 루트 모드"(`route_mode`)만 실제 동작.

## 목표

블록 루트 방식을 유지하면서 아래 사냥 패턴을 모두 설정 가능하게 한다.

- **왕복형**: 1-2-3-4-3-2-1
- **구간 반복형**: 3-4-3-4 (떨어지면 구간으로 복귀)
- **회수형**: 2 사냥 → 1 회수 → 2 사냥 → 3-4 회수 (사냥/통과 혼합)

## 핵심 결정

- 공격 방식: **이미지 탐지** — 사냥영역 몬스터 인식, 공격범위에 들어오면 스킬 사용
  (기존 `_monster_in_range` B 메커니즘 재사용)
- 복귀용 층 정보: **루트 블록에서 자동 추출** (별도 입력 UI 없음)
- 공격 로직 위치: **접근 A — 메인 루프(`hunting_tick`) 재사용** (새 스레드 없음)

## 설계

### 1. 패턴은 코드 추가 없음 (블록 구성으로 표현)

세 패턴은 블록 순서 + 블록 모드로 표현된다. 신규 코드 불필요, 사용 규약이다.

| 패턴 | 블록 구성 |
|------|-----------|
| 왕복 1-2-3-4-3-2-1 | 올라가는 블록 + 내려가는 블록 나열. 루프 시 반복 |
| 구간 3-4-3-4 | 3·4층 이동/사다리 블록만. 루프 + 낙하 복귀 |
| 회수형 | 사냥할 층 move = `infinite`/`count`, 들러 줍는 층 = `pass` |

`run_route`는 이미 블록을 순서대로 돌고 FloorHuntRunner가 반복 실행하므로 루프는 보장됨.
(자동 역순 왕복 같은 편의기능은 YAGNI — 이번 범위 제외.)

### 2. 루트 중 공격 (접근 A)

**데이터 흐름**

```
FloorHuntRunner(thread) → block_runner.run_route(blocks)
   각 블록 실행 직전: on_segment(block) 훅 호출
        runtime: self._route_hunt_active = (block.type=="move" and block.mode != "pass")

controller._loop(main) → hunting_tick()  (루트 모드)
   buffs/pet/pickup tick (기존)
   if self._route_hunt_active and attack_key:
       if self._monster_in_range():       # 이미지 탐지(B)
           self.combat.attack(attack_key, mode="duration")
```

**구성요소**

- `BlockRunner`: 생성자에 `on_segment: Callable[[Block], None] | None = None` 추가.
  `run_block` 진입 시(복구 판정 후) `if self._on_segment: self._on_segment(block)` 호출.
  순수 이동 모듈 유지를 위해 detector/combat 의존은 넣지 않음(플래그만 통지).
- `BotRuntime`: `self._route_hunt_active = False` 필드.
  `_on_route_segment(block)` 메서드로 플래그 갱신 → BlockRunner에 주입.
  `hunting_tick`의 루트 분기에서 플래그가 True일 때만 이미지 탐지+공격 수행
  (헌트모드 설정과 무관하게 루트 공격은 이미지 방식 고정).
- pass(회수) 구간은 플래그 False → 공격 안 함. 자동 줍기 타이머는 계속 동작.

### 3. 복귀용 층 자동 추출

- 신규 순수함수 `floors_from_route(route: list[dict]) -> list[Floor]`
  (신규 파일 `core/navigation/floor_extract.py`).
  - move 블록의 Y(`pos_y`, 미니맵 px)를 근접 클러스터링(밴드 폭 임계)으로 층 그룹화.
  - 각 층 = 정렬된 Y 밴드 → `Floor(name=f"F{i}", y_min, y_max)`.
  - 사다리(`y_top`/`y_bot`)는 층 연결 — `build_graph`가 이미 route ladder로 그래프 간선 생성.
- `BotRuntime.__init__`: `config.floors`가 비어 있고 route가 있으면
  `floors = floors_from_route(route)`로 대체 → `FloorJudge(floors)` + `build_graph(...)`.
  명시적 zones가 있으면 그대로 우선.
- 좌표계: char_scanner의 캐릭터 Y와 블록 `pos_y` 모두 미니맵 px 동일 공간 → 정합.
- 복구 동작(`_recover_if_needed`)은 기존 그대로. 현재 층≠기대 층이면 최단경로 사다리로 복귀.

### 4. 죽은 토글 정리

- "층별 사냥 사용"(`floor_hunt.enabled`) 체크박스 **제거** (pages.py page2).
- "커스텀 루트 모드"(`route_mode`) 단일 토글 유지.
- config의 `floor_hunt.enabled` 키는 읽지 않으므로 잔존해도 무해(마이그레이션 불필요).

## 테스트

- `test_floor_extract`: 블록 Y 클러스터링 → 층 밴드/개수, 같은 층 묶임, 사다리 연결.
- `test_route_hunt_active`: `_on_route_segment`가 pass→False, infinite/count/move→True 세팅.
- `test_hunting_tick_route_attack`: 루트 모드에서 플래그 True+몬스터 감지 시 combat.attack
  호출, pass 구간(플래그 False)에선 미호출 (fake combat/detector).
- 회귀: 기존 251 테스트 통과 유지.

## 비범위(YAGNI)

- 자동 역순 왕복 토글, 층 Y범위 수동 입력 UI, 회수 전용 별도 동작(줍기는 기존 자동 줍기로 충분).

## 트레이드오프

공격이 메인 루프 틱(30ms)에 묶여 이동과 완전 동기는 아니지만, 실사용엔 충분하고
모듈 경계(이동=block_runner / 공격=runtime)가 깨끗하게 유지된다.
