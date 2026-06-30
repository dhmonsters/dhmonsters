# 라이브 visible lock 보강 계획

## 목표

`puzzle.py`의 시간축 selector 구조는 유지하면서, 초반 흰색 도형을 놓치지 않도록 `planet_solver_noauth`의 초기 흰색 잠금 아이디어만 가져온다.

## 설계

- 흰색 도형 후보는 기존처럼 `white_anchor`로 생성한다.
- `white_anchor`가 2프레임 연속 가까운 위치에서 보이면 `visible_lock` 상태로 승격한다.
- `visible_lock` 동안은 selector 결과보다 흰색 도형 중심을 최종 마우스 목표로 우선한다.
- selector에는 계속 `white_anchor`를 넘겨 시간축 판별기가 이후 투명 구간을 이어받게 한다.
- 로그에는 `vlock`, `stable` 값을 표시해 실전 테스트에서 잠금 여부를 바로 확인한다.

