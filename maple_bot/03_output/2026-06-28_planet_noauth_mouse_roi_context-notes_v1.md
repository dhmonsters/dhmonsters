# planet noauth 마우스 ROI 컨텍스트 노트

## 2026-06-28
- 사용자는 감지 ROI뿐 아니라 마우스 ROI도 `planet_solver_noauth` 방식으로 동일하게 가져오길 원했다.
- noauth 구현은 보드 화면 시작점에 후보 중심을 더해 화면 절대좌표를 만들고, 다시 클라이언트 원점 `(bx, by)`를 빼서 `bg_click(hwnd, cli_x, cli_y)`를 호출한다.
- 현재 puzzle 경로의 `detect_roi`는 이미 게임 클라이언트 기준 보드 ROI이므로 `detect_roi.x + cx`, `detect_roi.y + cy`가 noauth의 `cli_x`, `cli_y`와 같은 의미다.
- 기존 `PlanetMouseController`는 분홍 커서 위치를 찾아 offset을 학습하는 방식이라 noauth 방식과 다르다. 이번 변경에서는 planet live 기본 경로를 noauth 배경 클릭 방식으로 맞춘다.
- 테스트는 번들 Python에 프로젝트 `.codex_pydeps`를 `PYTHONPATH`로 붙여 실행했다. `cv2`가 필요한 테스트까지 21개가 통과했다.
