# noauth 후보 생성기 결합 체크리스트

- [x] `planet_solver_noauth`의 후보 생성 방식과 `ShapeYolo` 인터페이스를 확인한다.
- [x] `PlanetNoAuthDetector` 변경 범위를 M1 wrapper 앞단으로 한정한다.
- [x] ShapeYolo weak 후보 우선 사용 테스트를 추가한다.
- [x] 커서 inpaint 프레임 전달 테스트를 추가한다.
- [x] ShapeYolo 실패 시 기존 M1 fallback이 유지되게 구현한다.
- [x] 관련 테스트와 문법 검증을 실행한다.
- [x] 커밋한다.
