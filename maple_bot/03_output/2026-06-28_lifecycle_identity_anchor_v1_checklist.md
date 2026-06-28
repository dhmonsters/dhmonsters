# 2026-06-28 lifecycle identity anchor v1 체크리스트

- [x] occlusion/switch 후보가 준비시간 anchor 점수에서 9999 벌점을 받는지 확인한다.
- [x] occlusion 후보가 원본 family의 anchor 신분을 상속하도록 테스트를 추가한다.
- [x] box switch 후보가 좌우 source family의 anchor 신분을 상속하도록 테스트를 추가한다.
- [x] `_identity_anchor_mean_distance` helper를 구현한다.
- [x] anchor selector가 새 helper를 사용하도록 연결한다.
- [x] 전체 테스트와 diff check를 통과했는지 남긴다.
- [x] GT 16개 selected-family 점수를 문서화한다.

## 성공 기준

- variant 자체에 준비시간 프레임이 없어도 source family anchor 거리를 사용할 수 있어야 한다.
- selected-family 점수가 바로 오르지 않더라도, lifecycle v2 selector의 기반 신호로 유지한다.
