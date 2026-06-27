# guarded consensus family sweep 리포트

| min_bg | match_px | shape_pct | max_step | live_max | clips | guarded_success | selected_success | emitted | selected | guarded_mean | selected_mean | reasons |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2 | 16.0 | 6.0 | 180.0 | 8 | 2 | 0 | 0 | 157 | 0 | 270.6 | 169.3 | background_signal=68, accepted=52, period=26, max_step=11 |
| 2 | 16.0 | 6.0 | 180.0 | 16 | 2 | 0 | 0 | 157 | 0 | 169.0 | 169.3 | accepted=129, period=26, background_signal=2 |
| 2 | 16.0 | 6.0 | 180.0 | 24 | 2 | 0 | 0 | 157 | 0 | 171.5 | 169.3 | accepted=124, period=26, background_signal=7 |

## 해석

`guarded_decal_identity_consensus_center_mild_state_mild`를 추가한 뒤 representative 2개 클립에서 다시 sweep했다.

consensus family 때문에 guarded 계열 emitted path는 더 자주 나오고, `live_max=16`의 guarded mean은 173.5에서 169.0으로 조금 개선됐다. 하지만 `selected_success`와 `selected_mean`은 변하지 않았다.

따라서 이번 변경은 후보 생성 쪽에는 의미가 있지만, 최종 selector가 consensus family를 아직 선택하지 않는 것이 다음 병목이다.
