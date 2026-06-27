# 2026-06-27_puzzle_activation_gate_roi_fix_checklist_v1

- [x] 일반 게임 화면에서 녹화가 시작되는 오탐 재현 테스트를 확인했다.
- [x] `planet_solver_noauth.py`의 팝업 헤더, board, detect ROI 비율을 확인했다.
- [x] 기본 감지에서 흰색 픽셀 fallback을 제거했다.
- [x] 팝업 헤더 템플릿 감지 테스트를 추가했다.
- [x] 감지 결과가 board/detect ROI를 녹화 runtime에 전달하도록 수정했다.
- [x] `PUZZLE_ACTIVATED` trace 이벤트를 추가했다.
- [x] UI ROI 표시 테스트를 planet 기준 값으로 갱신했다.
- [x] 최신 일반 게임 화면 샘플이 `popup_not_detected`로 막히는지 확인했다.
- [x] 관련 unittest와 수동 pytest 스타일 검증을 실행했다.
