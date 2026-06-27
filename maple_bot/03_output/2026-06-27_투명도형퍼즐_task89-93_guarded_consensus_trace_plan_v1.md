# Task89-93 guarded consensus trace plan

## Goal

guarded path가 먼 후보 섬을 선택할 때, 다른 live family가 GT 근처 후보를 가리키고 있었는지 확인한다.

## Success Criteria

- worst trace item에 live family point의 선택점 기준/GT 기준 거리 요약을 추가한다.
- raw continuity, raw rank, phase 계열 family가 GT 근처에 있었는지 리포트에서 볼 수 있다.
- 대표 2개 clip trace를 다시 생성해 cost 함수에 넣을 수 있는 합의 신호 후보를 기록한다.
- 관련 unittest와 문법 검사를 통과한다.

## Steps

1. live family nearest trace 테스트를 먼저 추가한다.
2. trace report에 `family_nearest_to_gt`, `family_nearest_to_selected`를 추가한다.
3. 대표 조합 trace를 다시 생성한다.
4. context notes에 쓸 수 있는 합의 신호를 기록한다.
5. 커밋한다.
