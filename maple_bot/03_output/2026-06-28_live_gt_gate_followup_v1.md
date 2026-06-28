# live GT gate follow-up v1

## 이번 진행 결과.

- `visual_box_points_for_candidates`를 추가해서 후보 박스 내부의 대각 보정 지점을 점검했다.
- visual beam sweep은 16GT 기준 최고 2/16이었다.
- 고정 rank 선택기는 0/16이었다.
- 단순 raw continuity sweep은 최고 6/16이었다.
- `_live_temporal_selector_gt_score.py`에 `--summary-only`를 추가했다.
- `_live_family_pool_gt_score.py`에 `--fast-mode`를 추가했고 초기 fast-mode는 4/16이었다.
- 이번 단계에서 occlusion variant 후보를 live family pool scoring 경로에 붙였다.
- fast-mode 후보 풀을 `raw_max_candidates_per_frame=24`, `raw_rank_families=20`, `raw_continuity_families=20`, `raw_beam_families=8`, `raw_beam_spawn=8`로 올렸다.
- occlusion variant 기준 13/16에서 시작했다.
- 후보 폭 확장으로 `000_0615_062325`가 살아나 14/16이 됐다.
- gap fill variant로 `000_0615_000258`이 살아나 15/16이 됐다.
- box switch variant로 `000_0614_124417`이 살아나 16/16이 됐다.
- `--fast-mode --occlusion-variants --success-px 40 --min-coverage 0.9` 기준 16/16을 재현했다.

## 마지막 실패 분석.

- `000_0615_062325`는 후보 폭 확장으로 해결됐다.
- `000_0615_000258`은 평균 오차는 낮지만 커버리지가 15/17이라 실패했고, 짧은 gap fill로 해결됐다.
- `000_0614_124417`은 같은 후보를 따라가면서 박스 내부 기준점이 중간에 바뀌어야 했고, box switch variant로 해결됐다.
- release 단계에서 배경 중심 판정으로 바꾸는 가설은 11/16으로 떨어져 폐기했다.

## 판단.

- 후보를 더 많이 뿌리는 것만으로는 부족하지만, 겹침 상태를 시간축으로 보정하는 방향은 효과가 있다.
- 이번 상승은 프레임별 정답 선택이 아니라, 이전 움직임으로 신분을 보류하고 배경 후보와 분리되는 순간 다시 잡는 방식에서 나왔다.
- 현재 16/16은 live family upper다.
- 아직 live selector가 GT 없이 이 family를 고르는 단계는 아니다.
- 다음 병목은 많은 switch family 중 어떤 것을 실시간 selector가 선택할지다.

## 다음 작업.

1. switch family 폭을 줄여서 live에서 감당 가능한 수로 만든다.
2. selector가 GT 없이 occlusion, gap fill, box switch family를 고르는 gate를 만든다.
3. live selector 기준으로 16GT를 다시 채점한다.
4. selector가 16/16을 유지하면 puzzle.py live 경로에 연결한다.
5. selector가 흔들리면 switch 후보 선택 조건을 먼저 줄인다.
