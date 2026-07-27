# Identity-Risk 사건 참여자 정규화 컨텍스트 노트

## 2026-07-27 재설계 결정

대표 Gate의 `duplicate_detection_unresolved`를 단순 중복 제거 실패로 해석하지 않는다. 실패 프레임에는 신뢰 가능한 흰색 앵커와 보드 전체의 실제 배경 후보 약 29개가 존재했다. 기존 추출기가 visible contact를 scoreable merge로 연 것이 상위 원인이다.

다음 구현은 보드 전체 후보를 두 개로 군집화하지 않는다. 흰색 신분이 실제로 위험해진 접촉만 사건으로 열고, 병합 전 타겟과 충돌 배경의 예측 영역 및 부모 계보를 이용해 사건 참여 후보만 지역화한다.

정규화 뒤 정확히 두 후보를 강제하지 않는다. 가능한 물리 쌍 가설을 유지하고 쌍 선택과 H1/H2 역할 선택이 모두 분명할 때만 신분을 전달한다. 모호하면 같은 사건 ID로 HOLD한다.

대표 기록은 합성 계약이 통과한 뒤 첫 scoreable identity-risk 사건 한 개만 다시 실행한다. visible contact 진단은 event limit에 포함하지 않는다.

## 2026-07-27 Task 5 대표 Gate

관련 7개 파일의 전체 non-CLI suite는 `171 passed, 2 deselected in 1.19s`로 통과했다. suite 통과 뒤 기존 `core.puzzle.binary_merge_shadow` entrypoint를 `--event-limit 1`로 정확히 한 번 실행했다.

대표 실행은 물리 identity-risk 사건을 만들기 전에 frame 70의 extraction diagnostic으로 종료됐다. 결과 행은 1개이며 `event_id=-1`, `candidate_count=35`, `extraction_reason=premerge_identity_untrusted`다. 물리 사건은 0개, merged-state target decision은 0개, wrong switch는 0개다.

Task 5 Gate는 정확히 한 개의 물리 사건을 요구하므로 FAIL이다. 단일 failing stage는 `event_detection`이다. 두 번째 사건, 파라미터 스윕, Studio batch, selection authority 연결은 수행하지 않았다.
