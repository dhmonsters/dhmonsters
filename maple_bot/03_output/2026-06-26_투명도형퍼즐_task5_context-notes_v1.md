# 투명도형 퍼즐 Task 5 컨텍스트 노트

- `planet_solver_noauth.py`의 녹화 흐름은 참고하되, 새 구현은 세션 녹화와 스냅샷 저장만 담당한다.
- 첫 프레임의 source, board, overlay 크기로 writer를 열고 이후 크기 변경은 실패로 처리한다.
- 크기 변경 실패는 UI에서 조용히 묻히지 않도록 `ROI_INVALID` trace 이벤트를 남긴다.
- snapshot 파일명은 추후 검증 자료 정렬을 위해 `000003_start.png`처럼 frame index를 6자리로 고정한다.
- 이번 단계에는 UI, 후보 판별, 자동 입력 로직을 넣지 않는다.
- RED 확인 결과는 `ModuleNotFoundError: No module named 'core.puzzle.recorder'`였고, 기대한 실패였다.
- GREEN 확인은 번들 Python과 `.codex_pydeps` 기반 OpenCV writer로 수행했다.
- Task 1부터 Task 5까지 수동 테스트를 함께 통과했고, `ast.parse` 문법 검사도 통과했다.
