# 2026-06-29 ROI noauth 통일 계획 v1

## 목표
- `감지 영역 미리보기`와 `puzzle.py` CCTV가 같은 게임창 client frame 안에서 같은 상대좌표 ROI를 보게 만든다.
- 게임창 기준 캡처는 유지하고, ROI 값만 `planet_solver_noauth.py` 기준으로 통일한다.

## 성공 기준
- 기본 ROI 상수가 `planet_solver_noauth.py`의 HDR, BRD, DET 비율과 일치한다.
- CCTV preview crop 크기가 1920x1080 기준 `695x634`로 고정된다.
- 기존 live watch, planet live, capture preflight, selector 회귀 검증이 통과한다.
- 16GT 시간축 판별기 점수가 16/16을 유지한다.

## 진행 순서
- 현재 mismatch 재현용 테스트 기대값을 noauth 기준으로 먼저 변경한다.
- 실패를 확인한 뒤 기본 ROI 상수를 noauth 기준으로 변경한다.
- 집중 테스트와 16GT 검증을 실행한다.
- 결과를 문서화하고 커밋한다.
