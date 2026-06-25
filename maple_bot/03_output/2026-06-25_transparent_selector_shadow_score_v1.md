# 투명 퍼즐 selector shadow v1 검증 결과

이번 단계는 실제 조종 좌표를 바꾸지 않고, `planet_solver_noauth.py`의 `_record_debug/*.jsonl` 프레임 기록에 `selector_shadow` 결과를 추가했다.

검증 결과는 다음과 같다.

```text
Ran 18 tests in 79.638s
OK
```

문법 검증도 통과했다.

```text
ok planet_solver_noauth.py
ok core/vision/transparent_selector_shadow.py
ok core/vision/transparent_feature_rows.py
ok core/vision/transparent_family_selector_runtime.py
```

라이브 연결은 보수적으로 제한했다.

- 최근 24프레임만 사용.
- 최소 8프레임부터 선택 실행.
- 10프레임마다 한 번만 shadow selector 실행.
- 후보는 score 상위 8개만 사용.

다음 단계는 새 랜덤판 녹화에서 `track`, `box`, `engine`, `selector_shadow`가 갈라지는 프레임을 비교하는 것이다.
