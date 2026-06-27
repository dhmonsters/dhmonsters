# Task79-83 guarded sweep plan

## Goal

`background_signal`과 `max_step` 병목을 동시에 확인할 수 있는 guarded parameter sweep 리포트를 만든다.

## Success Criteria

- `TransparentLiveFamilyPool`에서 guarded background match 거리와 shape 허용치를 설정할 수 있다.
- backfill과 GT replay scorer가 guarded 세부 파라미터를 전달할 수 있다.
- 작은 sweep 도구가 `min_bg`, `match_px`, `shape_pct`, `max_step` 조합별 결과를 markdown으로 출력한다.
- 대표 2개 clip에서 sweep 리포트를 생성해 후보 생성량, reason count, GT 오차 변화를 확인한다.
- 관련 unittest와 문법 검사를 통과한다.

## Steps

1. 파라미터 전달과 match 완화 테스트를 먼저 추가한다.
2. live pool, backfill, GT replay scorer에 파라미터를 연결한다.
3. sweep 리포트 도구와 요약 테스트를 추가한다.
4. 대표 2개 clip에서 작은 sweep을 실행한다.
5. context notes에 결과와 다음 판단을 기록한다.
6. 커밋한다.
