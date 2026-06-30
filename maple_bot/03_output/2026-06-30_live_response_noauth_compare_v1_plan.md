# 2026-06-30 라이브 반응속도 noauth 비교 보강 계획 v1

## 목표
- `puzzle.py` 라이브 추적이 `planet_solver_noauth`처럼 빠르게 반응하도록 병목을 줄인다.
- 커서가 흰색 도형 중심이 아니라 오른쪽 아래에 남는 문제를 noauth 방식의 커서 offset 학습으로 보정한다.
- FFV1 녹화 종료 시 libavcodec assert로 창이 꺼지는 문제를 피한다.

## 기준
- `planet_solver_noauth.py`는 추적 중 `TRACK_INTERVAL = 0.05`로 20fps를 목표로 한다.
- 최신 `puzzle.py` trace `20260630_131158_001`은 설정상 30fps였지만 실제 `MOUSE_MOVE` 간격이 약 430~508ms라 약 2fps였다.
- 느린 원인은 매 프레임 분석 전에 `raw_cctv`, `board_crop`, `overlay` 3개 FFV1 영상을 동기 기록하는 구조다.

## 변경
- 라이브 기본 fps를 noauth와 같은 20fps로 맞춘다.
- 분석/마우스 이동을 녹화 write보다 먼저 수행한다.
- 녹화 write는 `AsyncSessionRecorder`로 백그라운드 처리한다.
- FFV1 writer는 odd width/height를 짝수 크기로 패딩해 연산한다.
- 마우스 이동은 핑크 커서 검출 결과로 offset을 EMA 방식으로 학습한다.

