# motion feature cache 계획

목표는 path pool에서 16GT selector feature cache를 다시 만들어 `motion_div`를 학습 입력으로 넣을 수 있게 하는 것이다.

1. 기존 `local_box_family_paths`가 만든 family path pool을 입력으로 쓴다.
2. `build_transparent_feature_rows`를 통해 `motion_div`, `bg_like`, `divergence`를 포함한 row를 만든다.
3. GT는 오프라인 채점 label인 `success`, `mean`, `max`, `coverage`를 붙이는 데만 쓴다.
4. selector 입력에서는 기존처럼 GT label을 제거한다.
5. 실제 16GT 전체 생성 전에 synthetic 테스트로 row shape와 label 연결을 고정한다.

성공 기준은 새 cache row에 `rank_high_motion_div`가 들어가고, 새 cache로 학습한 selector가 16GT 기준 16/16을 유지하거나 개선 여지를 명확히 보여주는 것이다.
