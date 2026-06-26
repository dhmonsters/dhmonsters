# 2026-06-26 selector shadow rescue 맥락 노트

- `TransparentSelectorShadow`는 selector가 고른 family와 point를 로그로 반환하지만, 기존 `planet_solver_noauth.py`에서는 health selector 입력으로 쓰이지 않았다.
- 따라서 새 `bg_split_viterbi_center_mild_state_mild` family가 좋은 좌표를 내도 실제 마우스 좌표에 반영되지 않는 구조였다.
- 이번 단계는 selector 결과를 바로 주 좌표로 바꾸지 않고, health selector의 rescue 후보로만 올린다.
- rescue 우선순위는 visual을 가장 강하게 보고, selector shadow를 그 다음, engine을 마지막 보조로 둔다.
- `TransparentSelectorShadow` 결과에 `rescue_point`를 추가했다. 기존 `point`는 로그용 정수 좌표이고, `rescue_point`는 health selector에 넘기는 실수 좌표다.
- `planet_solver_noauth.py`의 selector shadow 계산 주기를 `emit_every=1`로 바꿨다. rescue 후보로 쓰려면 현재 프레임 좌표가 필요하기 때문이다.
- live loop 순서를 바꿔 selector shadow를 health selector 전에 계산한다. visual rescue가 있으면 selector는 덮지 않고, selector가 없을 때만 engine rescue를 사용한다.
- selector shadow가 틀린 좌표를 골라도 바로 추적 좌표가 되지는 않는다. 기존 `TransparentTrackHealthSelector`가 primary jump, out-of-bounds, repeated suspect 상태에서 rescue를 채택한다.
