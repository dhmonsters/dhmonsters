# 16GT 선택 family 실제 경로 재생 채점 결과

## 요약
- 성공 수는 16/16이다.
- 전체 평균 오차는 30.46px이다.
- 모든 선택 family가 실제 local-box path generator에서 재생되었다.
- 이 결과는 16GT 오프라인 baseline 검증이며, 새 랜덤 판 일반화를 증명한 것은 아니다.

## 판별 결과

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

## 결론
- 다음 단계로 넘어가도 된다.
- 이유는 16GT에서 family 생성 부족 문제가 아니라 family 선택 문제가 남았기 때문이다.
