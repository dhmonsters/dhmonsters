# 2026-06-28 background-flow escape signal v1 context notes

## 고정 문장

프레임별로 그 순간 제일 그럴듯한 점을 찍는 솔버가 아니라, 처음 타겟의 신분을 시간축에서 보류하고 복원할 수 있는 판별기를 만든다.

## 핵심 해석

겹쳤다는 것은 그 순간 타겟이 배경 데칼의 시계방향 흐름과 비슷한 상대 위치에 들어갔다는 뜻이다. 따라서 겹침 중에는 타겟도 잠깐 시계방향처럼 보일 수 있다.

분리된다는 것은 타겟이 배경 데칼의 시계방향 흐름에서 벗어나기 시작했다는 뜻이다. 그래서 판단 기준은 "시계방향이 아닌 것을 항상 고른다"가 아니라, "분리 순간 배경의 예상 시계방향 위치에 남는 가지와 그 위치에서 이탈하는 가지를 나눈다"가 되어야 한다.

## 다음 신호

background-flow escape signal은 release 순간에 두 가지를 비교한다.

- 배경 예상 위치에 계속 붙어 있는 가지는 배경 후보로 본다.
- 배경 예상 위치에서 멀어지는 가지는 타겟 후보로 본다.
- 한 프레임으로 확정하지 않고, 분리 후 몇 프레임 동안 이탈이 유지되는지 누적한다.

## 구현 결과

`background_flow_escape_frame_score`는 후보 박스 중심 기준으로 배경 위치에 남는 가지와 이탈하는 가지를 나눈다. 이 방식은 합성 테스트에서는 맞지만 실제 GT에서는 escape-only 0/16이었다.

`background_flow_escape_point_score`는 path가 실제로 찍은 박스 내부점을 기준으로 점수화한다. 커진 박스 안에서 배경 예상 위치에서 떨어진 내부점은 escape로 볼 수 있다. 이 방식은 합성 테스트에서는 맞았지만 실제 GT에서는 escape-only 1/16이었다.

합계, 평균, 비율 기준 모두 1/16이었고, 기존 selected-family 6/16을 넘지 못했다. 따라서 이 신호는 selector에 바로 통합하지 않는다.

## 해석

아이디어 자체는 맞다. 하지만 "배경 흐름에서 이탈했다"만 보면 오답 가지도 많이 뜬다. 지금 필요한 것은 escape 여부가 아니라 "처음 타겟 신분을 가진 가지가 escape했는가"다.

다음 단계에서는 source identity, release event type, duplicate background ID, pre-merge branch, post-release continuity를 함께 묶어야 한다.

## source identity escape 결과

`score_paths_by_identity_escape`는 escape 점수에 겹침 전 예측 연속성과 분리 후 연속성을 더했다. 합성 테스트에서는 오답 late escape를 낮출 수 있었지만, 실제 GT에서는 단독 0/16이었다.

`score_paths_by_source_identity_escape`는 occlusion/switch variant의 원본 source family 경로를 복원하고, 그 source의 과거 경로에서 분리 지점을 예측했다. 합성 테스트에서는 원본 family history와 이어지는 가지를 더 높게 골랐다.

실제 GT 16개에서는 source identity escape 단독이 2/16이었다. 기존 selector와 threshold hybrid를 해도 최대 6/16으로 현재 기준을 넘지 못했다.

결론은 source path 예측만으로도 부족하다는 것이다. 오답 가지도 source history와 비슷하게 이어지는 경우가 있다. 다음 단계는 source identity를 단독 점수로 쓰지 말고, release event type, duplicate background ID, family type, box 내부 offset 방향과 함께 조건부 feature로 묶어야 한다.

## 왜 기존 방향과 이어지는가

강체 방식과 phase catalog는 배경의 큰 시계방향 흐름을 예측하기 위한 기반이었다. box grid는 겹침 박스 안에서 타겟 중심 후보를 복원하기 위한 기반이었다. lifecycle identity anchor는 겹침 후 새로 생긴 후보가 원래 어느 후보에서 왔는지 잃지 않게 하기 위한 기반이었다.

이번 단계는 그 위에 "갈라질 때 어느 가지가 배경 흐름에 남고, 어느 가지가 배경 흐름에서 탈출하는가"를 판별하는 신호를 얹는 작업이다.
