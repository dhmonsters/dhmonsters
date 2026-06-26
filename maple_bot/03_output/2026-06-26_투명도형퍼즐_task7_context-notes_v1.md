# 투명도형 퍼즐 Task 7 컨텍스트 노트

- `CandidateProvider`는 후보를 고르지 않고, 기존 검출 행을 표준 `Candidate` 객체로 바꾼다.
- 좌표는 항상 board frame 기준으로 보존한다. 이 단계에서는 ROI 변환, 화면 좌표 변환, 마우스 좌표 변환을 하지 않는다.
- 지원 source 이름은 `yolo`, `raw`, `live_family`, `replay`로 제한한다.
- 드롭된 후보는 `last_debug["dropped"]`에 `row_index`, `reason`, `score`로 남긴다.
- `planet_solver_noauth.py`의 YOLO/검출 흐름은 source provider로 감싸는 참고 자료일 뿐, 이 단계에 직접 결합하지 않는다.
- RED 확인 결과는 `ModuleNotFoundError: No module named 'core.puzzle.candidates'`였고, 기대한 실패였다.
- GREEN 확인은 번들 Python 직접 호출로 수행했다.
- Task 1부터 Task 7까지 수동 테스트를 함께 통과했고, `ast.parse` 문법 검사도 통과했다.
