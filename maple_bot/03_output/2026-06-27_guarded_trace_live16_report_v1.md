# guarded worst frame trace

- clip: `000_0614_121417`
- config: min_bg=2, match_px=16.0, shape_pct=6.0, max_step=180.0, live_max=16

## f5341 row=81 err=435.4 reason=accepted

- selected=[526.0, 444.0] gt=[157.5, 212.0] step_prev=291.1 step_next=298.0
- debug=reason=accepted, background_frames=8, expected_frames=24, background_ratio=0.0, max_step=17.3, period=20
- cand0 point=[526.0, 444.0] score=0.5 rank=14 live8=False d_sel=0.0 d_gt=435.4
- gt_cand0 point=[119.0, 194.0] score=0.8 rank=10 live8=False d_sel=477.6 d_gt=42.5
- gt_family0 raw_candidate_cont20_box_offset_state_mild point=[171.0, 189.0] d_sel=437.1 d_gt=26.7
- gt_family1 raw_candidate_cont22_box_offset_state_mild point=[134.0, 229.0] d_sel=447.1 d_gt=29.0
- 해석: GT 근처 family가 live pool에 있지만 guarded 후보는 멀리 떨어진 raw cont5 위치를 선택했다.

## f5345 row=85 err=275.8 reason=accepted

- selected=[323.0, 439.0] gt=[133.5, 238.5] step_prev=9.1 step_next=144.3
- debug=reason=accepted, background_frames=6, expected_frames=24, background_ratio=0.0, max_step=15.8, period=20
- cand0 point=[323.0, 439.0] score=0.7 rank=15 live8=False d_sel=0.0 d_gt=275.8
- gt_cand0 point=[136.0, 238.0] score=0.8 rank=12 live8=False d_sel=274.5 d_gt=2.5
- gt_family0 balanced_viterbi_center_mild_offset_coast point=[136.0, 238.0] d_sel=274.5 d_gt=2.5
- gt_family3 raw_candidate_cont16_center_mild_state_mild point=[136.0, 238.0] d_sel=274.5 d_gt=2.5
- 해석: 정답에 거의 붙은 후보가 들어와 있는데 guarded가 같은 후보를 고르지 못했다.

## f5344 row=84 err=273.0 reason=accepted

- selected=[332.0, 438.0] gt=[144.1, 240.1] step_prev=140.8 step_next=9.1
- debug=reason=accepted, background_frames=7, expected_frames=24, background_ratio=0.0, max_step=15.8, period=20
- cand0 point=[332.0, 438.0] score=0.8 rank=9 live8=False d_sel=0.0 d_gt=273.0
- gt_cand0 point=[135.0, 236.0] score=0.6 rank=18 live8=False d_sel=282.2 d_gt=9.9
- gt_family0 raw_candidate_cont22_box_offset_state_mild point=[130.0, 260.0] d_sel=269.2 d_gt=24.4
- 해석: GT 근처 후보는 있으나 score rank가 낮고, guarded는 이전에 잡은 잘못된 정체성을 계속 따라간다.

## 판단

`live_max_candidates=16`은 GT 근처 후보를 live pool에 넣는 데 도움이 된다. 하지만 guarded_decal_identity가 pool 안의 올바른 후보를 선택하지 못한다.

다음 단계는 guarded_decal_identity 내부에서 후보별 점수 또는 선택 근거를 trace해야 한다. 지금 debug는 `accepted`, `period`, `background_frames`만 보여서 왜 wrong identity를 고르는지 설명하지 못한다.
