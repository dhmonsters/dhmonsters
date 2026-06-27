# consensus rescue sweep 리포트

| min_bg | match_px | shape_pct | max_step | live_max | clips | guarded_success | selected_success | emitted | selected | guarded_mean | selected_mean | reasons |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2 | 16.0 | 6.0 | 180.0 | 8 | 2 | 0 | 0 | 157 | 0 | 270.6 | 169.3 | background_signal=68, accepted=52, period=26, max_step=11 |
| 2 | 16.0 | 6.0 | 180.0 | 16 | 2 | 0 | 0 | 157 | 0 | 169.0 | 169.3 | accepted=129, period=26, background_signal=2 |
| 2 | 16.0 | 6.0 | 180.0 | 24 | 2 | 0 | 0 | 157 | 0 | 171.5 | 169.3 | accepted=124, period=26, background_signal=7 |

## 해석

Selector shadow record에는 consensus rescue 후보가 들어가지만, health selector가 primary를 건강하다고 판단하는 동안에는 rescue를 쓰지 않는다.

따라서 selected mean은 이전과 동일하다. 다음 병목은 rescue 후보 생성이 아니라, primary가 부드럽게 틀린 상태에서 consensus rescue를 언제 신뢰할지 판단하는 게이트다.
