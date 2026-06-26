# 투명도형퍼즐 Task 16 컨텍스트 노트

- Task 15에서 replay trace에 `CANDIDATES`, `EVIDENCE`, `IDENTITY_STATE` 이벤트가 기록되기 시작했다.
- Task 16은 trace를 화면에 보여주는 UI 계약을 추가하는 단계다.
- 실제 trace 파일 tailing이나 실시간 감시는 아직 연결하지 않고, 한 이벤트를 받아 화면 상태를 갱신하는 순수 메서드부터 만든다.
- 이번 단계는 자동 입력이나 보호 장치 우회 동작을 만들지 않는다.
- 새 테스트는 구현 전 `PuzzleConsoleWindow`에 `apply_trace_event`가 없어서 실패하는 것을 확인했다.
- `SESSION_START`는 세션 라벨을 갱신한다.
- `CANDIDATES`는 후보 수 metric을 갱신한다.
- `IDENTITY_STATE`는 상태, confidence, hold, reason, timeline frame을 갱신한다.
- UI smoke 테스트 6개, 전체 puzzle 테스트 43개, `ui/puzzle_console.py`와 `tests/test_puzzle_console_smoke.py` 문법 확인을 통과했다.
- 번들 Python에는 `pytest`가 없어 직접 함수 호출 방식으로 검증했다.
