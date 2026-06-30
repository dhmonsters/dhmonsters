# 라이브 visible lock 보강 체크리스트

- [x] `planet_solver_noauth`의 초반 흰색 도형 잠금 흐름 확인.
- [x] selector가 엉뚱한 점을 내도 stable white anchor가 최종 target을 이기는 테스트 추가.
- [x] `PlanetLiveSolver`에 2프레임 안정성 기반 visible lock 추가.
- [x] visible lock 상태를 candidate debug와 UI 로그에 표시.
- [ ] 실제 cv2 포함 Python 환경에서 테스트 실행.
- [ ] 인게임 승인 테스트에서 `vlock=True stable=2`와 `MOUSE moved` 확인.

