# Source Gap Partition 결과

현재 live source 상한 캐시, raw 후보 중심 oracle, raw 후보 박스 oracle을 같은 GT 프레임 기준으로 비교했다.

## 요약

- `source_upper_solved`: 9/16. 000_0614_114417, 000_0614_121417, 000_0614_185318, 000_0614_220518, 000_0614_233218, 000_0615_025624, 000_0615_035137, 000_0615_042024, 000_0615_062325.
- `raw_center_family_missing`: 6/16. 000_0614_124417, 000_0614_204718, 000_0615_000258, 000_0615_015619, 000_0615_022618, 000_0615_044401.
- `offset_or_merge_center_reconstruction`: 1/16. 000_0614_111417.
- `detection_gap_or_visual_reconstruction`: 0/16.

## 상한 점수

- 현재 source 상한 성공: 9/16.
- raw 후보 중심 oracle 성공: 15/16.
- raw 후보 박스 oracle 성공: 16/16.

| clip | bucket | GT | source best | raw center | raw box |
|---|---|---:|---|---|---|
| `000_0614_111417` | `offset_or_merge_center_reconstruction` | 12 | phase_catalog 52.3px | 50.9px | 1.8px OK |
| `000_0614_114417` | `source_upper_solved` | 16 | balanced_viterbi 12.9px OK | 10.0px OK | 0.0px OK |
| `000_0614_121417` | `source_upper_solved` | 21 | balanced_viterbi 32.7px OK | 16.0px OK | 1.9px OK |
| `000_0614_124417` | `raw_center_family_missing` | 41 | panel_default 55.5px | 35.3px OK | 2.6px OK |
| `000_0614_185318` | `source_upper_solved` | 15 | balanced_viterbi 39.3px OK | 37.4px OK | 0.3px OK |
| `000_0614_204718` | `raw_center_family_missing` | 16 | panel_default 86.7px | 27.8px OK | 0.5px OK |
| `000_0614_220518` | `source_upper_solved` | 25 | strict_transition_viterbi 24.8px OK | 13.0px OK | 0.5px OK |
| `000_0614_233218` | `source_upper_solved` | 11 | balanced_viterbi 39.3px OK | 34.6px OK | 0.0px OK |
| `000_0615_000258` | `raw_center_family_missing` | 17 | panel_default 88.2px | 35.5px OK | 1.7px OK |
| `000_0615_015619` | `raw_center_family_missing` | 17 | strict_transition_viterbi 87.3px | 10.1px OK | 0.7px OK |
| `000_0615_022618` | `raw_center_family_missing` | 15 | balanced_viterbi 40.6px | 13.7px OK | 0.0px OK |
| `000_0615_025624` | `source_upper_solved` | 11 | phase_catalog 12.4px OK | 20.2px OK | 0.0px OK |
| `000_0615_035137` | `source_upper_solved` | 16 | balanced_viterbi 19.3px OK | 11.7px OK | 0.0px OK |
| `000_0615_042024` | `source_upper_solved` | 10 | phase_catalog 12.1px OK | 12.1px OK | 0.0px OK |
| `000_0615_044401` | `raw_center_family_missing` | 21 | bg_split_viterbi 72.7px | 18.1px OK | 0.7px OK |
| `000_0615_062325` | `source_upper_solved` | 18 | balanced_viterbi 35.7px OK | 33.3px OK | 2.8px OK |

## 해석

- 현재 실패는 “YOLO가 못 잡는 문제”가 아니다. raw 후보 박스 기준으로는 16/16 모두 정답이 후보 안에 들어간다.
- 6개는 raw 후보 중심만 잘 고르면 풀린다. 현재 family가 이 경로를 만들지 못하므로, 다음 단계는 raw 후보를 직접 살리는 family가 필요하다.
- 1개 111417은 후보 중심이 평균 50.9px로 실패하지만 박스 oracle은 1.8px이다. 이 판은 병합 중심 복원이나 박스 내부 오프셋 추정이 핵심이다.
- 따라서 다음 구현은 새 검출기가 아니라 `raw-candidate family`와 `box-offset reconstruction family`를 live selector 후보로 올리는 쪽이 맞다.
