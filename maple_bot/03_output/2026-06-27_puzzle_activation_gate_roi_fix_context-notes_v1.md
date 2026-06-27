# 2026-06-27_puzzle_activation_gate_roi_fix_context-notes_v1

## 2026-06-27

- 사용자 제보에 따르면 F1을 누른 직후 퍼즐이 없는데도 스크린샷과 녹화가 시작됐다.
- 최신 세션 `20260627_220653_001`의 preview는 투명도형 퍼즐이 아닌 일반 게임 화면이었다.
- 기존 감지기는 shape YOLO가 비활성일 때 board ROI의 밝은 픽셀을 `white_shape`로 오인할 수 있었다.
- `planet_solver_noauth.py`는 먼저 팝업 헤더 템플릿을 감지하고, 감지 성공 뒤에 board/detect ROI를 사용한다.
- 새 기준은 detect ratio `0.320,0.265,0.358,0.463`, board ratio `0.318,0.188,0.362,0.587`이다.
- 팝업 헤더 기준은 ratio `0.320,0.202,0.358,0.061`이다.
- 기본 `LivePuzzleActivationDetector`는 이제 팝업 템플릿 점수가 threshold를 넘을 때만 `popup_board`로 활성화된다.
- 흰색 픽셀 fallback은 테스트나 특수 실험용으로만 `allow_white_fallback=True`에서 유지했다.
- 녹화 시작 시 `PUZZLE_ACTIVATED` trace 이벤트를 남겨서 활성화 이유, 점수, ROI, debug 값을 확인할 수 있게 했다.
- 번들 Python에는 pytest가 없어 pytest 스타일 테스트는 직접 함수 호출 방식으로 검증했다.
- `py_compile`은 `__pycache__` 권한 때문에 실패했으므로, 파일 내용을 읽어 `compile(..., 'exec')`하는 AST 방식으로 문법 검사를 대체했다.
