# GT 없는 family selector 채점 결과

## 요약
- label-free cache 선택 결과는 16/16이다.
- 선택 family를 실제 local-box path generator로 재생한 결과도 16/16이다.
- 실제 path 재생 평균 오차는 30.46px이다.
- 학습은 16GT label을 사용했지만, 선택 입력에서는 GT 기반 label을 제거했다.

## 실제 path 재생 결과

| clip | 결과 | 평균 오차 | 선택 family |
|---|---:|---:|---|
| 000_0614_111417 | OK | 36.9 | balanced_viterbi_center_mild_state_mild_lb_free |
| 000_0614_114417 | OK | 28.1 | panel_default_center_mild_state_mild_lb_loose |
| 000_0614_121417 | OK | 37.5 | strict_transition_viterbi_center_mild_state_mild_lb_loose |
| 000_0614_124417 | OK | 31.0 | panel_default_center_mild_state_mild_lb_smooth |
| 000_0614_185318 | OK | 38.3 | balanced_viterbi_center_mild_state_mild_lb_free |
| 000_0614_204718 | OK | 36.6 | balanced_viterbi_center_mild_lb_free |
| 000_0614_220518 | OK | 31.4 | panel_default_center_mild_state_mild_lb_loose |
| 000_0614_233218 | OK | 37.1 | strict_transition_viterbi_center_mild_state_mild |
| 000_0615_000258 | OK | 37.1 | strict_transition_viterbi_state_mild_lb_smooth |
| 000_0615_015619 | OK | 35.8 | strict_transition_viterbi_center_mild_state_mild |
| 000_0615_022618 | OK | 32.7 | balanced_viterbi_center_mild_state_mild_lb_free |
| 000_0615_025624 | OK | 20.5 | panel_default_center_mild_state_mild_lb_loose |
| 000_0615_035137 | OK | 7.0 | panel_default_center_mild_state_mild |
| 000_0615_042024 | OK | 29.0 | balanced_viterbi_center_mild_state_mild_lb_free |
| 000_0615_044401 | OK | 15.9 | panel_default_center_mild_state_mild |
| 000_0615_062325 | OK | 32.6 | panel_default_center_mild_state_mild_lb_free |

## 다음 단계
- 학습된 모델을 파일로 저장해 runtime에서 학습 시간을 제거한다.
- `planet_solver_noauth`에는 cache 학습이 아니라 저장 모델 로드 방식으로 연결한다.
- 새 랜덤 판에서는 feature rows를 만들고 이 selector로 family를 고른 뒤, 실패 clip을 다시 GT로 추가해 재학습한다.
