# 2026-06-27_puzzle_activation_gate_roi_fix_plan_v1

## 목표

F1은 솔버 감시만 켜고, 실제 투명도형 퍼즐 팝업이 감지된 뒤에만 녹화와 solver runtime을 시작한다.

## 문제 정의

기존 라이브 감지는 퍼즐 팝업 여부를 먼저 확인하지 않고 board ROI 안의 밝은 픽셀을 `white_shape`로 오인할 수 있었다. 이 때문에 일반 게임 화면에서도 녹화가 시작되고, 사용자는 퍼즐이 감지되었는지 알 수 없었다.

## 설계 방향

- `planet_solver_noauth.py`의 팝업 헤더 템플릿 감지를 라이브 감시의 첫 번째 게이트로 사용한다.
- ROI는 `planet_solver_noauth.py`의 상대좌표를 기준으로 맞춘다.
- 팝업 감지가 성공하면 `popup_board` 활성화로 판단하고 녹화를 시작한다.
- 녹화 세션에는 감지기가 계산한 detect ROI와 board ROI를 그대로 전달한다.
- `PUZZLE_ACTIVATED` trace 이벤트를 남겨서 어떤 이유와 점수로 녹화가 시작됐는지 확인할 수 있게 한다.
- 흰색 픽셀 fallback은 기본 자동 시작 조건에서 제외하고, 명시적인 `allow_white_fallback=True`일 때만 사용한다.

## 성공 기준

- 일반 게임 화면 프레임은 `popup_not_detected`로 남고 녹화가 시작되지 않는다.
- 팝업 헤더 템플릿이 있는 프레임은 `popup_board`로 활성화된다.
- UI의 ROI 표시는 planet 기준 detect, board 상대좌표를 보여준다.
- F1, F2, F3 흐름은 유지된다.
