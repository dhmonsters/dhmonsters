# 2026-06-26 selector shadow rescue gate 계획

목표는 selector shadow rescue가 과발화하지 않도록, 병합 분리용 family만 live rescue 후보로 허용하는 것이다.

1. selector shadow 결과에 `rescue_allowed` 계약을 추가하는 실패 테스트를 먼저 만든다.
2. `bg_split_viterbi` 계열은 rescue 허용, `panel_default` 계열은 rescue 비허용으로 구분한다.
3. `planet_solver_noauth.py`에서 `rescue_allowed`가 참일 때만 selector shadow rescue를 사용한다.
4. 관련 테스트와 컴파일 검증을 실행한다.
5. 결과와 다음 한계를 기록한다.
