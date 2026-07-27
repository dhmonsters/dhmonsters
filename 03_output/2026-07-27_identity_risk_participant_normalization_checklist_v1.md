# Identity-Risk 사건 참여자 정규화 체크리스트

## 설계

- [x] visible contact와 identity-risk 사건을 분리했다.
- [x] 검출 제안, 물리 후보, 사건 참여자, 신분 역할을 분리했다.
- [x] 고정 좌표와 절대 프레임을 사용하지 않는 계약을 고정했다.

## 구현

- [x] Task 1. visible contact가 scoreable event를 열지 않게 한다.
- [x] Task 2. 사건 지역 물리 후보 묶음과 가능한 쌍 생성기를 만든다.
- [x] Task 3. 여러 쌍 가설의 HOLD와 후속 관측 해소를 구현한다.
- [x] Task 4. 사건 추출과 replay에 identity-risk 지역화를 연결한다.
- [x] Task 5. 전체 합성 회귀와 대표 identity-risk 사건 1회 Gate를 수행했다. 결과는 FAIL이다.

## 검증

- [x] 30개 보드 후보가 있는 visible contact를 비채점 처리한다.
- [x] 사건 밖 후보 추가 전후 runtime 결정이 같다.
- [x] 근접한 서로 다른 도형을 중복으로 합치지 않는다.
- [x] 후보 쌍 모호성에서 잘못 선택하지 않고 HOLD한다.
- [x] 병합 부모 중심이 타겟 속도에 들어가지 않는다.
- [x] GT 변경이 runtime 결정에 영향을 주지 않는다.
- [x] 대표 사건 실패 시 두 번째 사건과 Studio 연결을 중단했다.

## Task 5 Gate 결과

- [x] 관련 전체 non-CLI suite가 `171 passed, 2 deselected`로 통과했다.
- [x] 기존 entrypoint를 `--event-limit 1`로 정확히 한 번 실행했다.
- [ ] 정확히 한 개의 물리 identity-risk 사건을 추출했다. 실제 결과는 0개다.
- [x] merged-state target decision은 0개다.
- [x] wrong switch는 0개다.
- [ ] correct transfer 또는 specific reason이 있는 safe HOLD를 얻었다. 실제 결과는 extraction diagnostic이다.
- [x] 단일 failing stage `event_detection`을 기록하고 추가 실행을 중단했다.

## 최종 리뷰 보완

- [x] physical candidate 단위로 visible contact와 premerge 참여자를 정규화했다.
- [x] 경과 시간과 속도를 반영해 split 위치와 불확실성을 예측한다.
- [x] 한 프레임 후보 누락을 같은 사건의 `candidate_absent` HOLD로 유지한다.
- [x] 증거가 있는 `SAFE_HOLD`만 Gate 성공으로 인정하고 missing-event 진단은 실패로 유지한다.
- [x] 관련 전체 non-CLI suite `178 passed, 2 deselected`를 확인했다.
- [x] 대표 trace를 재실행하지 않았으며 `expand_allowed=false`를 유지한다.
