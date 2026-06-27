# 투명도형 퍼즐 F1 F2 F3 런타임 작업 메모

## 2026-06-27

- 사용자가 F1, F2, F3 역할을 명확히 지정했다.
- 현재 구현은 F1이 곧장 `LiveRecordingRuntime.start()`를 호출해 녹화를 시작한다.
- 원하는 흐름은 F1이 솔버 감시 ON이고, 퍼즐 도형 감지 후 녹화 시작이다.
- 기존 `RecordingController`는 이미 솔버 정지와 녹화 종료를 분리한다.
- 이번 작업은 기존 녹화 파일 구조를 유지하고 앞단 감시 게이트를 추가하는 방식으로 진행한다.
- `LivePuzzleActivationDetector`를 추가했다. 기본은 shape YOLO를 먼저 쓰고, 실패하면 보드 ROI의 흰 도형 픽셀로 감시 활성화를 판단한다.
- `LiveRecordingRuntime.start(initial_frame=...)`를 지원해 감지된 프레임을 녹화 첫 프레임으로 남긴다.
- F1은 `SOLVER_ON` 상태로 들어가고, F2는 감시 중이면 감시 스레드를 끄며 녹화 중이면 솔버만 정지한다.
- F3은 녹화 종료로 유지한다.
- 감지 후 녹화가 시작되면 UI가 라이브 상태를 폴링해 `RECORDING`과 세션 경로를 표시하도록 보강했다.
- 최종 검증으로 `tests.test_puzzle_console_f1_hotkey`, `tests.test_puzzle_live_watch`, 문법 확인, headless 프리플라이트가 통과했다.
