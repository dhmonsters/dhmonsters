# live 후보 상한 sweep 계획

## 목표

GT 근처 후보가 `live_max_candidates=8`에서 잘리는 현상을 검증하기 위해, guarded sweep에 `live_max_candidates` 축을 추가한다.

## 성공 기준

- `score_gt_clip`이 `live_max_candidates` 값을 외부에서 받을 수 있다.
- `score_all_gt_clips`와 CLI가 같은 값을 전달한다.
- `_guarded_sweep_report.py`가 `8,16,24` 같은 후보 상한 목록을 sweep config로 만든다.
- 리포트 표에서 `live_max` 컬럼으로 결과를 비교할 수 있다.
- 관련 단위 테스트가 통과한다.

## 범위

- 후보 상한을 실험축으로 여는 것까지만 진행한다.
- selector 점수 함수 자체는 이번 단위에서 바꾸지 않는다.
