# 2026-06-25 local-box family 컨텍스트 노트

## 시작 상태

- delayed selector는 9~10/16 수준에서 멈췄다.
- background cost, learned family feature, grid residual feature 모두 16/16 selector로 이어지지 않았다.
- 하드판을 trace한 결과, 기존 family가 정답 후보 박스 근처까지는 오지만 박스 내부 중심을 놓치는 경우가 많다.

## 핵심 가설

- “어느 후보 박스인가”보다 “후보 박스 내부 어디인가”가 남은 오차의 큰 축이다.
- family anchor는 후보 박스를 고르는 데 쓰고, 최종 좌표는 박스 내부 grid Viterbi로 복원한다.

## 검증 결과

- 모든 family에 `lb_smooth`, `lb_loose`, `lb_free` variant를 붙인 하드판 5개 채점 결과는 5/5 성공이다.
- 111417: 36.9px, `balanced_viterbi_state_mild_lb_free`.
- 124417: 31.0px, `panel_default_center_mild_lb_smooth`.
- 233218: 29.1px, 기존 `strict_transition_viterbi_state_mild`.
- 000258: 31.9px, `balanced_viterbi_center_mild_state_medium_lb_loose`.
- 062325: 32.6px, `merge_context_lb_free`.
- 전체 16판 전체-family 채점은 모든 family에 3개 variant를 붙이면 시간이 너무 길어 중단했다. 다음 단계는 후보 family 제한 또는 캐시 최적화가 필요하다.
- 이 단계는 selector 완성이 아니라 best-family 상한 확장이다. 최종 selector는 아직 별도 문제로 남아 있다.

## 후속 확인

- `2026-06-25_fast_local_box_score_v1`에서 GT-free family prior로 local-box 대상 96개를 제한했다.
- 제한 모드 전체 16판 best-family 상한은 16/16, 평균오차 20.3px다.
