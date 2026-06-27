# 투명도형퍼즐 task127-130 puzzle replay candidates 계획

## 목표

`puzzle.py --transparent-test --headless`가 빈 후보가 아니라 같은 이름의 JSONL 후보 로그를 읽어서 실제 후보와 identity trace를 남기게 만든다.

## 현재 문제

- 기본 이미지 replay는 정상 실행된다.
- 하지만 `CandidateProvider`가 `_empty_replay_rows`를 쓰기 때문에 후보 수가 항상 0이다.
- 기본 이미지 폴더 `000_0621_180636_png` 옆에는 `000_0621_180636.jsonl` 후보 로그가 이미 있다.
- JSONL 후보는 `[cx, cy, score]` 3칸 형식이라 현재 `CandidateProvider`의 5칸 형식과 맞지 않는다.

## 성공 기준

- 3칸 후보 row를 기본 크기 후보로 변환한다.
- image sequence replay에서 companion JSONL을 자동 발견한다.
- headless 기본 테스트 trace에 `CANDIDATES` count가 0보다 크게 기록된다.
- 기존 replay와 UI 동작은 깨지지 않는다.

## 변경 예상 파일

- `maple_bot/core/puzzle/candidates.py`.
- `maple_bot/puzzle.py`.
- `maple_bot/tests/test_puzzle_candidates.py`.
- `maple_bot/tests/test_puzzle_replay_candidates.py`.

## 설계 원칙

- live detector를 새로 붙이지 않는다.
- 이미 있는 JSONL 후보 로그를 재사용한다.
- 후보 크기 정보가 없으면 작은 기본 박스를 쓴다.
- companion JSONL이 없으면 기존처럼 빈 후보로 replay한다.
