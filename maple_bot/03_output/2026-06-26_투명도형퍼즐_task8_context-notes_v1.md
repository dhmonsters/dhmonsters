# 투명도형 퍼즐 Task 8 컨텍스트 노트

- Task 8의 목적은 정답 후보를 고르는 것이 아니라 후보마다 동일한 형식의 판단 근거를 붙이는 것이다.
- 이번 단계의 `EvidenceJudges`는 해제 모델이 아니라 replay와 UI 검증을 위한 evidence 껍데기다.
- `merge_likelihood`는 후보 박스 크기와 후보 간 중심 거리만 사용한다.
- `color_residual`은 컬러 프레임에서만 계산하고, 2D 흑백 또는 채널이 같은 흑백 BGR 프레임에서는 0으로 둔다.
- phase catalog, background identity, rigid violation 같은 무거운 판단은 hook 자리만 만든다.
- 후보 좌표는 Task 7 결정처럼 항상 board frame 기준으로 유지한다.
- RED 확인 결과 `ModuleNotFoundError: No module named 'core.puzzle.evidence'`로 기대한 실패가 발생했다.
- GREEN 확인 결과 Task 8 수동 테스트 4개가 통과했다.
- hook 필드는 `bg_score`, `motion_divergence`, `rigid_violation`, `phase_similarity`, `texture_bg_score`로 제한했다.
- Task 1부터 Task 8까지 수동 테스트 23개가 통과했다.
- 새 evidence 파일과 export, 테스트 파일에 대한 AST 파싱 3개가 통과했다.
- 커밋 직전 `.git` ACL의 Deny 규칙 때문에 `index.lock` 생성이 막혀 스테이징이 보류됐다.
