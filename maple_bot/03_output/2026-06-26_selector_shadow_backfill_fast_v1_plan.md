# 2026-06-26 selector shadow backfill 빠른 재생 계획

목표는 기존 `_record_debug` 후보 로그를 더 짧은 시간에 재생해 `selector_shadow` 분석 가능성을 확인하는 것이다.

1. `emit_every` 옵션으로 selector runtime 호출 간격을 조절한다.
2. `limit` 옵션으로 JSONL 앞부분만 샘플 재생할 수 있게 한다.
3. CLI에 `--no-local-box`를 추가해 무거운 local-box 변형 생성을 끌 수 있게 한다.
4. analyzer가 읽을 수 있는 backfilled row를 빠르게 만드는지 테스트한다.
5. 실제 `_record_debug` 샘플에서 빠른 옵션을 검증한다.
