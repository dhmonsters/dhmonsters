# 2026-06-24 delayed selector v3 계획

## 목표

GT를 보지 않고도 `segment-splice oracle 16/16`에 가까운 family 전환을 고르는 selector를 만든다.

## 현재 사실

- center-stable prep 적용 후 family segment 상한은 16/16이다.
- 기존 consensus selector는 7/16이다.
- MHT 단독 solver는 0/16이라 기본 경로가 아니다.

## 접근

1. family 경로들을 그대로 후보로 둔다.
2. per-frame 즉시 선택 대신 짧은 미래 구간을 포함한 delayed 선택을 한다.
3. 비용은 family 합의, 궤적 부드러움, 후보 박스 지지, 배경 점수, family mode prior를 합친다.
4. 먼저 synthetic 테스트로 “현재는 헷갈려도 미래 일관성으로 전환한다”를 고정한다.
5. `_gt_frames`는 최종 채점에만 사용하고 selector 입력에는 넣지 않는다.

## 성공 기준

- 최소 기존 consensus 7/16을 넘긴다.
- 목표는 16/16이다.
- 16/16 전에는 `planet_solver_noauth.py` 기본 추적을 교체하지 않는다.
