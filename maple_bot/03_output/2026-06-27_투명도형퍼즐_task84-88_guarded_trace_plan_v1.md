# Task84-88 guarded trace plan

## Goal

guarded path가 큰 오차나 큰 점프를 만들 때 어느 프레임에서 어떤 후보를 선택했는지 추적한다.

## Success Criteria

- backfilled row와 GT만으로 guarded worst frame trace를 만들 수 있다.
- trace에는 frame, error, selected point, GT, reason, step, 주변 후보가 포함된다.
- 대표 sweep 조합에서 worst frame 리포트를 생성한다.
- 관련 unittest와 문법 검사를 통과한다.

## Steps

1. worst trace 요약 테스트를 먼저 추가한다.
2. trace report 도구를 구현한다.
3. 대표 조합 `min_bg=2`, `match_px=16`, `shape_pct=6`, `max_step=180`으로 2개 clip trace를 생성한다.
4. context notes에 튀는 원인 후보를 기록한다.
5. 커밋한다.
