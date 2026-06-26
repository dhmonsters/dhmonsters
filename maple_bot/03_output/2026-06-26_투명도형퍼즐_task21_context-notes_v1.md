# 투명도형퍼즐 Task 21 컨텍스트 노트

## 결정
- 실제 overlay drawing은 아직 하지 않는다.
- 후보 목록을 먼저 UI 상태에 저장해서 이후 QPainter 또는 overlay frame 생성기가 사용할 수 있는 상태를 만든다.
- 요약 텍스트는 frame 번호, 후보 수, 첫 후보 bbox만 보여준다.

## 이유
- Task 20에서 프레임 이미지는 보이기 시작했지만, 후보 정보는 우측 metric과 timeline에만 흩어져 있다.
- CCTV 영역에 후보 요약을 붙이면 같은 프레임에서 무엇을 보고 있는지 즉시 확인할 수 있다.

## 진행 기록
- 중앙 CCTV 영역에 `puzzleCctvCandidateSummary` 라벨을 추가했다.
- `CANDIDATES` 이벤트를 받으면 `current_frame_candidates[frame_index]`에 후보 목록을 저장한다.
- 후보 요약은 frame 번호, 후보 수, 첫 후보 bbox를 표시한다.
- `test_puzzle_*` 스모크 묶음 51개가 통과했다.
- `puzzle_console.py`와 `test_puzzle_console_smoke.py`의 `py_compile` 검증이 통과했다.
