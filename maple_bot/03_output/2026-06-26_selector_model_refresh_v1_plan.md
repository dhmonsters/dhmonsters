# selector model refresh 계획

목표는 새로 추가한 selector feature 신호가 저장 모델과 runtime selector에서 실제로 사용될 수 있게 만드는 것이다.

1. 기존 16GT feature cache가 새 신호를 포함하지 않는 문제를 테스트로 고정한다.
2. 기존 cache row에서 계산 가능한 새 신호를 보강하는 함수를 만든다.
3. 보강된 row로 학습한 모델이 16GT cached selection에서 16/16을 유지하는지 확인한다.
4. 저장된 기본 모델이 새 feature 이름을 포함하고 runtime 테스트에서도 16/16을 유지하게 갱신한다.
5. 결과와 한계를 03_output에 기록한다.

성공 기준은 기본 runtime selector 모델이 `rank_bg_like`, `rank_high_divergence`를 포함하고 기존 16GT cache 기준 16/16을 유지하는 것이다.
