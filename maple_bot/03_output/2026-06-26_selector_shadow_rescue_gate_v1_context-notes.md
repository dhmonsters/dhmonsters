# 2026-06-26 selector shadow rescue gate 맥락 노트

- 직전 단계에서 selector shadow 결과를 health selector의 rescue 후보로 연결했다.
- 하지만 selector가 `panel_default` 같은 현재 추적 계열을 고른 경우까지 rescue 후보로 올리면, 틀린 추적을 그대로 강화할 수 있다.
- 이번 단계는 live rescue 후보를 `bg_split_viterbi` 계열로 제한한다.
- 이 제한은 16/16을 위한 최종 selector 재학습이 아니라 live 안정성을 위한 안전장치다.
- `TransparentSelectorShadow` 결과에 `rescue_allowed`를 추가했다.
- 현재 허용 조건은 family 이름이 `bg_split_viterbi`로 시작하는 경우다. `_lb_free`, `_lb_loose`, `_lb_smooth` 같은 local-box variant도 이름 시작은 그대로라 허용된다.
- `planet_solver_noauth.py`는 `rescue_allowed`가 참일 때만 selector shadow의 `rescue_point`를 health selector 후보로 넘긴다.
- 이 단계는 과발화를 막는 1차 안전장치다. 다음 단계에서는 실제 shadow 로그에서 `bg_split`이 너무 늦게 선택되거나 너무 적게 선택되는지 봐야 한다.
