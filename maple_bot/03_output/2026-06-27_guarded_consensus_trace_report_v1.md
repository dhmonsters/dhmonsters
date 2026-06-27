# guarded consensus trace 리포트

- config: min_bg=2, match_px=16.0, shape_pct=6.0, max_step=180.0

## 핵심 요약

`000_0614_121417`에서는 GT에 매우 가까운 raw 후보가 있었지만, 그 후보들이 `live_max_candidates=8` 안에 들어오지 못했다.

따라서 현재 병목은 단순히 guarded cost가 잘못 고르는 것만이 아니다. live family pool이 보는 후보 상한에서 정답 후보가 잘리는 문제가 같이 있다.

## 000_0614_121417

### f5337 row=77

- selected=[546.0, 425.0], gt=[188.1, 181.0], error=433.2.
- selected candidate: score=0.9, rank=2, live8=True.
- GT nearest candidate: point=[189.0, 182.0], score=0.7, rank=11, live8=False, d_gt=1.3.
- nearest live family to GT: raw_candidate_beam4_center_mild_state_mild point=[116.0, 240.0], d_gt=93.1.
- 해석: 정답 후보는 raw 후보군 안에 있지만 live family 입력 상한에서 잘렸다.

### f5347 row=87

- selected=[534.0, 238.0], gt=[118.0, 247.6], error=416.1.
- selected candidate: score=0.9, rank=1, live8=True.
- GT nearest candidate: point=[103.0, 245.0], score=0.2, rank=19, live8=False, d_gt=15.2.
- nearest live family to GT: raw_candidate_cont18_box_offset_state_mild point=[93.0, 304.0], d_gt=61.7.
- 해석: 정답 근처 후보가 low-score라 live top8에 들어오지 않는다.

## 000_0614_111417

### f10658 row=69

- selected=[521.0, 87.0], gt=[185.0, 162.0], error=344.3.
- selected candidate: score=0.9, rank=6, live8=True.
- GT nearest candidate: point=[142.0, 198.0], score=0.8, rank=11, live8=False, d_gt=56.1.
- 일부 GT 근처 후보는 live8에 들어오지만 GT와의 거리가 아직 100px 이상인 것도 많다.

## 판단

다음 단계는 guarded cost만 조정하는 것이 아니라 `live_max_candidates` 후보 상한을 실험축으로 열어야 한다.

가장 먼저 볼 실험은 `live_max_candidates=8,16,24` sweep이다. 기대는 top8에서 잘리던 GT 근처 후보가 live pool에 들어오면서 guarded 또는 다른 family가 후보를 선택할 기회를 얻는지 확인하는 것이다.
