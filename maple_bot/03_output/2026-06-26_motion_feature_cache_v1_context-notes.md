# motion feature cache 기록

이전 단계에서 기존 cache row에는 path 시계열이 없어 `motion_div`를 정확히 복원할 수 없다는 결론을 냈다.

이번 단계는 path pool을 다시 열어서 `build_transparent_feature_rows`가 직접 `motion_div`를 계산하게 하는 것이다.

기존 cache와 비교 가능해야 하므로 family 생성은 `local_box_family_paths(..., max_local_box_families=96)`를 기준으로 둔다.

첫 구현은 생성기 자체를 작게 분리한다. 실제 16GT 전체 생성은 시간이 오래 걸릴 수 있으므로, 먼저 synthetic 테스트와 단일 clip 실행으로 구조를 검증한다.

단일 clip `000_0615_035137` 기준 `max_local_box_families=96`은 470 row를 만들었고, `motion_div`, `rank_high_motion_div`가 포함됐다.

16GT 전체 raw motion cache는 7520 row를 만들었고, temp 경로 `C:\Users\PC\AppData\Local\Temp\motion_feature_rows_v1.json`에 저장됐다.

전체 7520 row를 그대로 학습하면 시간이 너무 길어져 중단했다. 이 병목은 과거 local-box 전체 family 학습 병목과 같은 계열이다.

pattern subset은 2400 row, 16 clip이며 모든 clip에 성공 후보가 남아 있었다.

pattern subset motion cache는 temp 경로 `C:\Users\PC\AppData\Local\Temp\motion_feature_rows_pattern_v1.json`에 저장됐다.

motion-only 모델은 motion cache 기준 16/16, 평균 29.03px였지만 legacy cache에서는 10/16으로 떨어졌다.

legacy cache와 motion cache를 합산해 학습한 combo 모델은 legacy 16/16, motion 16/16을 모두 유지했다. 평균은 각각 31.50px, 31.45px였다.

combo 모델은 temp 경로 `C:\Users\PC\AppData\Local\Temp\gt_free_family_selector_combo_motion_v1.json`에 저장됐다.

현재 환경에서는 `models/transparent`와 `03_output`에 큰 JSON을 복사하거나 덮어쓰는 작업이 Access denied로 막혔다. 따라서 이번 커밋에서는 기본 모델 교체와 motion cache JSON 커밋을 보류한다.
