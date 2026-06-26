# 투명도형 퍼즐 Task 3 컨텍스트 노트

- `planet_solver_noauth.py`의 JSONL 기록 흐름은 참고하되, 새 trace는 `core/puzzle/trace.py`에 독립시킨다.
- trace는 세션 단위 산출물이며 `PuzzleSession.trace_path`에 한 줄 JSON으로 누적한다.
- `tg_token`, `telegram_token`, `chat_id`는 최상위와 중첩 payload 모두에서 `***`로 마스킹한다.
- 이번 단계는 기록 기반을 만드는 것이며 후보 판별이나 자동 입력 로직은 넣지 않는다.
- RED 확인 결과는 `ModuleNotFoundError: No module named 'core.puzzle.trace'`였고, 기대한 실패였다.
- GREEN 확인은 번들 Python 직접 호출로 수행했고, Task 1, Task 2, Task 3 수동 테스트를 함께 통과했다.
- `TraceLogger`는 파일 핸들을 오래 붙잡지 않고 이벤트마다 append로 열어 UI/리플레이 중단 상황에서도 기록 손실을 줄인다.
