# 2026-06-26 selector shadow backfill 계획

목표는 기존 `_record_debug` JSONL 후보 로그를 다시 재생해 `selector_shadow` 기록을 가상 생성하는 것이다.

1. backfill 함수의 실패 테스트를 먼저 추가한다.
2. 기존 row의 `track`, `cands`, `engine`을 anchor로 사용한다.
3. `TransparentLiveFamilyPool`도 함께 돌려 `bg_split_viterbi` family 후보를 생성한다.
4. 결과 row에 `selector_shadow`를 추가한다.
5. 관련 테스트와 컴파일 검증을 실행한다.
