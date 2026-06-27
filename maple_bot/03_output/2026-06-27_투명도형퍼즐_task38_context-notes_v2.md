# Task38 맥락 노트 v2

## 이번 결론

- `_fast_gt_score.py`의 `temporal_identity` 경로에 background identity를 실제로 연결했다.
- 단위 테스트로 `score_clip`이 expected background를 `temporal_identity_path_from_rows`에 넘기는 계약을 고정했다.
- 후보 중심 temporal identity는 16GT에서 `6/16`, 평균오차 `70.2px`에 머물렀다.
- 기존 `_offline_16gt_solver.py`는 캐시된 family-level 후보 row에서 `16/16`, 평균오차 `30.8px`를 재현했다.

## 중요한 구분

- 후보 중심 selector의 실패는 최종 비용만의 문제가 아니다.
- beam top 256 안에도 성공 경로가 거의 없었다.
- 즉 좋은 후보열 자체가 중간에 죽는 구조다.
- family-level solver는 여러 시간축 family를 후보로 둔 뒤, clip 전체 feature로 신분을 고른다.
- 이 방식은 “프레임별 정답 선택기”보다 처음 정의에 더 가깝다.

## 주의점

- `_offline_16gt_solver.py`의 16/16은 16GT 캐시 내부 재학습 결과다.
- 기존 LOOCV 기록은 `6/16`이다.
- 따라서 이것을 일반화 완료 solver로 부르면 안 된다.
- 다음 일반화 목표는 LOOCV와 새 랜덤판에서 버티는 관측 신호를 추가하는 것이다.

## 다음 후보 작업

- 후보 중심 `TemporalIdentitySelector`는 단독 주력에서 내리고, family-level selector 검증 기준선으로 둔다.
- 새 신호는 겹침 전후 split/release context, 후보 내부 offset 복원, 배경 설명 가능성 누적, source별 rank 의미 차이를 우선한다.
- GT16/16 재현은 `_offline_16gt_solver.py` 테스트로 잠근다.
