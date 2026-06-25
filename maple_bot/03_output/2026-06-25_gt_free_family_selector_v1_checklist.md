# GT 없는 family selector 체크리스트

- [x] label-free runtime 선택 테스트를 먼저 만든다.
- [x] 학습과 선택을 분리한 selector wrapper를 구현한다.
- [x] 16GT cache에서 `success`, `mean`, `max`, `coverage`를 제거해도 16/16이 선택되는지 확인한다.
- [x] 선택된 family를 실제 local-box path generator로 재생해 16/16인지 확인한다.
- [x] selector 모델 JSON 저장/불러오기 함수를 만든다.
- [x] 관련 테스트를 통과시킨다.
- [ ] `planet_solver_noauth`가 학습 없이 저장된 모델을 읽도록 연결한다.
