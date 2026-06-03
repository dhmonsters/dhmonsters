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
