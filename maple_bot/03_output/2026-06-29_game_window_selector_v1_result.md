# 2026-06-29 게임창 선택기 수정 결과 v1

## 변경
- `core/puzzle/game_window.py`를 추가해 게임창 후보를 점수화한다.
- `LiveRecordingRuntime`의 `GameClientFrameGrabber`가 새 게임창 선택기를 사용한다.
- `PlanetMouseController`의 background click 브릿지도 같은 게임창 선택기를 사용한다.
- 도구 UI를 제외하고 실제 게임 client 창을 고르는 테스트를 추가했다.

## 검증
- `tests.test_puzzle_game_window`, `tests.test_puzzle_planet_live`, `tests.test_puzzle_live_watch` 21개 통과.
- 게임 client grabber 직접 검증 통과.
- 주요 회귀 테스트 93개 통과.
- 16GT 시간축 판별기 검증 16/16 통과.

## 기대 효과
`puzzle.py` CCTV가 오른쪽 설정 UI나 감지 미리보기 창을 잡지 않고, noauth 미리보기와 같은 실제 게임창 client frame 기준으로 동작해야 한다.
