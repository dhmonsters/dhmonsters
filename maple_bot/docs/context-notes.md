# 컨텍스트 노트 (작업 맥락·결정 기록)

> 세션이 끊겨도 다음 세션이 결정을 다시 추론하지 않도록 누적 기록한다.

---

## 2026-06-04 — 매크로방지몹 "파훼" 기능 (보류)

**무엇:** 자동경비 / 루루모 / 리치 = 모두 매크로방지몹. 감지 후 동작은
"공격 중지 → 그 맵의 정해진 위치 NPC에게 가서 (말걸기 / 기타템 주기 /
기본공격 N대) → 방지몹 공격 가능 버프 수령 → 돌아와 방지몹 처치 → 사냥 복귀".

**조사 결과 (어디서도 코드를 가져올 수 없음):**
- **B(플래닛/카카오톡)**: 파훼 로직 보유하나 **Themida 보호**라 코드·문자열 모두 암호화 → 추출 불가.
  config.ini에서 읽힌 건 감지 토글뿐: `auto_guard_enabled` / `lulumo_enabled` / `rich_enabled`.
  위험대응 수단(참고): `cc_enabled/cc_interval/cc_slot`(채널변경), `telegram_enabled`(알림), `stop_tele`.
  ⚠️ B config에 이전 사용자 텔레그램 토큰/챗ID 노출돼 있었음 — **사용 안 함**.
- **C(MapleHunter, 디컴파일됨)**: 방지몹 NPC-버프 파훼 로직 **없음**. 위험대응은
  `MinigameWatcher`(캡차 감지→일시정지→외부 솔버 풀이→재개)뿐.
  단, **틀은 재사용 가능** — `routine_blocks`(move/teleport/attack(count·interval)/patrol/ladder/jump/wait)
  + `coord_script_runner`. "NPC좌표 이동→공격N대→대기"는 이 블록으로 표현 가능.
  **없는 동작 2개**: "NPC 대화(키)" · "기타템 주기" → 새 블록타입으로 추가 필요.
- **A**: 미확인(요청대로 스킵).

**보류 결정:** 사용자가 "파훼 기능 나중에 구현" 지시 → 미착수.
재개 시 설계: AntiMobScanner(감지·다중템플릿, 이미 있음) → 공격중지(release_all) →
몹별 파훼 블록 시퀀스(이동→대화/기타템/공격→대기) → 종료판정 → 복귀.
필요한 사용자 입력(데이터): 몹별 NPC 위치(고정x좌표 vs 이미지인식), 상호작용 종류·값, 종료판정 방식.

---

## 2026-06-04 — OCR 리더 (완료)

**무엇:** 고정 위치(ROI) 한국어 텍스트(기타창/확인창 등)를 글자로 인식.
det(박스탐색)는 기존 파이프라인이 담당, 여기선 **rec-only**(우리 `assets/ocr/rec.onnx` + 한글 dict).

**구현:** `core/sensing/ocr_reader.py` — `read_text(scene, roi)`, `read_lines(...)`.
지연로딩 싱글톤 RapidOCR(`use_text_det=False, use_angle_cls=False`).

**핵심 함정:** 설치된 `rapidocr_onnxruntime` 버전은 `rec_keys_path` kwarg를
인식기에 전달하지 못함(인식기는 `keys_path` 또는 모델의 `character` 메타데이터를 읽음).
→ **dict를 rec.onnx에 `character` 메타로 임베딩**해 자족화(`tools/embed_ocr_dict.py`, 빌드 시 onnx 필요·런타임 불필요).
※ `assets/ocr/`·`tools/`는 .gitignore 대상 → 코드만 커밋, 모델/스크립트는 로컬 유지.

**검증:** 렌더한 한글(확인/취소/기타) 실제 인식 통합테스트 포함. 전체 316 passed.

---

## 2026-06-04 — ⚠️ 사용자가 실제로 돌리는 경로 (중요·재확인)

**사용자는 `run_integrated.py`(신규 통합 런타임 = `BotRuntime` + `core_ui/shell.py`)를 돌린다.**
구형 `main.py`(→`MainWindow`→`BotLoop`+`ui/`)가 **아니다.**

- 판별법: 로그에 "✓ 캐릭터 감지"(`core/sensing/char_scanner.py`), "사다리 등반/점프잡기"
  (`core/navigation/block_runner.py`)가 보이면 신규 런타임이다.
- **버그 수정 시 신규 경로를 고쳐야 한다**: 동선=`navigation/block_runner`, 공격·물약=`acting/combat`,
  감지=`sensing/*`, UI/로그=`core_ui/shell.py`, 조립=`runtime.py`+`config_adapter`+`run_integrated`.
- 구형(`bot_loop.py`/`potion_manager.py`/`ui/tab_main.py`)은 이 경로에서 **안 쓰임**(헷갈리지 말 것).
  (이번에 물약 진단/로그스크롤을 구형에 먼저 고쳤다가 헛수고함.)

**이번 수정 3건(모두 신규 경로):**
1. 사다리 허위 '등반 완료' — `block_runner._climb_loop` 시작 가드(시작 y ≤ y_top+여유면 등반 아님).
   ※ 로그 "y 74→80"처럼 y_top이 시작보다 아래면 사용자 route의 ladder Y가 잘못된 것일 수 있음.
2. 물약 미작동 — `BotRuntime`이 HP/MP를 안 읽고 `Combat.check_potions`를 호출 안 했음.
   `hp_mp_reader`(A `Detector` 재사용) 주입 + `hunting_tick`에서 호출로 복구.
3. 로그 자동스크롤 — `core_ui/shell.py` 로그뷰 `verticalScrollBar().rangeChanged`→맨아래.

전체 324 passed.

## 2026-07-29 실행 경로 정리
- 공식 진입점은 run_integrated.py 하나로 고정한다.
- main.py는 구형 ui.main_window를 열지 않고 run_integrated.py로 위임한다.
- core_ui가 최신 UI이며 ui/main_window.py와 ui/tab_*.py는 구형 UI로 취급한다.
- 배포 시 core_ui만 교체하지 말고 core 의존 파일까지 같은 시점으로 포함한다.

