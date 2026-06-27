# Task 33 맥락 노트

## 결정
- 실전 라이브 테스트의 다음 단계는 자동 풀이가 아니라 화면 캡처 사전점검이다.
- 사전점검은 화면 1장을 잡아 PNG와 Markdown 리포트를 남긴다.
- 실패해도 리포트는 남겨 다음 세션에서 원인을 반복 조사하지 않게 한다.

## 이유
- Task32에서 녹화 런타임은 준비됐지만 Codex 실행 환경에서는 실제 화면 캡처가 실패했다.
- 사용자 PC에서 실전 진입 전에 캡처 가능 여부를 먼저 확인해야 녹화 실패와 게임 상황을 분리할 수 있다.

## 진행 기록
- 시작 시점에는 `--live-capture-check`가 없었다.
- 시작 시점에는 UI에서 화면 캡처만 따로 점검하는 버튼이 없었다.
- `core.puzzle.capture_preflight`를 추가해 성공 시 `capture_check.png`, 실패와 성공 공통으로 `capture_check.md`를 남기게 했다.
- CLI `--live-capture-check`는 성공 시 0, 실패 시 2를 반환한다.
- UI 입력 패널에 `캡처 점검` 버튼을 추가했다.
- Codex 실행 환경에서 실제 사전점검은 실패 코드 2와 함께 `capture_check.md`를 정상 생성했다.
- 전체 `test_puzzle_*.py` 수동 러너는 최종 검증에서 `passed=85 failed=0`으로 통과했다.
- 대상 파일 `py_compile`과 `git diff --check`가 통과했다.
