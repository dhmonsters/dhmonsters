# 2026-06-28 residual grid selector v1 context notes

## 설계

이번 단계는 box grid 후보마다 주변 작은 패치의 영상 residual을 계산한다. 배경과 같은 움직임을 보이는 후보는 차분이 고르게 나오고, 타겟 흔적이 남는 후보는 중심부와 주변 링의 차이가 커질 가능성이 있다.

기존 `_local_residual_signal.py`의 중심 패치 대비 함수를 재사용하되, 후보 family 생성은 현재 live family pool을 그대로 썼다.

## 탐색 결과

단순히 `contrast_median`, `contrast_mean`, `center_mean`, `ring_mean`을 box grid 점수에 더하거나 빼는 방식은 6/16을 넘지 못했다. 가장 나은 조합도 box grid 단독 5/16 수준이었다.

실패 원인은 residual이 타겟 흔적만 보는 신호가 아니기 때문이다. 배경 질감이 강한 곳이나 왜곡이 큰 곳도 residual이 크게 나오며, 이 값이 오답 데칼 후보를 끌어올렸다.

## 결정

residual v1은 selector에 통합하지 않는다. 다음 병목은 residual이 아니라, GT 구간에서 새로 만들어지는 occlusion/switch 후보가 원본 family의 초기 신분을 상속하지 못하는 구조였다.

따라서 다음 작업은 lifecycle 후보의 identity anchor 상속을 먼저 고정한다.
