# guarded live candidate sweep 리포트

| min_bg | match_px | shape_pct | max_step | live_max | clips | guarded_success | selected_success | emitted | selected | guarded_mean | selected_mean | reasons |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2 | 16.0 | 6.0 | 180.0 | 8 | 2 | 0 | 0 | 52 | 0 | 264.4 | 169.3 | background_signal=68, accepted=52, period=26, max_step=11 |
| 2 | 16.0 | 6.0 | 180.0 | 16 | 2 | 0 | 0 | 129 | 0 | 173.5 | 169.3 | accepted=129, period=26, background_signal=2 |
| 2 | 16.0 | 6.0 | 180.0 | 24 | 2 | 0 | 0 | 124 | 0 | 171.5 | 169.3 | accepted=124, period=26, background_signal=7 |

## 해석

`live_max_candidates=16`부터 guarded 후보 방출량이 크게 늘고 `guarded_mean`도 264.4에서 173.5로 개선된다.

하지만 `guarded_selected_frames`는 계속 0이고 `selected_mean`도 169.3으로 변하지 않는다. 따라서 현재 병목은 후보 상한 하나만이 아니라, live family pool 안에 살아난 후보를 최종 selector가 고르지 못하는 선택 비용 문제다.
