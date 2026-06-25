# 무손실 selector shadow replay v1 계획

목표는 기존 무손실 2판을 새 녹화 없이 재사용해 `selector_shadow`를 오프라인으로 재생하고, 핑크 커서 GT 기준으로 기존 `track`과 비교하는 것이다.

1. 무손실 JSONL의 `cands`, `track`을 읽는다.
2. PNG에서 핑크 커서 중심을 GT로 추출한다.
3. 커서 이상 구간과 해상도 이상 프레임을 제외한다.
4. `track`을 `panel_default_center_mild_state_mild` anchor로 넣어 `TransparentSelectorShadow`를 재생한다.
5. 기존 `track`, shadow replay, raw 후보 oracle을 같은 GT로 채점한다.
6. 결과를 `03_output`에 markdown으로 저장한다.

이번 단계는 검증 전용이며 실제 조종 좌표는 변경하지 않는다.
