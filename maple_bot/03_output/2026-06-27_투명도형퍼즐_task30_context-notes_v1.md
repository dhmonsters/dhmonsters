# Task 30 맥락 노트

## 결정
- UI의 `녹화 폴더` 버튼은 마지막으로 생성된 `report.md`의 부모 폴더를 연다.
- 테스트 안정성을 위해 실제 OS 파일 탐색기 호출은 `folder_opener` 콜백으로 감싼다.
- 아직 replay를 실행하지 않았거나 폴더가 없으면 버튼은 로그만 남기고 실패 상태로 만들지 않는다.

## 이유
- 사용자는 `puzzle.py` 또는 기본 테스트 버튼으로 테스트한 뒤 바로 산출물을 확인해야 한다.
- 리포트, trace, mp4가 한 세션 폴더에 모이므로 report parent가 가장 정확한 진입점이다.
- 실제 폴더 열기는 UI 편의 기능이고 추적 로직과 분리되어야 한다.

## 진행 기록
- 시작 시점에는 `녹화 폴더` 버튼이 placeholder 로그만 남겼다.
- replay 후 `녹화 폴더` 버튼이 마지막 `report.md`의 부모 폴더를 여는 실패 테스트를 추가했다.
- replay 전에는 opener를 호출하지 않고 로그만 남기는 실패 테스트를 추가했다.
- `PuzzleConsoleWindow`에 `folder_opener`, `last_report_path`, `last_session_dir`를 추가했다.
- 신규 테스트 2개가 통과했다.
- 수동 테스트 러너 기준 `test_puzzle_*.py` 전체 70개가 통과했다.
- 실제 `puzzle.py --transparent-test --output-root <temp> --max-frames 2` 실행이 리포트를 생성했다.
- `puzzle.py`, `ui/puzzle_console.py`, `tests/test_puzzle_console_smoke.py` 문법 검사를 통과했다.
