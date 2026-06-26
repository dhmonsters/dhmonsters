# 2026-06-26 selector shadow 병합 리포트 개선 결과

## 변경 요약

- `_selector_shadow_batch_report.py`가 `selector_shadow.merge_context`를 읽어 요약한다.
- markdown 표에 `merge_frames`, `merge_max`, `merge_ratio` 열을 추가했다.
- 이벤트 줄에도 해당 순간의 `merge_frames`, `merge_max`, `merge_ratio`를 출력한다.

## 샘플 확인

- 대상 파일: `_record_debug/000_0614_233218.jsonl`.
- 조건: `--limit 80 --emit-every 10 --max-candidates 8 --live-max-candidates 8`.
- 결과: `shadow=8`, `bg_split=1`, `allowed=0`, `merge_frames=5`, `merge_max=180.7`, `merge_ratio=1.229`.
- 첫 bg_split 이벤트: `f3808`, `rescue=False`, `merge_frames=0`, `merge_max=167.0`, `merge_ratio=1.138`.

## 검증

- `tests.test_selector_shadow_batch_report` 5개 통과.
- selector shadow 관련 테스트 묶음 32개 통과.
- `py_compile` 통과.
- 현재 Codex Python 런타임은 workspace의 `03_output`에 직접 파일을 쓰면 권한 오류가 나서 샘플 리포트 원본은 임시 폴더에 생성해 확인했다.
