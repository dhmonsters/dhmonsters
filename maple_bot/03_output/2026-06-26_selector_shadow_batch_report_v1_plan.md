# 2026-06-26 selector shadow 배치 리포트 계획

목표는 빠른 backfill을 여러 `_record_debug` JSONL에 적용해 `bg_split`과 `rescue_allowed` 발생 지점을 한 번에 모으는 것이다.

1. backfilled row 요약 함수의 실패 테스트를 먼저 만든다.
2. 여러 JSONL 파일을 제한 개수만큼 훑는 배치 함수를 만든다.
3. 리포트에는 frame 수, shadow 수, bg_split 수, rescue_allowed 수, 첫 발생 프레임, 주요 family를 넣는다.
4. 실제 `_record_debug` 샘플 여러 개에서 빠른 옵션으로 실행한다.
5. 관련 테스트와 컴파일 검증을 실행한다.
