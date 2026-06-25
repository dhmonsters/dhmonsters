# GT 없는 family selector 구현 계획

## 목표
- 16GT cache에서 학습한 selector를 만든다.
- 선택 시점에는 `success`, `mean`, `max`, `coverage` 같은 GT 기반 label을 제거한 row만 사용한다.
- 선택된 family를 실제 local-box path generator로 다시 재생해 16GT 통과 여부를 확인한다.

## 절차
1. 학습용 row에서만 성공 label을 사용해 linear selector를 만든다.
2. runtime row에는 동일한 feature 전처리만 적용한다.
3. runtime 선택 함수가 label 없이 family를 고르게 한다.
4. 모델 JSON 저장/불러오기 함수를 추가한다.
5. 16GT cache label-free 선택 결과를 실제 path로 재생해 채점한다.

## 성공 기준
- label-free 선택 결과가 16GT cache 기준 16/16을 재현한다.
- 선택 family를 실제 path generator로 재생해도 16/16을 통과한다.
