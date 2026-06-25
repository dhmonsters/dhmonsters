# 투명 퍼즐 feature rows runtime 맥락 기록

## 결정
- 새 모듈은 `core/vision/transparent_feature_rows.py`에 만들었다.
- 이 모듈은 live와 record 양쪽이 같은 입력 형식을 쓰도록 `paths`, `frames`, `meta`, `candidate_sets`, optional stats를 받는다.
- GT score label은 만들지 않는다.
- background identity와 residual은 내부에서 강제로 계산하지 않고, 호출자가 계산한 stats를 주입할 수 있게 했다.

## 이유
- `planet_solver_noauth` 라이브 루프에는 아직 family별 path pool 생성기가 없다.
- 따라서 이번 단계에서 바로 마우스 제어 경로를 바꾸면 검증 없는 연결이 된다.
- 먼저 `path pool -> feature rows -> selector` 흐름을 독립 모듈로 고정했다.

## 다음 단계
- live loop 안에서 여러 family path를 동시에 쌓는 path pool builder를 만든다.
- 준비 구간과 투명 구간의 후보 row를 같은 builder에 넣고, 짧은 window마다 selector rows를 생성한다.
- selector 결과를 처음에는 shadow log로만 기록하고, 녹화 replay와 비교한 뒤 마우스 경로에 연결한다.
