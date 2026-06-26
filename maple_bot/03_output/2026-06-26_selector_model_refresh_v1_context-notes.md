# selector model refresh 기록

이전 단계에서 `transparent_feature_rows`는 `motion_div`, `bg_like`, `divergence`를 만들게 됐다.

하지만 `03_output/2026-06-25_final_candidate_feature_rows_v1.json`, `v2`, `v3` 모두 이 새 feature를 갖고 있지 않다.

따라서 저장 모델을 그대로 재학습해도 새 feature를 사용할 수 없다.

이번 단계는 path pool 전체를 다시 만드는 긴 작업이 아니라, 기존 cache row에서 확실하게 계산 가능한 `bg_like = (match + run) / 2`, `divergence = cons_med`와 그 rank를 먼저 정식 모델 입력으로 편입한다.

`motion_div`는 기존 cache에 path 시계열이 없어서 정확히 복원할 수 없다. 이 값은 live row에는 존재하지만, 이번 저장 모델 갱신에서는 무리하게 가짜 값을 만들지 않는다.

`augment_legacy_signal_feature_rows`를 `_offline_16gt_solver.py`에 추가했다.

기존 cache row에서 `bg_like`, `divergence`, `rank_bg_like`, `rank_high_divergence`를 복원하고, 같은 준비 경로를 학습과 runtime selection에서 같이 사용한다.

새로 학습한 기본 모델은 feature 454개를 갖고, `rank_bg_like`, `rank_high_divergence`를 포함한다.

16GT cached selection은 16/16, 평균 30.81px로 유지됐다.

무손실 2판은 최종 selected 기준 2/2를 유지했다. shadow replay 자체는 165634에서 실패하지만, 이 판은 health selector가 visual rescue를 선택하는 구조가 맞다.
