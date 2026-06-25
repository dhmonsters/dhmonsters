# selector shadow 분석기 v1 계획

목표는 `_record_debug/*.jsonl`에 기록된 `selector_shadow`를 읽어 기존 추적과 새 selector 판단이 갈라지는 프레임을 자동 요약하는 것이다.

1. JSONL 프레임을 안전하게 읽는다.
2. `track`, `engine.track`, `selector_shadow.point`를 추출한다.
3. `track`과 `selector_shadow.point`의 거리가 큰 프레임을 divergence로 표시한다.
4. `track`은 없지만 shadow point가 있는 프레임을 recovery 후보로 표시한다.
5. 이전 프레임 대비 track jump와 shadow jump를 비교해 shadow가 더 안정적인 프레임을 표시한다.
6. `_record_debug` 전체를 훑어 markdown 리포트를 생성한다.

이번 단계는 분석 전용이며 실제 조종 좌표는 바꾸지 않는다.
