# live track health selector 기록

이번 selector는 밝기를 보지 않는다. 흰색 도형이 완전히 투명해지면 밝기는 배경 데칼과 같아지므로, 밝기는 lock 단계 이후 판별 기준에서 제외한다.

불건강 판정은 세 가지로 나눈다.

- 화면 밖 이탈은 즉시 rescue를 허용한다.
- 화면 안쪽 큰 이탈은 2프레임 연속일 때 rescue를 허용한다.
- 흰색 단계처럼 `force_primary`가 들어오면 primary를 믿고 의심 상태를 초기화한다.

live loop에서는 ByteTrack/box selector 결과를 primary로 보고, `TransparentPuzzleEngine` 결과를 rescue 후보로 본다.

테스트를 먼저 추가했고, 처음에는 모듈 없음으로 실패했다. helper 구현 뒤 한 테스트가 실패했는데, 원인은 첫 번째 의심 점프를 내부 예측 상태가 학습해버렸기 때문이다.

수정은 의심 프레임을 출력은 하되 내부 속도와 마지막 위치에는 반영하지 않는 방식으로 했다. 이렇게 해야 2프레임 연속 의심을 제대로 볼 수 있다.

`planet_solver_noauth`에서는 box selector 직후 health selector를 실행한다. rescue가 선택되면 `TransparentBoxSelector.reset()`과 `ByteTracker.nudge()`를 같이 호출해 다음 프레임에 기존 나쁜 가지로 되돌아가는 힘을 낮춘다.

녹화 JSON에는 `health` 항목을 추가했다. 실제 테스트에서 rescue가 켜진 프레임은 `health.reason`으로 확인한다.
