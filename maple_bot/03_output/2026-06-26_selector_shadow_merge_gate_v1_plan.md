# 2026-06-26 selector shadow 병합 맥락 gate 계획

목표는 selector shadow rescue가 `bg_split` family라는 이유만으로 켜지지 않게 하고, 최근 후보 로그에 실제 병합 후보가 있었을 때만 허용하는 것이다.

1. `TransparentSelectorShadow` 테스트에서 bg_split 단독은 차단되도록 실패 테스트를 만든다.
2. 큰 후보 박스나 주변 후보 대비 큰 박스가 최근 window에 있으면 병합 맥락으로 기록한다.
3. `rescue_allowed`는 bg_split family와 병합 맥락이 동시에 있을 때만 true가 되게 한다.
4. 결과 record에 `merge_context` 요약을 포함해 analyzer와 batch report에서 원인을 볼 수 있게 한다.
5. 관련 테스트와 빠른 batch 샘플을 다시 검증한다.
