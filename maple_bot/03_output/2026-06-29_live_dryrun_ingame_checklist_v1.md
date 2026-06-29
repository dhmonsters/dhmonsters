# 2026-06-29 인게임 첫 dry-run 체크리스트

## 실행 전

1. `python puzzle.py --live-dry-run`으로 실행한다.
2. 오른쪽 설정에서 `마우스 제어`가 꺼져 있는지 확인한다.
3. CCTV가 게임 클라이언트와 퍼즐 ROI를 실시간으로 보여주는지 확인한다.

## 실행 중

1. F1을 눌러 solver 감시를 켠다.
2. 퍼즐이 뜨기 전에는 녹화가 시작되지 않아야 한다.
3. 퍼즐이 감지되면 녹화가 시작되고, CCTV에 추적 표시가 갱신되어야 한다.
4. 실패하거나 이상하면 F2로 solver만 멈춘다.
5. 전체 자료가 충분히 쌓인 뒤 F3으로 녹화를 종료한다.

## 종료 후 확인

1. 세션 폴더의 `trace.jsonl`이 존재해야 한다.
2. `live_session_review.md`가 존재해야 한다.
3. dry-run이면 `mouse_enabled: false`여야 한다.
4. dry-run이면 `mouse_moved: 0`이어야 한다.
5. `temporal_selector_events`가 1 이상이어야 한다.
6. `Selector Families`에 선택 family가 찍혀야 한다.

## 판정

- 위 항목을 만족하면 다음 단계는 마우스 제어 ON 소규모 테스트다.
- 퍼즐 감지가 0이면 감지 ROI 또는 캡처 경로 문제다.
- 후보가 0이면 noauth detector 또는 보드 crop 문제다.
- selector event가 0이면 라이브 후보가 selector까지 전달되지 않은 문제다.
- mouse_moved가 1 이상이면 dry-run 안전장치 문제다.
