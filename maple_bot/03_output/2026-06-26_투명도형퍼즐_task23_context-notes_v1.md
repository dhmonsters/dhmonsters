# 투명도형퍼즐 Task 23 컨텍스트 노트

## 결정
- evidence는 전체 표가 아니라 첫 evidence의 대표 점수만 CCTV 영역에 표시한다.
- 전체 evidence 목록은 `current_frame_evidence`에 저장해서 이후 상세 패널이나 overlay와 연결한다.
- 표시 점수는 `bg_score`, `motion_divergence`, `merge_likelihood`로 시작한다.

## 이유
- Task 20, 21, 22로 frame, 후보, identity가 CCTV 영역에 붙었다.
- evidence 요약을 추가하면 같은 프레임에서 “왜 이 후보가 살아남거나 밀렸는지”를 바로 확인할 수 있다.

## 진행 기록
- 중앙 CCTV 영역에 `puzzleCctvEvidenceSummary` 라벨을 추가했다.
- `EVIDENCE` 이벤트를 받으면 `current_frame_evidence[frame_index]`에 evidence 목록을 저장한다.
- evidence 요약은 frame, evidence 수, 첫 candidate_id, bg, motion, merge 점수를 표시한다.
- `test_puzzle_*` 스모크 묶음 55개가 통과했다.
- `puzzle_console.py`와 `test_puzzle_console_smoke.py`의 `py_compile` 검증이 통과했다.
