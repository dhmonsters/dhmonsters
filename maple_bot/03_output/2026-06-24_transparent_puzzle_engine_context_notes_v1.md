# 2026-06-24 transparent puzzle engine 컨텍스트 노트 v1

- 사용자는 `planet_solver_noauth.py`의 불필요한 추적 실험 흔적을 지우고, 새 설계로 넣는 방향을 승인했다.
- 단, UI, 캡처, YOLO, 마우스, 녹화는 유지한다.
- 새 엔진은 먼저 오프라인 replay로 검증한다.
- replay가 기존 consensus 9/16보다 좋아지기 전까지 live 기본 경로로 켜지 않는다.
- live 연결은 shadow mode를 우선한다.
- 핵심 병목은 후보 검출이 아니라 merged blob 내부의 타겟 중심 복원이다.
- Task 1에서 `PuzzleCandidate`, `PuzzleEngineInput`, `PuzzleEngineOutput`, `TransparentPuzzleEngine.update` 최소 계약을 추가했다.
- 흰색 anchor가 들어오면 후보보다 anchor를 우선하고 `state="white_anchor"`를 반환한다.
- Task 2에서 `BackgroundCatalog`를 추가했다.
- `prep_end`를 period로 고정하지 않고, 후보 중심 반복 거리의 median score가 가장 낮은 lag를 period로 선택한다.
- Task 3에서 `EngineConfig`, continuity gate, coast 상태를 추가했다.
- 후보가 예측 위치에서 너무 멀면 검출 중심을 따르지 않고 velocity 예측 위치를 반환한다.
- Task 4에서 후보 박스 내부 격자점과 `merged_internal` 상태를 추가했다.
- 내부점 보정은 작은 일반 박스에는 적용하지 않고, `merged_min_size` 이상의 큰 후보에서만 적용한다.
