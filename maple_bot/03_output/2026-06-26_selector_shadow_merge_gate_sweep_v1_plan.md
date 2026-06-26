# 2026-06-26 selector shadow merge gate sweep 계획

## 목표

16개 GT 녹화에서 병합 gate 기준을 바꿔가며 `bg_split`과 `rescue_allowed` 발생 양상을 빠르게 비교할 수 있게 만든다.

## 성공 기준

- backfill 재생에서 `merge_context_frames`, `merge_min_size`, `merge_size_ratio`를 외부에서 전달할 수 있다.
- batch report CLI에서도 같은 값을 받을 수 있다.
- 단위 테스트로 파라미터 전달과 결과 차이를 검증한다.
- 실제 GT 로그 일부 또는 전체에서 sweep 결과를 산출한다.

## 범위

- 이번 단계는 판단 기준을 실험 가능하게 만드는 작업이다.
- `planet_solver_noauth.py` live 동작은 아직 바꾸지 않는다.
