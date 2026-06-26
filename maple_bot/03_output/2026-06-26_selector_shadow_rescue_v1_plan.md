# 2026-06-26 selector shadow rescue 계획

목표는 selector shadow가 고른 family 좌표를 실제 live health selector의 rescue 후보로 연결하는 것이다.

1. selector shadow 결과에 live rescue용 실수 좌표를 노출하는 테스트를 먼저 추가한다.
2. selector shadow 결과에 `rescue_point`를 추가한다.
3. `planet_solver_noauth.py`에서 selector shadow를 health selector 전에 계산한다.
4. rescue 우선순위는 visual, selector shadow, engine 순서로 둔다.
5. 관련 테스트와 컴파일 검증을 실행한다.
