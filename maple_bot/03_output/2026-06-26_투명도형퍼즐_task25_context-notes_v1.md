# Task 25 맥락 노트

## 결정
- Task 24의 `select_timeline_frame`을 재사용한다.
- 새 기능은 solver 판단 로직이 아니라 저장된 trace frame을 되짚어보는 UI 탐색 기능으로 제한한다.
- 사용자가 frame 번호를 직접 입력하는 기능은 이번 범위에서 제외한다.

## 이유
- 현재 CCTV preview와 후보, evidence, identity summary는 frame 단위 복원 상태를 이미 들고 있다.
- 이전과 다음 이동은 기존 상태 복원 메서드를 호출하는 얇은 UI 계층으로 유지하는 편이 안전하다.
- trace 검증 자료를 빠르게 확인하는 것이 목적이므로 버튼 동작을 먼저 안정화한다.

## 진행 기록
- 신규 smoke test 3개를 먼저 추가했다.
- 실패 확인 결과 navigation 버튼이 아직 없는 AttributeError로 떨어져 테스트가 의도한 기능 부재를 잡았다.
- timeline 패널에 이전과 다음 버튼을 추가하고 저장된 frame state의 합집합을 정렬해 이동하도록 구현했다.
- 전체 `test_puzzle_*.py` 경량 실행 결과 60개 테스트가 통과했다.
- `puzzle_console.py`와 `test_puzzle_console_smoke.py` 문법 검사가 통과했다.
