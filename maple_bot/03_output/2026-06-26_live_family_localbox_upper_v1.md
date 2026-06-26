# live family local-box 상한 확인

## 목적

현재 live에서 만들어지는 family pool 자체가 16/16에 충분한지 확인했다.

## 결과

| 실험 | 성공 | 해석 |
|---|---:|---|
| live family 중심 경로 best-family | 4/16 | selector 이전에 family 재료가 부족하다. |
| live family + local-box variant best-family | 7/16 | local-box는 일부 판을 살리지만 16/16 재료는 아니다. |

## live family + local-box clip별 best

| 클립 | best family | 평균오차 | 판정 |
|---|---|---:|---|
| `000_0614_111417` | `strict_transition_viterbi_center_mild_state_mild_lb_smooth` | 50.4px | 실패 |
| `000_0614_114417` | `balanced_viterbi_center_mild_state_mild` | 12.9px | 성공 |
| `000_0614_121417` | `balanced_viterbi_center_mild_state_mild_lb_smooth` | 58.9px | 실패 |
| `000_0614_124417` | `balanced_viterbi_center_mild_state_mild_lb_free` | 78.4px | 실패 |
| `000_0614_185318` | `balanced_viterbi_center_mild_state_mild_lb_smooth` | 50.2px | 실패 |
| `000_0614_204718` | `strict_transition_viterbi_center_mild_state_mild_lb_free` | 89.4px | 실패 |
| `000_0614_220518` | `strict_transition_viterbi_center_mild_state_mild_lb_smooth` | 11.4px | 성공 |
| `000_0614_233218` | `balanced_viterbi_center_mild_state_mild_lb_smooth` | 33.1px | 성공 |
| `000_0615_000258` | `balanced_viterbi_center_mild_state_mild_lb_loose` | 99.0px | 실패 |
| `000_0615_015619` | `strict_transition_viterbi_center_mild_state_mild_lb_smooth` | 73.2px | 실패 |
| `000_0615_022618` | `balanced_viterbi_center_mild_state_mild_lb_loose` | 35.0px | 성공 |
| `000_0615_025624` | `bg_split_viterbi_center_mild_state_mild_lb_loose` | 18.7px | 성공 |
| `000_0615_035137` | `balanced_viterbi_center_mild_state_mild_lb_smooth` | 13.1px | 성공 |
| `000_0615_042024` | `balanced_viterbi_center_mild_state_mild_lb_free` | 13.7px | 성공 |
| `000_0615_044401` | `strict_transition_viterbi_center_mild_state_mild_lb_free` | 95.3px | 실패 |
| `000_0615_062325` | `balanced_viterbi_center_mild_state_mild` | 48.3px | 실패 |

## 결론

`TransparentSelectorShadow`의 local-box 후보 순서 버그는 실제 버그였고 수정했다. 하지만 수정 후에도 live family pool의 best-family 상한은 7/16이므로, 다음 단계는 selector 튜닝이 아니라 `panel_default`, `phase_catalog`, `offset_state`, `center_reconstruct`에 해당하는 source를 live에서 더 만들 수 있는지 검토하는 것이다.
