# 2026-06-29 게임창 기준 CCTV ROI 수정 컨텍스트 노트

## 고정 정의

프레임별 정답 선택기가 아니라, 처음 타겟의 신분을 보류하고 복원할 수 있는 시간축 판별기를 만든다.

## 원인 메모

사용자 화면에서 CCTV가 게임창이 아니라 puzzle GUI 자기 창을 잡고 있었다. 확인 결과 `LiveRecordingRuntime` 기본 캡처는 `grab_screen_bgr`로 메인 모니터 전체를 가져오고, 그 위에 `window_client` ROI 비율을 적용하고 있었다.

`planet_solver_noauth.py`는 먼저 게임창 hwnd를 찾고, `GetClientRect`와 `ClientToScreen`으로 게임 클라이언트 영역만 캡처한 뒤 그 안에서 상대좌표 ROI를 계산한다. 현재 `puzzle.py` 라이브 경로는 이 기준과 달랐다.

또한 `core/puzzle/defaults.py`는 `planet_live_solver.py`의 구형 넓은 ROI 비율을 사용하고 있었다. 사용자가 기준으로 지정한 `planet_solver_noauth.py`의 보정 ROI는 더 좁다.

## 수정 메모

`LiveRecordingRuntime`의 기본 `frame_grabber`를 `GameClientFrameGrabber`로 바꿨다. 이 캡처기는 `planet_live_solver.find_maple_hwnd()`로 게임창을 찾고, `get_client_rect_screen()`으로 클라이언트 영역만 mss/ImageGrab으로 캡처한다. 게임창을 못 찾으면 전체화면 fallback을 하지 않는다.

`capture_preflight`도 같은 캡처기를 기본값으로 사용한다. 따라서 캡처 점검 이미지는 이제 모니터 전체가 아니라 게임 클라이언트 내부의 board ROI만 저장된다.

ROI 기본값은 `planet_solver_noauth.py`의 보정값으로 맞췄다.

- HDR: `0.320,0.202,0.358,0.061`.
- DET: `0.320,0.265,0.358,0.463`.
- BOARD/PREVIEW: `0.318,0.188,0.362,0.587`.

검증 결과 관련 unittest 89개, live recording 직접 테스트, replay ROI smoke, console ROI smoke가 통과했다. `_live_temporal_selector_gt_score.py --summary-only`도 16/16, 평균 오차 26.3176px로 유지됐다.
