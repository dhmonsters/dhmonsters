# 2026-06-28 residual grid selector v1 체크리스트

- [x] 현재 live family pool의 box grid 후보에 residual 신호를 붙일 수 있는지 확인한다.
- [x] 기존 `_local_residual_signal.py`의 중심 패치 대비 신호를 재사용해 탐색한다.
- [x] GT 16개에서 residual grid selector 단독 점수를 측정한다.
- [x] 현재 box grid 점수와 결합했을 때 점수가 오르는지 확인한다.
- [x] 결과와 다음 계획을 문서화한다.

## 성공 기준

- GT는 채점에만 사용한다.
- 기존 selected-family 6/16보다 올라가면 채택한다.
- 10/16 이상이면 `puzzle.py` 연결 전 검토 후보로 승격한다.

## 결과

- 단순 residual 최고 후보는 배경 질감이 강한 점을 고르는 경우가 많았다.
- box grid 기준 residual 결합은 최대 5/16이었다.
- 현재 selected-family 6/16보다 낮으므로 selector에 통합하지 않는다.
