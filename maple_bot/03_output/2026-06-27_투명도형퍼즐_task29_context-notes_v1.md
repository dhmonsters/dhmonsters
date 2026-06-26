# Task 29 맥락 노트

## 결정
- 사용자가 바로 실행하기 쉽게 프로젝트 루트에 `run_puzzle_test.bat`를 둔다.
- 배치 파일은 기본 5프레임을 처리하고, 첫 번째 인자를 주면 `max_frames` 값으로 사용한다.
- 출력 경로는 `puzzle.py` 기본값을 사용하므로 `03_output/YYYY-MM-DD_transparent_puzzle_sessions` 아래에 생성된다.
- 배치 파일 안에서 `PYTHONPATH`에 프로젝트 루트와 `.codex_pydeps`를 함께 넣어 로컬 의존성 차이를 줄인다.

## 이유
- CLI 옵션은 이미 있지만 실제 테스트 시작 단계에서는 더블클릭 가능한 파일이 안전하다.
- 테스트용 런처는 솔버 성능을 바꾸지 않고, 검증 진입점만 고정한다.
- Python 실행 파일은 PC 고정 경로의 Python 3.14를 우선 사용하고, 없으면 3.13, 3.12, `python` 순서로 내려간다.

## 진행 기록
- 런처 테스트를 먼저 추가했고, `run_puzzle_test.bat`가 없어서 실패하는 RED 상태를 확인했다.
- `run_puzzle_test.bat`를 추가해 `puzzle.py --transparent-test --max-frames %MAX_FRAMES%`를 호출하도록 만들었다.
- 실제 `puzzle.py --transparent-test --output-root <temp> --max-frames 2` 실행이 리포트를 생성하는 것을 확인했다.
- 수동 테스트 러너로 `test_puzzle_*.py` 전체 68개가 통과하는 것을 확인했다.
- `puzzle.py`와 신규 런처 테스트 파일의 문법 검사를 통과했다.
- Task 29 대상 파일의 공백 검사를 통과했다.
