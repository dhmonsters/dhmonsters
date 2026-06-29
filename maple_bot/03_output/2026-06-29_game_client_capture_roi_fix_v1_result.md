# 2026-06-29 게임창 기준 CCTV ROI 수정 결과

## 변경 내용

- 라이브 기본 캡처를 메인 모니터 전체에서 게임 클라이언트 영역 전용 캡처로 변경했다.
- 캡처 점검도 같은 게임 클라이언트 기준을 쓰도록 변경했다.
- 기본 HDR, DET, BOARD, PREVIEW ROI를 `planet_solver_noauth.py`의 보정 비율과 일치시켰다.
- UI ROI 표시와 관련 테스트 기대값을 새 비율로 갱신했다.

## 확인한 원인

CCTV가 프로그램 자기 창을 잡은 이유는 live 경로가 전체 모니터 프레임에 `window_client` ROI 비율을 적용했기 때문이다. 프로그램 창이 게임 위에 있으면 ROI 안에 puzzle GUI가 들어와서, 감지와 녹화가 잘못된 화면을 기준으로 진행됐다.

## 검증

- `tests.test_puzzle_live_watch` 통과.
- 주요 puzzle unittest 89개 통과.
- live recording 직접 테스트 통과.
- replay ROI smoke 통과.
- console ROI smoke 통과.
- GT 채점 16/16 유지.
- GT 평균 오차 26.317640328557086px 유지.

## 다음 테스트 기준

사용자 PC에서 `python puzzle.py --live-dry-run` 실행 후 F1을 누르면 CCTV에는 게임창 내부의 noauth 보정 ROI만 보여야 한다. puzzle GUI가 CCTV 안에 다시 보이면 게임창 hwnd 탐지 또는 창 제목 기준을 다시 확인한다.
