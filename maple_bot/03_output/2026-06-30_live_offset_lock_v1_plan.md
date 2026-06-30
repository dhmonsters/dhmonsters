# 2026-06-30 live offset lock v1 plan

## 목표

라이브 투명도형 추적 중 흰색 앵커가 한 프레임만 다시 잡히는 상황에서 마우스 보정값이 오염되지 않게 한다.

## 성공 기준

- visible lock이 안정되지 않은 흰색 앵커 프레임에서는 `learn_offset=False`가 된다.
- visible lock이 안정된 흰색 앵커 프레임에서는 기존처럼 보정 학습이 가능하다.
- 기존 identity override와 마우스 보정 freeze 테스트가 유지된다.

## 변경 범위

- `core/puzzle/planet_live.py`.
- `tests/test_puzzle_planet_live.py`.
