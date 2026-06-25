# live family pool 결과

## 요약

- `TransparentLiveFamilyPool`을 추가했다.
- `planet_solver_noauth.py`의 selector shadow 입력에 live family point를 추가했다.
- 조종 좌표는 아직 바꾸지 않았다.
- 단위 테스트와 문법 검증은 통과했다.

## 새 family

- `balanced_viterbi_center_mild_state_mild`.
- `strict_transition_viterbi_center_mild_state_mild`.

`balanced`는 후보 score와 raw motion anomaly를 쓴다.
`strict`는 먼 score spike보다 부드러운 전환을 우선한다.

## family 자체 채점

motion anomaly 추가 후 일부 판에서 유효한 family가 생겼다.

| 클립 | balanced 평균오차 | strict 평균오차 |
|---|---:|---:|
| 000_0614_114417 | 12.9px | 30.3px |
| 000_0615_035137 | 19.3px | 80.7px |
| 000_0615_022618 | 40.6px | 276.3px |
| 000_0614_233218 | 45.5px | 77.6px |
| 000_0615_062325 | 48.3px | 104.9px |

하지만 전체 16개를 해결할 정도는 아니다.
`111417`, `000258`, `044401` 등은 live family 자체가 아직 멀다.

## selector shadow 진단

live family는 대부분 프레임에서 준비됐지만 selector는 여전히 `panel_default_center_mild_state_mild_lb_smooth`를 주로 골랐다.
따라서 새 family를 추가하는 것만으로는 현재 selector shadow 점수가 오르지 않았다.

## 결론

이번 단계는 실제 family 재료를 live에 넣는 첫 발판이다.
다음 병목은 두 가지다.

1. live family의 신호를 더 보강해야 한다.
2. selector feature가 좋은 live family를 고를 수 있게 바뀌어야 한다.

다음 추천 작업은 `balanced` family의 motion quality, background-like penalty, path divergence를 selector feature로 노출하는 것이다.
