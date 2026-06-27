# 2026-06-27_planet_live_solver_parity_plan_v1

## 목표

`planet_solver_noauth.py`의 live 동작 방식 중 팝업 감지 이후의 실시간 CCTV 표시와 마우스 이동 방식을 현재 `puzzle.py` 아키텍처에 이식한다.

## 범위

- F1 armed 상태에서도 popup/DET ROI가 표시된 CCTV preview를 갱신한다.
- 녹화가 시작된 뒤 매 프레임 planet live solver를 호출한다.
- DET 후보를 board 좌표로 변환해 기존 시간축 `IdentityTracker`에 넣는다.
- 결정된 타겟 위치를 다시 DET 좌표로 변환해 `SetCursorPos` 방식으로 마우스를 이동한다.
- 분홍 커서 검출 기반 offset 학습을 planet 방식과 동일하게 적용한다.
- F2로 solver가 정지되면 녹화는 유지하되 마우스 이동은 멈춘다.

## 설계

새 모듈 `core/puzzle/planet_live.py`를 추가해 planet 전용 동작을 격리한다. `PlanetLiveSolver`는 DET crop에서 후보를 만들고, 기존 evidence와 identity tracker를 거친 뒤 `PlanetMouseController`에 결정점을 넘긴다. CCTV preview는 popup preview ROI를 crop하고 HDR, DET, 후보 박스, 선택 마커를 그린다.

`LiveRecordingRuntime`은 각 프레임을 저장한 뒤 `PlanetLiveSolver.analyze()`를 호출하고, solver trace 이벤트와 preview 이미지를 세션에 기록한다. `puzzle.py`의 armed 감시 루프는 녹화 시작 전에도 watch preview 이미지를 5프레임마다 갱신한다.

## 성공 기준

- armed 상태에서 session 없이 preview가 UI에 표시된다.
- live recording runtime이 solver를 호출하고 trace 이벤트를 남긴다.
- 마우스 컨트롤러가 DET 좌표와 커서 offset으로 절대 좌표를 계산한다.
- 기존 F1/F2/F3 흐름과 녹화 지속 정책이 유지된다.
