# 투명도형퍼즐 Task 22 컨텍스트 노트

## 결정
- 실제 overlay drawing 전에 identity 상태를 CCTV 영역의 텍스트 요약으로 먼저 고정한다.
- 저장 단위는 frame index별 원본 payload로 둔다.
- point는 있으면 표시하고, candidate_id도 있으면 함께 표시한다.

## 이유
- Task 20과 Task 21로 frame preview와 후보 목록이 CCTV 영역에 붙었다.
- 여기에 identity 상태를 붙이면 같은 프레임에서 “무엇을 봤고, 어떤 후보를 어떻게 판단했는지”를 UI 한 곳에서 확인할 수 있다.

## 진행 기록
- 중앙 CCTV 영역에 `puzzleCctvIdentitySummary` 라벨을 추가했다.
- `IDENTITY_STATE` 이벤트를 받으면 `current_frame_identity[frame_index]`에 payload를 저장한다.
- identity 요약은 frame, state, confidence, candidate_id, point를 표시한다.
- `test_puzzle_*` 스모크 묶음 53개가 통과했다.
- `puzzle_console.py`와 `test_puzzle_console_smoke.py`의 `py_compile` 검증이 통과했다.
