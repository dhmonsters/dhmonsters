# selector rank guarded consensus 리포트

- clip: `000_0614_121417`
- replay: live_max=16, guarded consensus family enabled.

| row | frame | selected | family | selector_rank | selector_score | rank_center | rank_cons_med | rank_rough | prior |
|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| 79 | 5339 | raw_candidate_beam10_center_mild_state_mild | guarded_decal_identity_center_mild_state_mild | 28 | 5.482 | 0.636 | 0.143 | 0.610 | -1.0 |
| 79 | 5339 | raw_candidate_beam10_center_mild_state_mild | guarded_decal_identity_consensus_center_mild_state_mild | 30 | 4.224 | 0.727 | 0.117 | 0.597 | -1.0 |
| 80 | 5340 | raw_candidate_beam10_center_mild_state_mild | guarded_decal_identity_center_mild_state_mild | 27 | 6.031 | 0.623 | 0.143 | 0.610 | -1.0 |
| 80 | 5340 | raw_candidate_beam10_center_mild_state_mild | guarded_decal_identity_consensus_center_mild_state_mild | 32 | 4.424 | 0.740 | 0.104 | 0.597 | -1.0 |
| 81 | 5341 | raw_candidate_beam8_center_mild_state_mild | guarded_decal_identity_center_mild_state_mild | 29 | 5.891 | 0.623 | 0.130 | 0.610 | -1.0 |
| 81 | 5341 | raw_candidate_beam8_center_mild_state_mild | guarded_decal_identity_consensus_center_mild_state_mild | 34 | 4.459 | 0.753 | 0.104 | 0.597 | -1.0 |
| 85 | 5345 | raw_candidate_beam8_center_mild_state_mild | guarded_decal_identity_center_mild_state_mild | 28 | 6.007 | 0.455 | 0.013 | 0.558 | -1.0 |
| 85 | 5345 | raw_candidate_beam8_center_mild_state_mild | guarded_decal_identity_consensus_center_mild_state_mild | 29 | 5.789 | 0.701 | 0.130 | 0.610 | -1.0 |

## 해석

Consensus family는 일부 frame에서 GT 근처 후보를 만들지만 selector rank는 29에서 34위 수준이다.

`rank_cons_med`는 비교적 좋지만 `rank_center`가 나쁘고, 모델에는 guarded consensus source를 별도로 보상하는 feature가 없다. 그래서 최종 선택은 raw beam 계열로 남는다.

다음 단계는 둘 중 하나다.

1. selector shadow에서 guarded consensus family를 별도 rescue 후보로 평가한다.
2. GT-free model feature에 guarded consensus source prior를 추가하고 모델을 다시 학습한다.

라이브 안정성 관점에서는 1번이 더 작고 빠른 변경이다.
