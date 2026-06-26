# decal-filter MHT live source upper 결과

## 요약

`phase_catalog_mht_center_mild_state_mild`를 구현했지만 기본 live source로 켜기에는 계산량이 컸다.
full local-box source upper는 장시간 실행되어 중단했고, base-only 재생으로 효과를 먼저 확인했다.

## base-only 결과

- `phase_catalog`: 2/16.
- `balanced_viterbi`: 2/16.
- `strict_transition_viterbi`: 1/16.
- `bg_split_viterbi`: 0/16.
- `merge_context`: 0/16.
- `panel_default`: 0/16.

## 판단

MHT family는 synthetic 장면에서는 반복 배경 후보를 제거하고 타겟 후보를 선택한다.
하지만 실제 16개 GT replay에서는 추가 성공을 만들지 못했다.
따라서 기본값은 `enable_phase_mht=False`로 유지한다.
