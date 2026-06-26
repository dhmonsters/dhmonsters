# Task 31 맥락 노트

## 결정
- 프로그램 전체 종료 후에도 녹화가 계속되는 별도 프로세스는 만들지 않는다.
- 프로그램이 살아있는 동안에는 솔버 중지와 녹화 종료를 분리한다.
- 녹화 종료는 `F3` 또는 `녹화 종료 F3` 버튼으로 명시적으로 수행한다.
- 영상 파일은 `raw_cctv.mkv`, `board_crop.mkv`, `overlay.mkv`로 저장한다.
- 기본 코덱은 OpenCV에서 확인 가능한 `FFV1`로 둔다.

## 이유
- 사용자가 솔버를 멈추고 직접 푸는 구간도 시작부터 끝까지 검증 영상에 남아야 한다.
- `mp4v`는 손실 압축이라 추후 프레임 단위 검증 자료로는 약하다.
- `FFV1 + MKV`는 파일 크기는 커지지만 디버깅 자료로 더 적합하다.

## 진행 기록
- 시작 시점에는 `SessionRecorder`가 `mp4v`와 `.mp4` 경로를 사용했다.
- 시작 시점에는 녹화 종료 버튼과 F3 진입점이 없었다.
- 이 환경의 OpenCV 의존성에서 `FFV1 + MKV` writer가 열리는 것을 확인했다.
- `RecordingController`를 추가해 `stop_solver`가 recorder를 닫지 않고, `stop_recording`만 recorder를 닫게 했다.
- `SessionManager`의 영상 산출물 경로를 `raw_cctv.mkv`, `board_crop.mkv`, `overlay.mkv`로 바꿨다.
- `SessionRecorder` 기본 fourcc를 `FFV1`로 바꿨다.
- `PuzzleConsoleWindow`에 `녹화 종료 F3` 버튼과 F3 keyPress 진입점을 추가했다.
- 신규 테스트 묶음 7개가 통과했다.
- 수동 테스트 러너 기준 `test_puzzle_*.py` 전체 75개가 통과했다.
- 실제 `puzzle.py --transparent-test --output-root <temp> --max-frames 2` 실행에서 `raw_cctv.mkv`, `board_crop.mkv`, `overlay.mkv`가 생성됐다.
- 변경 파일 문법 검사를 통과했다.
