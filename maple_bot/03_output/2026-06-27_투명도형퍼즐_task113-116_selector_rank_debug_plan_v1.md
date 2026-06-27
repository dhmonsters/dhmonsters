# selector rank debug 계획

## 목표

GT-free selector가 각 family row에 부여한 선형 점수와 순위를 노출해서, consensus family가 왜 선택되지 않는지 확인한다.

## 성공 기준

- `_final_candidate_selector.py`에 family row 점수 순위를 반환하는 helper를 추가한다.
- 기존 `select_linear_feature_rows`와 같은 점수 계산을 사용한다.
- 테스트에서 selector score와 rank 정렬을 검증한다.
- representative clip에서 consensus family의 selector rank를 확인한다.

## 이유

consensus family는 GT 근처 후보를 일부 만들었지만 최종 selector가 선택하지 않았다. 이제 후보 생성 문제가 아니라 selector ranking 문제인지 확인해야 한다.
