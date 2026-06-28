# 2026-06-28 lifecycle identity anchor v1 context notes

## 발견

현재 후보 풀의 best-family 상한은 16/16이다. 즉 정답 경로는 후보 안에 있다.

하지만 occlusion/switch variant는 GT 구간에서 새로 만들어지기 때문에 준비시간 anchor 프레임을 포함하지 않는 경우가 많다. 기존 `_anchor_mean_distance`는 anchor와 겹치는 프레임이 없으면 9999를 반환했고, 이 때문에 좋은 lifecycle 후보도 selector에서 사실상 탈락했다.

## 구현

`_identity_anchor_mean_distance`를 추가했다.

occlusion 후보는 `_occlusion_source_family`로 원본 family를 찾고, box switch 후보는 `_box_switch_source_families`로 좌우 source family를 복원한다. source family가 anchor 거리 계산에 성공하면 그 값을 variant의 identity anchor 거리로 사용한다.

## 현재 결과

단위 테스트에서는 occlusion과 box switch가 source family anchor 거리를 상속하는 것을 확인했다.

GT 16개 selected-family 점수는 6/16으로 유지됐다. 즉 상속 수정은 필요 조건이지만, 이것만으로 lifecycle 후보를 고르는 충분 조건은 아니다.

## 다음 계획

다음 단계는 lifecycle v2다. anchor 점수 자체를 selector로 쓰지 말고, event type, duplicate background ID, expected center 대비 offset, event-local acceleration, pre/post branch continuity를 분해해서 trace-first로 확인한다.
