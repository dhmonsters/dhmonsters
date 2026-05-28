# 작업 목록 (Todo)

> 세션 시작 시 이 파일을 먼저 읽을 것. 완료 항목은 ✅로 표시.

---

## 완료된 작업

### YOLO 거짓말탐지기 파이프라인 안정화
- ✅ `_check_lie_detector` — YOLO 재감지 실패 시 `return False` 제거, 알림·해제 흐름 유지
- ✅ `_solve_lie_detector_manual()` 및 `has_manual` 분기 삭제 (dead code 제거)
- ✅ `board_roi` 비율 좌표 수정 (`x_ratio, y_ratio, w_ratio, h_ratio`)
- ✅ `run_follow_loop()` 동작 확인 — 투명도형 찾기 통합 버전 = standalone 동일 알고리즘
- ✅ 텔레그램 알림 미발송 원인 확인 및 수정 (재감지 실패로 인한 early return)

### 설정1 탭 UI 정리
- ✅ 거짓말탐지기 그룹에서 템플릿 캡처 행 제거
- ✅ 거짓말탐지기 그룹에서 영역 설정 행 제거
- ✅ 거짓말탐지기 그룹에서 영역 단축키 행 제거
- ✅ 투명도형 그룹 YOLO 모델 경로 입력 제거
- ✅ YOLO 모델 경로 단일 입력으로 통합 (거짓말탐지기 + 투명도형 공용)
- ✅ 관련 dead code 메서드 9개 삭제

### 투명 도형 마우스 추적 수정
- ✅ `board_roi` 쓰레기 좌표(X=32737) → YOLO bbox 기반 `dynamic_roi` 자동 계산
- ✅ 알람(`winsound.Beep`)을 async 스레드로 분리 — 추적 시작 1.2초 지연 제거
- ✅ `run_follow_loop()` 최초 도형 감지 로그 추가, 캡처 예외 처리 추가

### 로그 / 진단 개선
- ✅ 메인 탭 로그 필터 체크박스 소급 적용 (버퍼 + `_rerender_log`)
- ✅ 거짓말탐지기 YOLO 진단 로그 — 스레드 시작·모델 로드 성공/실패·감지 이벤트 UI 표시

### 잡템 판매 좌표 창 이동 독립
- ✅ `_save_junk_coord()` — 절대 좌표와 함께 `key_ratio` 비율 병행 저장
- ✅ `_resolve_coords()` — 비율 우선, 없으면 절대 폴백
- ✅ 스크롤 최하단 오매칭 해결 (템플릿 재등록)

### UI 하드코딩 (설정 잠금)
- ✅ `tab_settings2.py` — 잡템 판매 ①②③ 섹션 캡처/지정/✕ 버튼 전부 제거, `locked=True` 파라미터 추가
- ✅ `tab_settings2.py` — 기타템 판매 활성화 체크박스 `setEnabled(False)`
- ✅ `tab_settings1.py` — 투명 도형 찾기 설정(타이틀 템플릿·게임판·높이·디버그) UI 제거, 읽기 전용 라벨만 표시

### 문서
- ✅ `docs/workflow.md` — 워크플로우 설계 가이드 작성
- ✅ `tasks/lessons.md` — 교훈 기록 초기 작성

---

## 진행 중 / 대기 중

### 자동 판매 주기 + 안전지대 이동 (`plan: compiled-fluttering-yao.md`)

계획 파일: `C:\Users\PC\.claude\plans\compiled-fluttering-yao.md`

UI 부분 (tab_settings2.py)은 이미 구현 완료. bot_loop.py 구현 남음.

- [ ] `core/bot_loop.py` — `__init__`에 `_auto_sell_active`, `_auto_sell_selling`, `_auto_sell_last` 플래그 추가
- [ ] `core/bot_loop.py` — `_run()` 메인 루프 최상단에 자동 판매 타이머·이동·판매 블록 추가
- [ ] `core/bot_loop.py` — `_auto_sell_worker()` 메서드 추가
- [ ] 검증: 봇 실행 → 설정 주기 후 로그에 "자동 판매: 안전지대로 이동 시작" 확인
- [ ] 검증: 안전지대 도착 후 "자동 판매 완료 — 사냥 재개" + 사냥 재개 확인

---

## 백로그 (우선순위 낮음)

- [ ] YOLO11 몬스터 감지 — 몬스터용 별도 모델 학습 필요 (현재 거짓말탐지기 모델만 존재)
- [ ] `transparent_shape_standalone.py` — `board_roi.json` 대신 `config.json` 직접 읽도록 통일
- [ ] 거짓말탐지기 YOLO 감지 후 `matched_pos`가 `None`일 때 슬라이딩 퍼즐 해제 시 경고 로그 개선
- [ ] `config.json`에 남아 있는 `settings1.lie_detector.region` 키 정리 (UI 제거됨, 레거시 값)
