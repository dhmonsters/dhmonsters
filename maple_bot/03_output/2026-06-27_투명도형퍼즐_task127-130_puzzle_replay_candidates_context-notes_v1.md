# 투명도형퍼즐 task127-130 puzzle replay candidates 컨텍스트 노트

## 시작 판단

`puzzle.py` headless 기본 테스트는 실행과 녹화가 정상이다.

## 발견한 문제

기본 replay의 `CANDIDATES` count가 0으로 기록된다. 원인은 replay runner가 `_empty_replay_rows`를 쓰기 때문이다.

## 이번 작업의 결정

기본 이미지 폴더와 같은 stem의 JSONL 후보 로그를 자동으로 읽는 adapter를 추가한다. 이 작업은 live detector를 새로 붙이는 것이 아니라 오프라인 검증용 replay를 실제 후보가 있는 상태로 만드는 작업이다.

## 진행 로그

- task127-130 작업을 시작했다.
- `[cx, cy, score]` 3칸 후보 row 테스트를 먼저 추가했고 기존 구현에서 RED를 확인했다.
- 3칸 후보 row에는 기본 20x20 박스를 부여하도록 구현했다.
- image sequence replay 경로가 `*_png`이면 같은 stem의 `.jsonl` 후보 로그를 자동으로 찾는 테스트를 추가했고 RED를 확인했다.
- `puzzle.py`에 companion JSONL 후보 provider를 연결했다.
- `puzzle.py --transparent-test --headless --max-frames 2`를 임시 출력 경로로 실행했고 `CANDIDATES` count가 19로 기록되며 `TRACK_CONFIDENT` 상태가 생성되는 것을 확인했다.
