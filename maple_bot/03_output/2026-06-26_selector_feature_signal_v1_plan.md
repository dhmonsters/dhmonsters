# selector feature signal 계획

## 목표

live family pool에서 생긴 좋은 family를 selector가 알아볼 수 있게 feature row에 새 신호를 추가한다.

## 작업 순서

1. `transparent_feature_rows` 테스트에 motion quality, background-like penalty, divergence feature 기대값을 추가한다.
2. 테스트가 실패하는 것을 확인한다.
3. feature row 생성기에 새 feature와 rank feature를 추가한다.
4. selector shadow/runtime 경로에서 새 feature가 rows에 포함되는지 검증한다.
5. 저장 모델이 새 feature를 쓰려면 재학습이 필요하다는 점을 결과에 기록한다.

## 성공 기준

- `tests.test_transparent_feature_rows`가 새 feature를 확인한다.
- 관련 selector/runtime 테스트가 통과한다.
- 현재 저장 모델의 feature list와 새 feature list 차이를 명확히 기록한다.
