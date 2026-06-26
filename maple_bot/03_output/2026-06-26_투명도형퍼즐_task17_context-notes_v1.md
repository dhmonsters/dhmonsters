# Task 17 Context Notes

## 결정
- Trace 경로는 report 파일과 같은 폴더의 `trace.jsonl`로 추론한다.
- UI는 replay runner의 산출물 구조를 깊게 알지 않고, report 경로에서 형제 trace만 찾는다.
- trace가 없거나 일부 줄이 깨진 경우에도 replay 완료 자체는 실패로 바꾸지 않는다.

## 이유
- headless replay는 이미 session 폴더에 `report.md`와 `trace.jsonl`을 함께 만든다.
- 자동 반영을 UI 내부에 두면 사용자가 replay 후 파일을 따로 고를 필요가 없다.

## 진행 기록
- replay 완료 후 `Path(report_path).parent / "trace.jsonl"`을 자동으로 읽도록 연결했다.
- `load_trace_summary()`는 JSONL을 순서대로 읽고 기존 `apply_trace_event()`에 위임한다.
- trace 파일이 없거나 일부 줄이 깨져도 UI replay 완료 흐름은 유지한다.
- `test_puzzle_*` 스모크 묶음 45개가 통과했다.
