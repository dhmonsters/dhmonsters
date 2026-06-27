# 2026-06-27_planet_live_solver_parity_context-notes_v1

## 2026-06-27

- 직전 커밋은 `planet_solver_noauth.py`의 팝업 감지 게이트와 ROI 기준만 가져온 상태였다.
- 이번 작업에서는 마우스 이동과 실시간 CCTV 표시를 추가로 이식했다.
- `planet_solver_noauth.py`의 마우스 이동은 클릭이 아니라 `win32api.SetCursorPos` 기반 fg_move 방식이다.
- 커서 보정은 DET crop에서 분홍 커서를 HSV로 검출하고, 타겟점과 커서점 차이를 offset에 EMA 방식으로 반영한다.
- offset은 X/Y 각각 `-200`부터 `200`까지 제한한다.
- F2로 solver를 멈추면 `solver_running=False`가 전달되어 마우스 이동은 하지 않고 녹화는 계속된다.
- ShapeYolo가 현재 테스트 런타임에서 `ncnn` 부재로 비활성화되지만, solver runtime은 실패하지 않고 빈 후보와 WAIT preview로 동작한다.
- 실제 환경에서 ShapeYolo가 활성화되면 DET 후보가 `IdentityTracker`로 들어가고, 결정된 point가 마우스 이동점으로 사용된다.
- armed 상태 preview는 `03_output/YYYY-MM-DD_transparent_puzzle_watch/live_watch_preview.png`에 갱신된다.
