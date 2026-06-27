# planet noauth 마우스 ROI 정합 계획

## 목표
- `planet_solver_noauth.py`와 같은 방식으로 도형 후보 중심을 클릭 좌표로 바꾼다.
- 기준 좌표계는 게임 클라이언트 좌표다.
- 감지 ROI, CCTV 표시 ROI, 마우스 클릭 ROI가 같은 보드 기준을 공유하게 한다.

## 설계
- 감지 결과의 `(cx, cy)`는 detect ROI 내부 좌표로 본다.
- 클릭 좌표는 `detect_roi.x + cx`, `detect_roi.y + cy`로 만든다.
- 기본 클릭은 noauth처럼 `bg_click(hwnd, client_x, client_y)`를 사용한다.
- 화면 절대좌표는 로그와 디버그용으로만 계산한다.
- 기존 분홍 커서 기반 offset 보정은 planet noauth 경로에서는 사용하지 않는다.

## 검증
- 단위 테스트로 클릭 좌표가 noauth 방식의 클라이언트 좌표인지 확인한다.
- 기존 planet live 테스트와 녹화 테스트를 함께 실행한다.
