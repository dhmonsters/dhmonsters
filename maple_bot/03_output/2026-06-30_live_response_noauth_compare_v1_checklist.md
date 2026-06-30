# 2026-06-30 라이브 반응속도 noauth 비교 보강 체크리스트 v1

- [x] 최신 trace에서 실제 `MOUSE_MOVE` 간격 확인.
- [x] `planet_solver_noauth.py`의 추적 주기 20fps 확인.
- [x] 라이브 기본 fps를 20fps로 조정.
- [x] 분석/마우스 이동을 녹화 write보다 앞에 배치.
- [x] 녹화 writer를 백그라운드 큐로 분리.
- [x] FFV1 odd dimension 패딩 추가.
- [x] 핑크 커서 검출 기반 offset 학습 추가.
- [x] 직접 검증 스크립트로 cursor offset, recorder padding, async recorder 확인.
- [ ] 사용자 PC 실전 테스트에서 trace `MOUSE_MOVE` 간격이 50ms 근처로 내려가는지 확인.
- [ ] 실전 테스트에서 커서가 흰색 도형 중심으로 보정되는지 확인.

