# 2026-06-29 ROI noauth 통일 결과 v1

## 변경
- `core/puzzle/defaults.py`의 기본 HDR, BRD, DET ROI를 `planet_solver_noauth.py` 기준으로 통일했다.
- CCTV preview crop 기준을 BRD와 같게 맞췄다.
- ROI 라벨, replay snapshot, preview shape 테스트 기대값을 noauth 기준으로 갱신했다.

## 검증
- `tests.test_puzzle_live_watch`, `tests.test_puzzle_planet_live` 17개 통과.
- ROI 직접 검증 통과.
- live recording F2/F3 직접 검증 통과.
- game client grabber 직접 검증 통과.
- 주요 회귀 테스트 89개 통과.
- 16GT 시간축 판별기 검증 16/16 통과.

## 참고
현재 런타임에는 pytest 모듈이 없어서 pytest 함수형 테스트는 전체 자동 실행하지 못했다. 대신 변경 지점인 ROI 문자열, ROI snapshot, F2/F3 동작, game client grabber는 직접 검증으로 확인했다.
