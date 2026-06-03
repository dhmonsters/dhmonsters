# A/B/C 대비 "얇게 재구현/미포팅" 감사 체크리스트 (2026-06-03)

목적: 통합 런타임(block_runner/runtime/sensing/acting)이 검증된 A/B/C 소스
(`bot_loop.py`, `map_navigator.py`, `minimap_reader.py`, `detector.py`)의 로직을
제대로 포팅했는지 점검. 새로 만들기 전에 여기부터 본다.

범례: ✅ 포팅/동등 · ⚠️ 얇게 재구현(차이·누락, 포팅 권장) · ❌ 미구현/미연결

---

## 0. 참조 소스 상태 — 왜 A만 비교 대상인가

추출본 분석 결과, **코드 포팅이 가능한 건 A뿐**이다.

| 프로그램 | 형태 | 포팅 |
|---|---|---|
| **A** (DHMONSTERS, 우리 `core/`) | 파이썬 소스 | ✅ 유일하게 소스 포팅 가능 (이 감사의 기준) |
| **B** (Planet) | 앱 전체 `__mypyc.cp313-win_amd64.pyd`(mypyc 네이티브) + Themida + 메모리 기반 | ❌ 디컴파일 불가 + 메모리(헌법 위반) |
| **C** (MapleHunter) | 핵심 `core/hunting.pyd`·`memory_reader_external.pyd` 등 컴파일 .pyd + 메모리 기반 | ❌ 알고리즘 디컴파일 불가 |

- C에서 **읽을 수 있는 건 루트 데이터뿐**: `coord_scripts/*.json`, `maps/*.pyc`.
  스키마 = `{skill_key, actions:[{type:attack|move, x, direction, move_type, attack_mode, attack_value}]}`
  → 우리 `Block` 모델과 **이미 호환**(데이터 모델은 C를 잘 따름). 알고리즘은 참고 불가.
- 결론: 아래 항목들은 모두 **A 소스** 기준 포팅 점검이다.

---

## 1. 감지 (Sensing)

- [ ] ⚠️ **캐릭터 위치 검출** — A/B/C `minimap_reader.get_character_pos`는 `char_r/g/b ± tolerance`
      **RGB 정확색 매칭**(per-channel diff ≤ tolerance, 최소 4px). 우리 `find_char_in_hsv`는
      **HSV 변환**(얇은 재구현). **검출 불일치/실패의 유력 원인** → RGB-tolerance 방식으로 포팅 권장.
- [x] ✅ 미니맵 영역 캡처 — 스레드별 mss 포팅 완료(스캐너 스레드 캡처 정상).
- [x] ✅ 몬스터 감지(닉네임→atk박스→박스내 매칭) — `monster_vision`로 동등 포팅.
- [x] ✅ 거탐(lie) 감지 → 안전모드 전환 + 알림(소리+텔레그램) 통합.
- [x] ✅ 투명도형 감지/자동풀이 — registry/transparent 엔진.
- [x] ✅ 유저 감지(빨강 픽셀) — user_scanner.
- [ ] ❌ **레벨업/사망 감지** — A `_check_level_up`/`_check_dead` 미포팅(레벨정지는 의도적 제거, 사망감지는 빠짐).
- [ ] ❌ **맵 이탈 감지** — A `_check_map_exit` 미포팅. 영역 픽커만 있고 런타임 소비자 없음.

## 2. 이동 (Movement)

- [ ] ⚠️ **방향키 keepalive** — A `_direction_keepalive_loop`가 40ms마다 key_down 재전송
      (게임이 유지키를 놓쳐도 계속 이동). 우리는 `hold_dir` 1회뿐 → **장시간 이동 중 끊김 가능**. 포팅 권장.
- [x] ✅ 사다리 등반 — 방금 A/B/C 방식 포팅(접근점 점프+재시도+진척감지).
- [ ] ⚠️ 구역 왕복 + 랜덤마진 전환 — A `map_navigator._update_direction`/`_pick_*_target`.
      우리 `patrol.py`+`run_sweep`에 일부 있으나 통합 경로(route 모드)에선 미사용. 정리/통일 필요.
- [ ] ⚠️ 구역 이탈 복귀 — A는 가장 가까운 구역으로 X복귀. 우리는 층 그래프(map_graph) 복귀로 **개념이 다름**. 의도 확인 필요.
- [ ] ❌ **위치 미감지 폴백** — A는 3초간 위치 못 잡으면 방향 강제전환 + 진단로그. 우리는 멈춤판정만.
- [ ] ⚠️ 하강(다운+점프 뛰어내림) — `_descend_ladder` 있음. A 로직(`_descend_ladder_jump`)과 세부 비교 미완.
- [ ] ❌ **다운점프/포탈 이동** — 블록 타입 없음(이동 move_type=teleport만 있음). 포탈/다운점프 미구현.

## 3. 전투 (Combat)

- [ ] ⚠️ **공격 루프** — A `_attack_loop`(별도 스레드 스팸). 우리는 메인틱에서 1회/틱 공격(이미지 게이팅). 동작 모델 다름 — 연사/쿨다운 비교 필요.
- [x] ✅ 포션(HP/MP 임계+쿨다운) — `combat.check_potions` 동등.
- [x] ✅ 버프(주기) — `buff.py`.
- [x] ✅ 펫먹이/줍기(주기) — `PetFeeder`.
- [ ] ❌ **점프 후 공격**(jump_before_attack) — A 옵션 미포팅.

## 4. 안전·안티밴

- [x] ✅ 거탐 알림 통합(소리+텔레그램, 단일 토글).
- [x] ✅ 인간화(고정수치 랜덤화) — Humanizer.
- [ ] ⚠️ **안티밴(방지몹) 대응동작** — A `_handle_anti_mob`(클릭/아이템사용/기본)·`_move_to_minimap_x`.
      우리 `antimob_scanner`는 **감지(Event)만** 함. 감지 후 대응동작 미포팅(확인 필요).

## 5. 자동화·운영

- [ ] ⚠️ **자동판매** — A `_auto_sell_worker`. 우리 `JunkSeller` 인스턴스만 만들고 **루프 미연결**.
- [ ] ❌ **마을 귀환**(물약부족/조건) — A `_check_town_scroll_trigger`/`_use_town_scroll` 미포팅.
- [ ] ❌ **예약 종료** — 미구현.
- [x] ✅ 텔레그램 알림.

---

## 우선순위 제안 (영향 큰 순)

1. ⚠️ **캐릭터 검출 RGB-tolerance 포팅** — 지금 사다리/이동 불안정의 잠재 근원. (감지 1)
2. ⚠️ **방향키 keepalive** — 장거리 이동 끊김 방지. (이동 1)
3. ⚠️ **위치 미감지 폴백 + 구역 이탈 복귀 정합** — 멈춤 시 자가복구. (이동)
4. ⚠️ **안티밴 대응동작 포팅** — 감지만 하고 대응 없음. (안전 4)
5. ⚠️ **자동판매 루프 연결**, ❌ 마을귀환/사망·맵이탈 감지 — 운영 안정성.
6. ❌ 다운점프/포탈, 점프후공격 — 동선/전투 확장(필요 시).
