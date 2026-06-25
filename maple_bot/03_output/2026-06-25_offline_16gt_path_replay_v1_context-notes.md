# 16GT 선택 family 실제 경로 재생 맥락 기록

## 결정
- 캐시 점수만 믿지 않고, 선택된 family 이름을 현재 `local_box_family_paths` 출력에 다시 연결해 검증했다.
- family가 생성되지 않는 경우를 별도 실패인 `missing_family`로 기록하게 했다.
- `max_local_box_families=96`을 기본값으로 두었다.

## 이유
- 이전 16/16은 캐시 기반 selector 결과였으므로 실제 솔버 통합 가능성을 바로 보장하지 않았다.
- 실제 경로 생성으로 재채점해야 “이 family 조합을 솔버에 붙일 수 있는가”를 판단할 수 있다.

## 다음 판단
- 실제 path replay도 16/16이므로 family 생성력 자체는 16GT 범위에서 충분하다.
- 남은 문제는 GT 없이 어떤 family를 고를지 결정하는 selector다.
- 다음 단계는 clip 초반의 비지도 신호로 `panel_default`, `balanced_viterbi`, `strict_transition_viterbi` 계열 중 하나를 고르는 selector를 만드는 것이다.
