# live GT gate follow-up checklist v1

- [x] visual box residual helper를 추가했다.
- [x] visual beam이 16GT에서 주력 신호인지 확인했다.
- [x] raw GT nearest 후보의 score rank 분포를 확인했다.
- [x] 고정 rank selector 상한을 확인했다.
- [x] raw continuity selector 상한을 확인했다.
- [x] live temporal score summary-only 모드를 추가했다.
- [x] live family pool fast-mode를 추가했다.
- [x] fast-mode 16GT 초기 기준을 확인했다.
- [x] occlusion variant 후보를 빠른 scoring 경로에 넣었다.
- [x] fast-mode 후보 풀을 확장했다.
- [x] fast-mode + occlusion variant 기준 13/16을 재현했다.
- [ ] 실패 3개 trace를 만든다.
- [ ] occlusion release 조건을 보강한다.
- [ ] 13/16 이상 유지 여부를 재검증한다.
- [ ] live selector 경로에는 검증된 gate만 연결한다.
- [ ] live selector 기준 16GT를 다시 채점한다.
