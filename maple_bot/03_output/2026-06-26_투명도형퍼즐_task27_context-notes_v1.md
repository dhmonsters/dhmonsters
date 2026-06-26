# Task 27 맥락 노트

## 발견
- `puzzle.py --headless --replay` 실행이 세션 폴더 생성 단계에서 `PermissionError`로 중단됐다.
- 실패 지점은 추적 로직이 아니라 `SessionManager.start`의 날짜별 세션 폴더 생성이다.

## 결정
- 날짜별 세션 폴더 suffix를 ASCII인 `transparent_puzzle_sessions`로 고정한다.
- 산출물 내부의 trace, mp4, report 구조는 기존 이름을 유지한다.

## 진행 기록
- `test_session_manager_creates_output_paths`와 `test_session_manager_uses_ascii_safe_session_root`가 기존 suffix 때문에 실패하는 RED 상태를 확인했다.
- `SessionManager`의 날짜별 세션 폴더 suffix를 `transparent_puzzle_sessions`로 바꿨다.
- 관련 세션 테스트 3개가 통과했다.
- Codex sandbox의 workspace 쓰기 제한 때문에 실제 `_record_debug` replay는 임시 출력 루트로 검증했고, report 생성까지 성공했다.
- 전체 `test_puzzle_*.py` 경량 실행 결과 64개 테스트가 통과했다.
- `session.py`와 `test_puzzle_session.py` 문법 검사가 통과했다.
