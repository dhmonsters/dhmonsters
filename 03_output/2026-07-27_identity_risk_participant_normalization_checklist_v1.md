# Identity-Risk 사건 참여자 정규화 체크리스트

## 설계

- [x] visible contact와 identity-risk 사건을 분리했다.
- [x] 검출 제안, 물리 후보, 사건 참여자, 신분 역할을 분리했다.
- [x] 고정 좌표와 절대 프레임을 사용하지 않는 계약을 고정했다.

## 구현

- [ ] Task 1. visible contact가 scoreable event를 열지 않게 한다.
- [ ] Task 2. 사건 지역 물리 후보 묶음과 가능한 쌍 생성기를 만든다.
- [ ] Task 3. 여러 쌍 가설의 HOLD와 후속 관측 해소를 구현한다.
- [ ] Task 4. 사건 추출과 replay에 identity-risk 지역화를 연결한다.
- [ ] Task 5. 전체 합성 회귀와 대표 identity-risk 사건 1회 Gate를 수행한다.

## 검증

- [ ] 30개 보드 후보가 있는 visible contact를 비채점 처리한다.
- [ ] 사건 밖 후보 추가 전후 runtime 결정이 같다.
- [ ] 근접한 서로 다른 도형을 중복으로 합치지 않는다.
- [ ] 후보 쌍 모호성에서 잘못 선택하지 않고 HOLD한다.
- [ ] 병합 부모 중심이 타겟 속도에 들어가지 않는다.
- [ ] GT 변경이 runtime 결정에 영향을 주지 않는다.
- [ ] 대표 사건 실패 시 두 번째 사건과 Studio 연결을 중단한다.
