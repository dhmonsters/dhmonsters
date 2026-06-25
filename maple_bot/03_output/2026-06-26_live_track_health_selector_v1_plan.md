# live track health selector 계획

목표는 `planet_solver_noauth`에서 ByteTrack 또는 box selector가 건강하지 않은 순간을 감지하고, 준비된 보조 경로가 있으면 그 경로로 주도권을 넘기는 것이다.

1. 밝기 정보 없이 좌표와 예측 오차만 보는 `TransparentTrackHealthSelector`를 만든다.
2. 화면 밖 이탈은 즉시 unhealthy로 본다.
3. 화면 안쪽 큰 이탈은 2프레임 연속 의심일 때 rescue로 넘긴다.
4. rescue 선택 시 몇 프레임 동안 rescue 주도권을 유지한다.
5. `planet_solver_noauth`에는 ByteTrack/box 결과와 engine 결과 사이의 최종 선택 단계로 연결한다.

성공 기준은 단위 테스트 통과와 `planet_solver_noauth.py` 문법 검증이다.
