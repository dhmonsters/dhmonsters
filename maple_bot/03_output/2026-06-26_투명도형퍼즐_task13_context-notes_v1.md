# 투명도형 퍼즐 Task 13 컨텍스트 노트

- 이번 단계는 사용자가 고른 다음 진행 항목 중 `2. 실제 UI 연결`과 `3. 고정 ROI 연결`만 다룬다.
- UI 버튼은 아직 실시간 감시나 자동 입력이 아니라 replay runner를 호출하는 분석 도구 경로로 연결한다.
- 탐지 ROI는 기존 기본값 `settings1.lie_detector.region`의 `[1126, 297, 296, 130]`을 기준으로 둔다.
- 퍼즐 ROI는 기존 기본값 `settings1.transparent_shape.board_roi`의 `{x_ratio:0.286, y_ratio:0.183, w_ratio:0.428, h_ratio:0.575}`를 기준으로 둔다.
- replay 세션은 시작 시점의 detect ROI와 board ROI를 trace에 남긴다.
- RED는 `PuzzleConsoleWindow.__init__()`가 `replay_runner`를 받지 못하는 실패로 확인했다.
- `core.puzzle.defaults`에 고정 ROI 기본값과 trace payload 변환 함수를 분리했다.
- `PuzzleConsoleWindow`는 image sequence, video, JSONL replay 버튼을 replay runner에 연결한다.
- UI 오른쪽 분석 패널은 detect ROI와 board ROI 고정값을 표시한다.
- `run_headless_replay()`는 고정 detect ROI와 board ROI를 세션에 적용하고 `SESSION_START` payload에도 남긴다.
- Task 13 집중 테스트 8개를 통과했다.
- Task 1부터 Task 13까지 수동 회귀 테스트 41개를 통과했다.
- 변경 파일 AST 파싱 6개를 통과했다.
