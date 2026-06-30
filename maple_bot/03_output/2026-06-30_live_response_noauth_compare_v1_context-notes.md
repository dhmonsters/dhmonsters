# 2026-06-30 라이브 반응속도 noauth 비교 보강 컨텍스트 v1

## 관찰
- 에러 메시지 `Assertion bytes < pkt->size / f->slice_count failed at libavcodec/ffv1enc.c:1256`는 FFV1 인코더 내부 assert라 Python 예외로 잡히지 않고 프로세스를 종료시킬 수 있다.
- `board_crop` ROI 폭이 695처럼 홀수인 경우가 있어 FFV1 writer에 불안정한 입력이 들어갈 수 있다.
- `puzzle.py`는 기존에 매 프레임 `recording.write()`를 먼저 수행하고 이후 solver를 실행했다.
- 이 때문에 녹화 I/O가 느리면 마우스 이동 자체가 늦어진다.
- 최신 trace에서 `MOUSE_MOVE` 간격은 약 0.45초였다.

## noauth와 다른 점
- noauth는 추적 중 20fps 루프를 목표로 한다.
- noauth는 실제 화면의 핑크 커서 중심을 검출해 `(target - cursor)` 차이를 offset으로 학습한다.
- 기존 `puzzle.py`는 `detect_pink_cursor()` 함수가 있어도 `SetCursorPos` 전에 offset을 학습하지 않았다.

## 결정
- live 기본 주기를 noauth와 같은 20fps로 맞춘다.
- solver/mouse를 먼저 실행하고, 녹화 write는 비동기 writer가 처리하게 한다.
- FFV1은 무손실 유지하되 writer 입력 크기를 짝수로 패딩한다.
- trace의 `MOUSE_MOVE.offset`으로 커서 보정이 실제 적용되는지 확인한다.

