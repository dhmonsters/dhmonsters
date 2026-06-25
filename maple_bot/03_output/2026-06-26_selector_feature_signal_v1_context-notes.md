# selector feature signal 기록

직전 단계에서 `balanced_viterbi_center_mild_state_mild` family는 일부 판에서 좋은 경로를 만들었다.
하지만 selector shadow는 여전히 `panel_default_center_mild_state_mild_lb_smooth` 쪽으로 쏠렸다.

이번 단계는 family를 더 만드는 것이 아니라, 좋은 family를 고를 수 있게 feature row에 motion quality, background penalty, path divergence 신호를 추가하는 것이다.

추가한 feature는 `motion_div`, `bg_like`, `divergence`다.
`motion_div`는 해당 family의 속도가 다른 family들의 중앙 속도와 얼마나 다른지 본다.
`bg_like`는 background matched ratio와 run identity ratio의 평균이다.
`divergence`는 consensus와 떨어진 정도를 high-is-better rank로도 볼 수 있게 둔 값이다.

runtime 샘플에서 `rank_high_motion_div`, `rank_bg_like`, `rank_high_divergence`가 row에 들어오는 것을 확인했다.
하지만 현재 저장된 `models/transparent/gt_free_family_selector_v1.json`의 feature list에는 이 이름들이 없다.
따라서 현 상태만으로는 기본 selector 선택 결과가 바뀌지 않는다.
다음 단계는 이 feature를 포함해 모델을 재학습하거나, live 전용 guarded heuristic을 별도로 얹는 것이다.
