# live GT gate follow-up v1

## 이번 진행 결과.

- `visual_box_points_for_candidates`를 추가해서 후보 박스 내부의 대각 보정 지점을 점검했다.
- visual beam sweep은 16GT 기준 최고 2/16이었다.
- 고정 rank 선택기는 0/16이었다.
- 단순 raw continuity sweep은 최고 6/16이었다.
- `_live_temporal_selector_gt_score.py`에 `--summary-only`를 추가했다.
- `_live_family_pool_gt_score.py`에 `--fast-mode`를 추가했고 초기 fast-mode는 4/16이었다.
- 이번 단계에서 occlusion variant 후보를 live family pool scoring 경로에 붙였다.
- fast-mode 후보 풀을 `raw_max_candidates_per_frame=24`, `raw_rank_families=16`, `raw_continuity_families=16`, `raw_beam_families=6`, `raw_beam_spawn=6`으로 올렸다.
- `--fast-mode --occlusion-variants --success-px 40 --min-coverage 0.9` 기준 13/16까지 재현됐다.

## 현재 실패 3개.

- `000_0614_124417`, mean 62.34, best `raw_candidate_cont10_box_rel_z0_p05_state_mild`.
- `000_0615_000258`, mean 50.92, best `raw_candidate_cont12_box_rel_n1_n1_state_mild_occlusion_state`.
- `000_0615_062325`, mean 48.29, best `balanced_viterbi_center_mild_state_mild`.

## 판단.

- 후보를 더 많이 뿌리는 것만으로는 부족하지만, 겹침 상태를 시간축으로 보정하는 방향은 효과가 있다.
- 이번 상승은 프레임별 정답 선택이 아니라, 이전 움직임으로 신분을 보류하고 배경 후보와 분리되는 순간 다시 잡는 방식에서 나왔다.
- 아직 live selector 16/16은 아니다.
- 다음 병목은 남은 3개에서 배경 후보로 끌려간 시점과 release 후보를 고르는 조건이다.

## 다음 작업.

1. 실패 3개만 따로 trace해서 어느 프레임에서 identity가 깨지는지 기록한다.
2. occlusion variant의 release 조건을 배경 후보와 진짜 후보가 다시 벌어지는 순간 중심으로 조정한다.
3. 13/16이 유지되는지 먼저 재검증한다.
4. 성공 수가 15/16 이상으로 오르면 live selector 경로에 selector gate로 연결한다.
5. 성공 수가 오르지 않으면 새 후보를 늘리지 말고 실패 3개 전용 관측 신호를 만든다.
