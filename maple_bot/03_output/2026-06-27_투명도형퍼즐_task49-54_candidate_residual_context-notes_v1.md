# 투명도형 퍼즐 task49-54 후보 residual 고도화 맥락 메모

## 시작 상태

- Task48 이후 `_fast_gt_score.py` 기준 `temporal_identity`는 7/16, 평균 68.9px다.
- 실패 9개 중 대부분은 후보가 없는 문제가 아니라 후보 선택 문제다.
- raw center oracle은 15/16, raw box oracle은 16/16이다.
- 따라서 목표는 후보를 더 많이 만드는 것이 아니라, 시간축 선택기가 배경 후보로 갈아타지 않게 만드는 것이다.

## 작업 원칙

- GT label은 selector 입력으로 직접 쓰지 않는다.
- GT는 평가와 실패 분석에만 사용한다.
- 기본 라이브 경로 교체는 16GT가 실제로 개선된 뒤에만 판단한다.

## Task49 결과

- 첫 실패 프레임 후보 dump는 `03_output/2026-06-27_task49_candidate_feature_dump_v1.md`에 남겼다.
- 일부 실패는 selected와 raw center 후보가 다르다.
- 일부 실패는 selected가 raw center와 같지만 후보 중심이 40px를 넘는다.
- 따라서 후보 선택 신호와 box 내부 중심 복원을 둘 다 봐야 한다.

## Task50 결과

- `_temporal_candidate_features.py`에 후보별 local appearance residual support를 추가했다.
- `_temporal_identity_selector.py`에 `appearance_supports`와 `appearance_support_weight`를 추가했다.
- 이 신호는 시간에 따라 사라지는 color support와 별도로 동작한다.

## Task51 결과

- `_temporal_residual_score.py`로 appearance support를 붙인 16GT 채점을 추가했다.
- `appearance_weight=14` 기준 결과는 `appearance_identity` 6/16, 평균 70.2px다.
- 기존 `temporal_identity` 7/16, 평균 68.9px보다 나빠졌다.
- 실패 프레임을 뜯어보면 residual 최고점이 먼 배경 조각으로 가는 경우가 많다.
- 결론은 local appearance residual을 단독 보너스로 쓰면 안 된다는 것이다.

## Task52 결과

- `prediction_box_point`와 `point_inside_candidate_box`를 추가했다.
- 이 복원은 GT를 보지 않고, 시간축 예측점이 선택 후보 박스 안에 있을 때만 후보 내부 점으로 복원한다.

## Task53 결과

- appearance support와 box projection을 결합한 `appearance_box_identity`는 6/16, 평균 71.3px다.
- box projection은 일부 평균 오차를 조금 줄였지만 성공 수를 올리지 못했다.
- raw box oracle 16/16과의 차이는 여전히 “어느 후보 박스를 선택하느냐”에 남아 있다.

## Task54 판단

- 이번 residual 계열은 라이브 기본 경로에 적용하지 않는다.
- 코드는 실험용 채점기와 feature로 유지한다.
- 다음 단계는 residual 강화가 아니라, 겹침 직후 후보 전환을 막는 candidate identity 판별 신호를 새로 만들어야 한다.
- 후보별 질문은 “이 후보가 배경 데칼의 다음 위치로 설명되는가”와 “겹침 직후 분리된 후보 중 어느 쪽이 이전 타겟 운동과 더 일관적인가”로 좁힌다.

## 추가 진단

- 검출 score weight를 0으로 내려도 7/16 그대로다.
- keep/branch를 크게 키워도 주요 실패 클립은 그대로다.
- 준비시간 이전 프레임을 끊어도 7/16 그대로다.
- track hint를 직접 비용으로 쓰면 5/16 이하로 악화된다.
- background identity 감점을 강하게 하면 성공 수는 7/16 그대로지만 평균은 68.9px에서 65.8px까지 개선된다.
