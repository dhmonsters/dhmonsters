# selector_shadow 분석 리포트

현재 `_record_debug`의 기존 JSONL 34개를 확인한 결과, `selector_shadow` 로그가 있는 파일은 아직 없습니다.

- selector_shadow 파일: 0개.
- shadow 프레임: 0개.

이는 정상입니다. `selector_shadow` 기록은 직전 단계에서 `planet_solver_noauth.py`에 새로 추가했기 때문에, 기존 녹화에는 들어있지 않습니다.

새 `planet_solver_noauth.py`로 랜덤판을 녹화한 뒤 다음 명령을 실행하면 divergence 표가 채워집니다.

```text
python _selector_shadow_analyzer.py _record_debug --out 03_output/2026-06-25_selector_shadow_analysis_v1.md
```

분석기가 보는 핵심 신호는 다음과 같습니다.

- 기존 `track`과 `selector_shadow.point`가 30px 이상 벌어진 프레임.
- 기존 `track`은 없지만 `selector_shadow.point`는 있는 recovery 후보 프레임.
- 기존 `track`이 크게 튀었지만 shadow point는 덜 튄 프레임.
