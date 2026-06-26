# 2026-06-26 selector shadow rescue 분석 맥락 노트

- `_record_debug`의 오래된 JSONL은 selector shadow가 없거나 새 `rescue_allowed` 필드가 없다.
- 앞으로 live 테스트를 할 때 `bg_split_viterbi`가 선택됐는지와 health selector가 실제로 rescue를 채택했는지를 바로 봐야 한다.
- 기존 frame record에는 health decision은 있지만 `_health_rescue_source`가 저장되지 않아 selector rescue 채택 여부를 로그만으로 분리하기 어렵다.
- 이번 단계에서는 analyzer 지표를 추가하고, live frame record에 `rescue_source`를 함께 기록한다.
- analyzer가 `rescue_allowed_frames`, `rescue_blocked_frames`, `bg_split_frames`, `selector_rescue_used`, `health_rescue_frames`를 계산하도록 보강했다.
- `write_markdown_report`는 03_output 쓰기 권한 오류가 나도 실패하지 않고 `None`을 반환한다.
- 현재 `_record_debug`를 분석하면 selector_shadow 로그가 있는 파일은 0개다. 새 live 녹화 후 다시 실행해야 의미 있는 지표가 나온다.
- `planet_solver_noauth.py`의 frame record에 `rescue_source`를 저장하도록 추가했다. 이제 visual, selector_shadow, engine 중 어느 rescue 후보였는지 JSONL에서 분리할 수 있다.
