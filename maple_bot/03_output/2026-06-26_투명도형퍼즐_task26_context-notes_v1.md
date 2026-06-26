# Task 26 맥락 노트

## 결정
- timeline 클릭 UI 전에 이동 가능한 frame 목록을 먼저 보이게 한다.
- frame 목록은 source, candidates, evidence, identity 중 하나라도 저장된 frame의 합집합으로 계산한다.
- 선택 상태는 별도 상태를 만들지 않고 기존 `selected_frame_index`를 표시한다.

## 이유
- Task 25에서 이전과 다음 이동은 가능해졌지만, 사용자는 이동 가능한 frame 범위를 알 수 없다.
- 클릭 가능한 timeline으로 가기 전에 frame 목록 표시를 먼저 고정하면 UI 검증이 쉬워진다.

## 진행 기록
- 신규 smoke test 3개를 먼저 추가했다.
- RED 확인 결과 `timeline_frames_label` 부재 AttributeError로 실패했고, 의도한 기능 부재를 잡았다.
- `puzzleTimelineFrames` 라벨을 추가했다.
- frame source, candidates, evidence, identity 저장 시 frame 목록 요약을 갱신하도록 연결했다.
- `select_timeline_frame` 성공 시 selected frame 표시도 함께 갱신한다.
- 전체 `test_puzzle_*.py` 경량 실행 결과 63개 테스트가 통과했다.
- `puzzle_console.py`와 `test_puzzle_console_smoke.py` 문법 검사가 통과했다.
