# 투명도형 퍼즐 Task 9 컨텍스트 노트

- Task 9의 목적은 프레임별 정답 선택이 아니라 신분의 연속성을 보류하고 복원하는 상태 흐름을 코드로 고정하는 것이다.
- 초기 anchor가 있으면 `INIT_VISIBLE`로 시작하고, 가까운 후보가 이어지면 `TRACK_CONFIDENT`로 넘어간다.
- 후보가 갑자기 멀어지거나 `merge_likelihood`가 높으면 즉시 갈아타지 않고 `OCCLUSION_SUSPECTED`로 둔다.
- 후보가 없거나 애매한 구간은 `IDENTITY_HOLD`로 이전 위치와 후보 신분을 유지한다.
- 보류 중 가까운 후보가 낮은 병합 점수로 돌아오면 `REACQUIRE`를 한 번 반환한 뒤 다음 정상 프레임에서 `TRACK_CONFIDENT`로 복귀한다.
- 이 단계에서는 배경 정합, phase catalog, health guard를 직접 붙이지 않고 evidence 입력값만 사용한다.
- RED 확인 결과 `ModuleNotFoundError: No module named 'core.puzzle.identity'`로 기대한 실패가 발생했다.
- GREEN 확인 결과 Task 9 수동 테스트 6개가 통과했다.
- 후보 비용은 거리, 후보 score, target-like evidence, background-like evidence, merge likelihood만 사용한다.
- Task 1부터 Task 9까지 수동 테스트 29개가 통과했다.
- 새 evidence, identity, export, 테스트 파일에 대한 AST 파싱 5개가 통과했다.
