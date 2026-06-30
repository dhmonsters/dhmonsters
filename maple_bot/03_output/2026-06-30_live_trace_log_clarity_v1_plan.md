# 2026-06-30 live trace log clarity v1 plan

## Goal

라이브 테스트 중 로그만 봐도 퍼즐 감지, 후보 검출, 시간축 선택, 마우스 이동 여부를 즉시 판단할 수 있게 한다.

## Scope

- UI 로그 표시만 변경한다.
- ROI, CCTV 캡처, solver 판단 로직은 변경하지 않는다.
- 라이브 세션의 `trace.jsonl`을 따라 읽어 UI 로그에 반영한다.

## Verification

- `tests.test_puzzle_console_f1_hotkey`로 F1/F2/F3와 live trace 로그 반영을 확인한다.
- puzzle live 관련 테스트 묶음으로 기존 동작이 깨지지 않았는지 확인한다.
