# 2026-06-30 live target arbitration v1 plan

## 목표

실전 로그에서 흰색 도형이 사라진 뒤 selector가 옆 후보로 튀는 순간을 줄이고, 마우스 보정값이 투명화 이후 오염되는 문제를 막는다.

## 성공 기준

- identity가 충분히 확신하는데 temporal selector가 큰 폭으로 벗어나면 identity 점을 우선한다.
- 마우스 커서 보정값은 흰색 앵커가 보이는 안정 구간에서만 학습한다.
- 기존 temporal selector 우선 테스트와 visible lock 테스트는 유지된다.
- 관련 단위 테스트가 통과한다.

## 변경 범위

- `core/puzzle/planet_live.py`.
- `tests/test_puzzle_planet_live.py`.
