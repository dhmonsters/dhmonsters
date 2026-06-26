# Task 32 맥락 노트

## 결정
- 실전 첫 단계는 자동 입력 없이 라이브 화면 녹화만 연다.
- 캡처는 `mss`를 먼저 시도하고, 실패하면 `PIL.ImageGrab`으로 되돌린다.
- 테스트에서는 화면 캡처 대신 frame grabber를 주입한다.
- UI의 `화면 감시`는 라이브 녹화를 시작하고, F3는 녹화만 종료한다.
- CLI는 `--live-record`로 열고, 테스트용 종료 조건은 `--live-max-frames`로 둔다.

## 이유
- 먼저 시작부터 끝까지의 무손실 검증 영상을 얻어야 다음 솔버 판단을 비교할 수 있다.
- 실제 게임 조작과 분리하면 실전 리허설의 위험과 디버깅 범위가 작아진다.
- Codex 번들 실행 환경에서는 실제 화면 캡처가 `screen grab failed`로 막혔지만, 테스트에서는 frame grabber 주입으로 녹화 생명주기를 검증할 수 있다.

## 진행 기록
- 시작 시점에는 `화면 감시` 버튼이 placeholder 로그만 남겼다.
- 시작 시점에는 라이브 화면 캡처 기반 세션 녹화 runtime이 없었다.
- `LiveRecordingRuntime`을 추가해 `raw_cctv.mkv`, `board_crop.mkv`, `overlay.mkv`, `trace.jsonl`, `report.md`를 생성하게 했다.
- UI `화면 감시` 버튼은 라이브 녹화를 시작하고, 기존 `녹화 종료 F3` 버튼과 F3 키는 녹화 종료로 연결했다.
- CLI에 `--live-record`, `--live-max-frames`를 추가했다.
- 선택 테스트는 `passed=35 failed=0`으로 통과했다.
- 전체 `test_puzzle_*.py` 수동 러너는 `passed=80 failed=0`으로 통과했다.
- 문법 검사는 대상 파일 `py_compile` 통과, 공백 검사는 `git diff --check` 통과했다.
- 실제 `--live-record --live-max-frames 2` dry-run은 Codex 실행 환경에서 `screen capture failed (mss: No module named 'mss' | ImageGrab: screen grab failed)`로 실패했다. 실제 사용자 데스크톱에서는 같은 명령 또는 UI `화면 감시`로 최종 확인해야 한다.
