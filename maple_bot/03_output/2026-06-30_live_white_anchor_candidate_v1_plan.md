# 라이브 흰색 시작 도형 후보 보강 계획

## 목표

라이브 검증 중 퍼즐은 감지됐지만 `CANDIDATES count=0`으로 끊기는 문제를 해결한다.

## 진행

- 녹화 중 `snapshots/live_preview_*.png`를 모든 프레임마다 저장한다.
- YOLO raw 후보가 0개여도 준비 시간의 흰색 도형을 `white_anchor` 후보로 생성한다.
- 생성된 `white_anchor`를 `IdentityTracker`와 `LiveTemporalSelector`의 시간축 anchor로 전달한다.
- 로그에 `raw`, `white`, `merged` 후보 수를 표시해 다음 인게임 테스트에서 실패 위치를 바로 볼 수 있게 한다.

