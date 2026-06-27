# guarded internal debug trace 리포트

- clip: `000_0614_121417`
- config: min_bg=2, match_px=16.0, shape_pct=6.0, max_step=180.0, live_max=16

## f5341 row=81

- guarded selected `[526,444]`, GT `[157.5,212.0]`, error 435.4.
- score_margin 0.205.
- guarded rank0 `[526,444]`, path_score 225.7, node_score 10.0, background false.
- guarded rank1 `[266,309]`, path_score 225.5, node_score 10.0, background false.
- GT 근처 live family는 `[171,189]`, `[134,229]`까지 들어와 있지만 guarded top5에는 없다.

## f5345 row=85

- guarded selected `[323,439]`, GT `[133.5,238.5]`, error 275.8.
- score_margin 0.679.
- guarded rank0 `[323,439]`, path_score 225.8, node_score 10.0, background false.
- guarded rank1 `[229,337]`, path_score 225.1, node_score 10.0, background false.
- GT 2.5px 후보 `[136,238]`가 live family에 있지만 guarded top5에는 없다.

## f5344 row=84

- guarded selected `[332,438]`, GT `[144.1,240.1]`, error 273.0.
- score_margin 0.196.
- guarded rank0 `[332,438]`, path_score 225.4, node_score 10.0, background false.
- guarded rank4 `[184,174]`, path_score 222.1, node_score 10.0, background false.
- GT 근처 raw 후보는 있으나 guarded는 smooth wrong path를 유지한다.

## 판단

현재 guarded 내부 점수는 비배경 후보에 거의 같은 `node_score=10.0`을 주고, detector score는 `-0.01 * score` 수준이라 후보 간 차이를 거의 만들지 못한다.

따라서 wrong identity가 한 번 잡히면 transition smoothness가 계속 우세하다. 다음 단계는 guarded 후보 점수에 raw rank, live family consensus, 또는 split recovery 같은 정체성 회복 신호를 넣어 wrong smooth path를 이길 수 있게 만드는 것이다.
