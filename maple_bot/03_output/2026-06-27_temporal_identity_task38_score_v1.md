# Task38 시간축 판별기 GT 결과

## 후보 중심 temporal identity

- 입력은 JSONL 후보, track hint, background identity run penalty만 사용했다.
- selector 입력에 expected background를 연결한 뒤 16GT를 다시 채점했다.
- 결과는 `temporal_identity 6/16`, 평균오차 `70.2px`이다.
- raw center oracle은 `15/16`, raw box oracle은 `16/16`이다.

| clip | temporal identity |
|---|---:|
| `000_0614_111417` | 200.6 |
| `000_0614_114417` | 10.2 OK |
| `000_0614_121417` | 102.4 |
| `000_0614_124417` | 69.1 |
| `000_0614_185318` | 101.7 |
| `000_0614_204718` | 92.7 |
| `000_0614_220518` | 13.8 OK |
| `000_0614_233218` | 77.6 |
| `000_0615_000258` | 135.2 |
| `000_0615_015619` | 10.1 OK |
| `000_0615_022618` | 41.6 |
| `000_0615_025624` | 20.2 OK |
| `000_0615_035137` | 11.7 OK |
| `000_0615_042024` | 12.1 OK |
| `000_0615_044401` | 112.2 |
| `000_0615_062325` | 112.0 |

## 오프라인 family-level 시간축 판별기

- 입력은 `03_output/2026-06-25_final_candidate_feature_rows_v1.json` 캐시다.
- `_offline_16gt_solver.py`가 조건부 feature와 success label로 구조화 퍼셉트론을 학습한다.
- 선택 단계는 clip별 family feature만 보고 고른다.
- 현재 16GT 캐시 내부 재학습 기준 결과는 `16/16`, 평균오차 `30.8px`이다.
- 단, 기존 LOOCV 기록은 `6/16`이므로 일반화 solver로 확정하면 안 된다.

| clip | result | mean px | family |
|---|---:|---:|---|
| `000_0614_111417` | OK | 36.9 | `balanced_viterbi_center_mild_state_mild_lb_free` |
| `000_0614_114417` | OK | 28.1 | `panel_default_center_mild_state_mild_lb_loose` |
| `000_0614_121417` | OK | 36.7 | `strict_transition_viterbi_state_mild_lb_loose` |
| `000_0614_124417` | OK | 31.0 | `panel_default_center_mild_state_mild_lb_smooth` |
| `000_0614_185318` | OK | 38.3 | `balanced_viterbi_center_mild_state_mild_lb_free` |
| `000_0614_204718` | OK | 28.8 | `strict_transition_viterbi_state_mild_lb_loose` |
| `000_0614_220518` | OK | 31.4 | `panel_default_center_mild_state_mild_lb_loose` |
| `000_0614_233218` | OK | 37.1 | `strict_transition_viterbi_center_mild_state_mild` |
| `000_0615_000258` | OK | 37.1 | `strict_transition_viterbi_state_mild_lb_smooth` |
| `000_0615_015619` | OK | 38.6 | `strict_transition_viterbi_state_mild_lb_smooth` |
| `000_0615_022618` | OK | 37.2 | `strict_transition_viterbi_state_mild_lb_loose` |
| `000_0615_025624` | OK | 20.5 | `panel_default_center_mild_state_mild_lb_loose` |
| `000_0615_035137` | OK | 7.0 | `panel_default_center_mild_state_mild` |
| `000_0615_042024` | OK | 18.7 | `strict_transition_viterbi_center_mild_state_aggressive` |
| `000_0615_044401` | OK | 33.1 | `panel_default_center_mild_state_mild_lb_loose` |
| `000_0615_062325` | OK | 32.6 | `panel_default_center_medium_state_mild_lb_free` |

## 판단

- 후보 중심 selector는 아직 GT16/16이 아니다.
- 처음 정의한 “신분을 보류하고 시간축으로 복원하는 판별기”는 family-level 후보군에서는 16/16까지 재현된다.
- 다음 일반화 작업은 오프라인 학습 selector를 고정 모델로 승격하는 것이 아니라, LOOCV 6/16을 올릴 새 관측 신호를 추가하는 것이다.
