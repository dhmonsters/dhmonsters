# guarded parameter sweep 리포트

| min_bg | match_px | shape_pct | max_step | clips | guarded_success | selected_success | emitted | selected | guarded_mean | selected_mean | reasons |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 2 | 10.0 | 6.0 | 80.0 | 2 | 0 | 0 | 13 | 1 | 97.9 | 169.3 | background_signal=88, max_step=30, period=26, accepted=13 |
| 2 | 10.0 | 6.0 | 180.0 | 2 | 0 | 0 | 38 | 0 | 295.4 | 169.3 | background_signal=88, accepted=38, period=26, max_step=5 |
| 2 | 16.0 | 6.0 | 80.0 | 2 | 0 | 0 | 9 | 0 | 97.9 | 169.3 | background_signal=68, max_step=54, period=26, accepted=9 |
| 2 | 16.0 | 6.0 | 180.0 | 2 | 0 | 0 | 52 | 0 | 264.4 | 169.3 | background_signal=68, accepted=52, period=26, max_step=11 |

## 해석

`match_px=16`은 `background_signal`을 88에서 68로 낮췄다. 즉 배경 match 기준을 완화하면 병목 일부는 풀린다.

하지만 `max_step=180`으로 풀면 emitted frame은 늘어나도 guarded mean error가 264.4px에서 295.4px 수준으로 커진다. 후보가 많이 살아나는 것과 정답 후보가 살아나는 것은 아직 다르다.

다음 단계는 단순 threshold 완화가 아니라, guarded path가 큰 점프를 만들 때 어떤 후보로 튀는지 worst frame 후보를 직접 뽑아보는 것이다.
