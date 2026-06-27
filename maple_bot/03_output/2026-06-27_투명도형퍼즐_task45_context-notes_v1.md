# Task45 맥락 노트

## 시작 결론

- `RELEASE_PENDING`은 필요한 재료지만, 낮은 비용으로 항상 열면 044401 같은 판이 크게 악화된다.
- 044401 악화 경로는 GT 구간 초반부터 track과 예측 위치가 200px 이상 떨어진 잘못된 가지를 탄다.
- 111417 개선 경로는 초반에는 track과 예측이 가까운 상태에서 올바른 후보로 갈아탄다.

## 가설

track hint와 예측 위치가 지나치게 벌어진 가지에는 `RELEASE_PENDING` 후보를 주지 않으면, 보류 상태의 이득은 남기고 044401식 붕괴는 줄일 수 있다.

## 구현 기록

- `TemporalIdentityConfig.prediction_hold_track_gate`를 추가했다.
- track hint가 없으면 gate를 적용하지 않는다.
- gate 값이 0 이하이면 기존처럼 gate를 비활성화한다.
- track hint와 예측 위치의 거리가 gate를 넘으면 `MERGED_HOLD`에서 `RELEASE_PENDING` 후보를 만들지 않는다.
- 같은 조건을 내부점 기반 보류 후보에도 적용했다.

## 검증 기록

- RED 단계에서 새 옵션을 넣은 테스트가 `unexpected keyword argument`로 실패하는 것을 확인했다.
- 구현 뒤 `tests.test_temporal_identity_selector`의 전체 테스트 함수를 직접 실행해 통과를 확인했다.
- AST 문법 검사로 `_temporal_identity_selector.py`와 `test_temporal_identity_selector.py` 파싱을 확인했다.
- 수정 파일의 trailing whitespace 검사를 통과했다.
- `_fast_gt_score.py`는 콘솔 채점은 통과했지만, `03_output` 자동 리포트 저장은 기존 권한 문제로 skip됐다.

## 채점 결론

- 기본 설정은 16GT 기준 6/16을 유지했다.
- 기본 평균 오차는 70.5px로 확인됐다.
- opt-in `prediction_hold_cost=14.0`에서 gate 40은 044401 붕괴를 233.7px에서 111.5px로 줄였다.
- gate만으로 성공 개수는 오르지 않았다.
- 다음 핵심은 `RELEASE_PENDING`을 더 여는 것이 아니라, 후보 박스 내부의 실제 중심 복원과 pixel residual 판별이다.
