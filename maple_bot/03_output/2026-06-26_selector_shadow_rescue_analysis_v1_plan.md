# 2026-06-26 selector shadow rescue 분석 계획

목표는 새 live 로그에서 selector shadow rescue가 언제 후보가 되고 언제 실제 채택되는지 요약하는 것이다.

1. 기존 `_selector_shadow_analyzer.py`와 테스트를 확인한다.
2. `rescue_allowed`, `bg_split` 선택, `selector_shadow` rescue 채택 지표의 실패 테스트를 먼저 추가한다.
3. 분석기에 새 카운터와 이벤트를 추가한다.
4. live JSONL에 `rescue_source`가 남도록 frame record를 보강한다.
5. 관련 테스트와 컴파일 검증을 실행한다.
