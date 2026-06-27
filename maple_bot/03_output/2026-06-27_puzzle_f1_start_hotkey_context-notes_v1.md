# 투명도형 퍼즐 F1 시작 단축키 작업 메모

## 2026-06-27

- 사용자가 인게임에서 F1 시작이 되지 않는다고 보고했다.
- 스크린샷에는 `recording stop skipped`가 남아 있었다. 이는 F3 종료 입력은 들어왔지만 활성 녹화가 없었다는 뜻이다.
- 코드 확인 결과 `PuzzleConsoleWindow.keyPressEvent`는 F3만 처리하고 있었다.
- 코드 확인 결과 `puzzle._attach_puzzle_hotkeys`도 전역 F3만 등록하고 있었다.
- 이번 작업은 F1 시작 연결만 좁게 수정하고 기존 F3 종료 흐름은 유지한다.
- `start_watch_input`이 이미 버튼 시작 동작의 단일 입구라서 F1도 이 메서드를 그대로 호출하게 했다.
- 전역 단축키는 `puzzle_start_recording` 이름으로 F1을 추가하고 기존 F3 종료 등록은 유지했다.
- `tests.test_puzzle_console_f1_hotkey`는 처음 실행에서 F1 미연결로 실패했고, 연결 후 통과했다.
- 번들 Python의 바이트코드 생성은 기존 `__pycache__` 권한 때문에 막혔으므로 `-B`와 직접 compile 방식으로 문법을 확인했다.
- headless 프리플라이트는 `.codex_pydeps`를 `PYTHONPATH`에 추가하고 임시 출력 경로를 사용해 통과했다.
