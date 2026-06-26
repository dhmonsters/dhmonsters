# 투명도형 퍼즐 Task 6 컨텍스트 노트

- `DetectionGate`는 퍼즐 팝업 또는 탐지 점수가 안정적으로 떠 있는지만 판단한다.
- 이 단계는 후보 생성, 후보 선택, 정체성 추적, 자동 입력을 전혀 다루지 않는다.
- 연속 hit가 `required_hits`에 도달하기 전에는 `DETECTION_PENDING`으로 두고, 도달한 순간 `PUZZLE_DETECTED`를 반환한다.
- 점수가 threshold 아래로 떨어지면 `DETECTION_NOISE`로 기록하고 hit count를 0으로 리셋한다.
- `planet_solver_noauth.py`의 팝업 감지 흐름은 운영 참고용이며, 새 구현은 순수 점수 게이트로 시작한다.
- RED 확인 결과는 `ModuleNotFoundError: No module named 'core.puzzle.detection'`였고, 기대한 실패였다.
- GREEN 확인은 번들 Python 직접 호출로 수행했다.
- Task 1부터 Task 6까지 수동 테스트를 함께 통과했고, `ast.parse` 문법 검사도 통과했다.
