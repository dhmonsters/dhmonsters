# live family pool 기록

이전 단계에서 visual rescue만으로는 3/18에 머물렀다.
selector shadow를 직접 좌표로 쓰면 일부 판을 살리지만 기존 성공판을 깨서 총점은 오르지 않았다.

원인은 live shadow가 16/16 캐시 selector의 실제 family pool을 만들지 못한 것이다.
따라서 이번 단계는 selector tuning이 아니라 live에서 실제 family 후보를 늘리는 작업이다.

첫 구현은 sliding Viterbi family 두 개를 만들었다.
`balanced_viterbi_center_mild_state_mild`는 후보 score와 raw motion anomaly를 쓰고, `strict_transition_viterbi_center_mild_state_mild`는 연속성만 강하게 본다.

motion anomaly 추가 전에는 balanced family가 대부분 100px 이상이었다.
motion anomaly 추가 후에는 일부 판에서 좋은 family가 생겼다.
예를 들어 `114417`은 balanced 12.9px, `035137`은 balanced 19.3px, `022618`은 balanced 40.6px까지 내려왔다.
다만 `111417`, `000258`, `044401` 등은 여전히 나쁘다.

selector shadow 진단에서는 family가 준비되는 프레임 수가 충분했지만, 선택 결과는 여전히 `panel_default_center_mild_state_mild_lb_smooth`로 크게 쏠렸다.
즉 이번 단계의 병목은 family 생성 부족에서 일부 family 품질 문제와 selector feature 문제로 이동했다.
다음 단계는 selector feature rows에서 live family의 motion quality를 드러내거나, balanced family가 강한 조건에서만 제한적으로 rescue 후보로 쓰는 게 맞다.
