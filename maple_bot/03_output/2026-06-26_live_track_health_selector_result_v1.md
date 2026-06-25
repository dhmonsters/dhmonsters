# live track health selector 적용 결과

`planet_solver_noauth`에 live용 health selector를 연결했다.

## 적용 위치

ByteTrack 결과를 `TransparentBoxSelector`가 보정한 뒤, 마우스 이동과 녹화 JSON 기록 전에 최종 선택 단계로 들어간다.

primary는 ByteTrack/box selector의 현재 위치다.

rescue는 `TransparentPuzzleEngine`의 현재 위치다.

## 불건강 판정 타이밍

화면 밖 이탈은 즉시 rescue를 선택한다.

화면 안쪽 큰 이탈은 바로 rescue하지 않고 의심 상태로 둔다. 같은 종류의 큰 예측 오차가 2프레임 연속이면 rescue를 선택한다.

rescue를 선택하면 몇 프레임 동안 rescue 주도권을 유지하고, `TransparentBoxSelector`를 rescue 위치로 reset한다. ByteTracker가 locked 상태면 `nudge`로 같은 위치를 알려 다음 프레임에 기존 나쁜 가지로 되돌아가는 것을 줄인다.

밝기 정보는 health selector에 들어가지 않는다.

## 검증

`tests.test_transparent_track_health`와 `tests.test_transparent_box_selector`를 실행했다.

결과는 8개 테스트 통과다.

`core/vision/transparent_track_health.py`, `planet_solver_noauth.py`, `tests/test_transparent_track_health.py` 문법 컴파일도 통과했다.

## 다음 실제 테스트에서 볼 로그

녹화 JSON의 `health` 항목을 보면 된다.

- `source`: `primary` 또는 `rescue`.
- `reason`: `primary_healthy`, `primary_suspect`, `primary_out_of_bounds`, `primary_repeated_jump`, `rescue_hold` 등.
- `err`: 예측 위치와 primary의 거리.
- `suspect`: 누적 의심 프레임 수.
- `oob`: 화면 밖 이탈 여부.

실제 테스트에서 `reason=primary_out_of_bounds` 또는 `reason=primary_repeated_jump`가 뜬 프레임이 rescue 승계 타이밍이다.
