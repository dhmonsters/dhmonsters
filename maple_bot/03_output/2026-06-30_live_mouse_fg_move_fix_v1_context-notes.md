# 2026-06-30 라이브 마우스 이동/녹화 종료 보강 컨텍스트 v1

## 로그에서 확인한 사실
- 최신 세션은 `03_output/2026-06-30_transparent_puzzle_sessions/20260630_123558_001`이다.
- `PUZZLE_ACTIVATED`는 1회 기록되어 감지는 성공했다.
- 초기 프레임에서 `white_anchor_count=1`, `candidate_count=1`, `visible_lock=True`가 찍혀 흰색 도형 후보도 잡혔다.
- `MOUSE_MOVE moved=True reason=bg_click`로 기록되었지만 실제 커서는 움직이지 않았다.
- `bg_click`은 백그라운드 클릭 방식이라 사용자 눈에 보이는 커서 이동과 다르다.
- `planet_solver_noauth.py`의 실제 마우스 이동은 `win32api.SetCursorPos` 기반의 보이는 커서 이동이다.

## 결정
- 라이브 기본 마우스 동작은 `bg_click`이 아니라 `fg_move`로 둔다.
- 테스트나 명시적 주입에서만 `background_clicker`를 쓰면 기존 `bg_click` 경로가 유지된다.
- `RECORDING_STOPPED`는 recorder close보다 먼저 trace에 기록한다.
- F3 녹화 종료 중 예외가 나면 UI 창이 죽지 않도록 `recording stop failed` 로그를 남기고 False를 반환한다.

## 남은 확인
- 사용자 PC에서 다시 `python puzzle.py` 실행 후 F1을 누른다.
- 감지 후 로그에 `MOUSE moved ... reason=fg_move`가 찍히는지 본다.
- 실제 커서가 흰색 도형 쪽으로 움직이는지 본다.
- F3을 눌렀을 때 프로그램 창이 남고 `RECORDING_STOPPED` 또는 실패 로그가 남는지 확인한다.

