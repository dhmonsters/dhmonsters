# Task 28 맥락 노트

## 결정
- 사용자가 경로를 매번 입력하지 않아도 되도록 `--transparent-test`를 추가한다.
- 기본 replay 경로는 프로젝트 내부 `_record_debug/000_0621_180636_png`로 둔다.
- `--max-frames`는 headless와 transparent-test 둘 다에서 사용한다.
- UI 기본 테스트 버튼은 replay runner를 그대로 재사용하고 새 분석 로직을 만들지 않는다.

## 이유
- 사용자의 현재 목표는 풀 성능이 아니라 `puzzle.py`를 실행해 테스트를 시작할 수 있는 단계다.
- 기존 headless replay, trace, report, CCTV summary 경로를 재사용하면 구현 범위가 작고 검증이 쉽다.

## 진행 기록
- CLI `--max-frames` 테스트는 현재 parser가 옵션을 모르는 `SystemExit` 경로로 실패했다.
- `puzzle.py`에 `--transparent-test`와 `--max-frames`를 추가했다.
- `default_transparent_test_replay_path()`는 `_record_debug/000_0621_180636_png`를 가리킨다.
- UI에 `runDefaultPuzzleTestButton`을 추가하고 기존 replay runner 경로를 재사용하게 했다.
- `puzzle.py --transparent-test --output-root <temp> --max-frames 3` 실행이 report 생성까지 성공했다.
- 전체 `test_puzzle_*.py` 경량 실행 결과 67개 테스트가 통과했다.
- `puzzle.py`, `puzzle_console.py`, 관련 smoke test 문법 검사가 통과했다.
