# 2026-06-26 selector shadow 병합 리포트 개선 계획

목표는 batch report에서 selector shadow rescue가 왜 통과하거나 막혔는지 숫자로 바로 보이게 만드는 것이다.

1. `merge_context`가 summary에 집계되는 실패 테스트를 추가한다.
2. 이벤트에도 `merge_context`를 포함해 blocked bg_split의 이유를 확인할 수 있게 한다.
3. markdown 표에 `merge_frames`, `merge_max`, `merge_ratio` 열을 추가한다.
4. 실제 `_record_debug` 단일 샘플로 출력 형식을 확인한다.
5. 관련 테스트와 컴파일 검증을 실행한다.
