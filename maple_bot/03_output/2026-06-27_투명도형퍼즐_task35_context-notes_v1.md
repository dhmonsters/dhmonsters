# Task 35 맥락 노트

## 결정
- 빠른 성능 확인기는 정확한 live selector 재생기가 아니라, 현재 기록 데이터의 핵심 지표를 빠르게 보는 진단기로 만든다.
- `track`, `engine`, `raw center oracle`, `raw box oracle`을 같은 GT frame 기준으로 나란히 보여준다.

## 이유
- `_selector_shadow_gt_replay_score.py`는 full local-box 포함 실행이 3분 이상 걸렸고, `--no-local-box`도 90초 이상 걸렸다.
- `_live_source_upper_score.py --raw-fast --no-local-box`는 완료됐지만 약 90초가 걸려 반복 확인용으로는 무겁다.
- 실전 전에는 먼저 16GT 전체 감각을 빠르게 확인할 수 있어야 한다.

## 구현 결과
- `_fast_gt_score.py`를 추가해 JSONL의 `track`, `engine.track`, `cands`만으로 16GT를 채점한다.
- 순수 함수 테스트는 RED에서 `ModuleNotFoundError`로 실패를 확인한 뒤 GREEN에서 5개 모두 통과했다.
- 16GT 실제 실행은 6.55초가 걸렸다.
- 결과는 `track` 0/16, `engine` 0/16, `raw_center_oracle` 15/16, `raw_box_oracle` 16/16이다.
- 평균 오차는 `track` 107.7px, `raw_center_oracle` 23.7px, `raw_box_oracle` 12.2px이다.
- `engine.track`은 현재 JSONL에 기록이 없어 평균을 계산할 수 없었다.
- 결론은 기존 추적점 자체는 실패하지만 raw 후보 안에는 정답이 거의 항상 있고, 남은 병목은 후보 선택과 박스 내부 중심 복원이다.
- 실행 결과 리포트는 `2026-06-27_fast_gt_score_current_v1.md`에 고정했다.

## 검증
- `_fast_gt_score.py --out %TEMP%/fast_gt_score_cli_check.md` 실행 종료 코드는 0이다.
- `test_fast_gt_score.py` 순수 함수 테스트는 5개 통과, 0개 실패다.
- `test_puzzle_*.py` 전체 87개는 임시 fixture runner 기준 87개 통과, 0개 실패다.
- `pytest`는 현재 런타임에 설치되어 있지 않아 직접 실행하지 못했다.
- `py_compile`은 `_fast_gt_score.py`, `tests/test_fast_gt_score.py` 모두 통과했다.
- 변경 파일 6개의 trailing whitespace와 final newline 검사는 통과했다.
