# 2026-06-24 delayed selector v3 체크리스트

- [x] selector 실패 clip의 공통 feature를 확인한다.
- [x] delayed selector synthetic 테스트를 먼저 작성한다.
- [x] 테스트가 실패하는 것을 확인한다.
- [x] 최소 selector 구현으로 테스트를 통과시킨다.
- [x] 16판 GT replay 채점을 실행한다.
- [x] 결과를 context-notes에 기록한다.
- [x] 단위 테스트를 실행한다.
- [x] 논리 단위로 커밋한다.

## 추가 확인

- [x] naive cluster-size Viterbi가 실패함을 확인한다.
- [x] background family cost를 테스트로 추가하고 통과시킨다.
- [x] background cost 스윕이 185318만 회복하고 나머지 하드판은 회복하지 못함을 기록한다.
- [x] learned family feature 진단이 11/16에서 멈춤을 확인한다.
- [x] grid/residual feature 검색이 6/16에서 멈춤을 확인한다.
- [ ] 하드판을 위한 새 family 생성 방식을 설계한다.
