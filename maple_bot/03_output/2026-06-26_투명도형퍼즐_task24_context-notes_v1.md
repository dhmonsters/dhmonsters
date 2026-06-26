# 투명도형퍼즐 Task 24 컨텍스트 노트

## 결정
- 실제 timeline 클릭 UI보다 먼저 frame 재동기화 메서드를 만든다.
- frame source, candidates, evidence, identity 중 하나라도 있으면 선택 가능한 frame으로 본다.
- 없는 frame을 선택하면 UI 상태를 바꾸지 않고 `False`를 반환한다.

## 이유
- Task 20부터 23까지 frame별 데이터를 저장했지만, 특정 frame으로 되돌아가는 계약은 아직 없다.
- 이 메서드가 생기면 다음 단계에서 timeline 클릭, 북마크, 오류 프레임 점프를 모두 같은 경로로 연결할 수 있다.

## 진행 기록
- `selected_frame_index`와 `select_timeline_frame(frame_index)`를 추가했다.
- 저장된 source, candidates, evidence, identity를 선택 frame 기준으로 CCTV 요약 라벨에 다시 적용한다.
- 저장된 identity는 우측 상태, confidence, hold, reason metric에도 다시 반영한다.
- 저장된 데이터가 없는 frame은 `False`를 반환하고 기존 선택 상태를 유지한다.
- `test_puzzle_*` 스모크 묶음 57개가 통과했다.
- `puzzle_console.py`와 `test_puzzle_console_smoke.py`의 `py_compile` 검증이 통과했다.
