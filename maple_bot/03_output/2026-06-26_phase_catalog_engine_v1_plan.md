# phase-catalog engine 구현 계획

## 목적

현재 `TransparentPuzzleEngine`은 `phase_catalog` 이름으로 shadow에 들어가지만 실제로는 배경 catalog를 후보 선택에 사용하지 않는다.
offline에서 효과가 있었던 핵심은 한 바퀴 전 후보 집합으로 배경 데칼을 설명하고, 설명되는 후보를 타겟 후보에서 제외하는 방식이다.

## 설계

1. `TransparentPuzzleEngine`이 매 프레임 후보를 `BackgroundCatalog`에 저장한다.
2. 흰색 준비 구간에는 white anchor 주변 후보를 catalog에서 제외한다.
3. 흰색 구간이 끝나는 첫 프레임에서 period lag를 추정한다.
4. period가 있으면 현재 후보 중 한 바퀴 전 배경으로 설명되는 후보를 제거한다.
5. 제거 후 남는 후보가 있으면 그 후보들 안에서 기존 연속성 선택을 수행한다.

## 검증

- synthetic 테스트로 예측 위치에 더 가까운 데칼이 있어도 catalog로 설명되면 제거되는지 확인한다.
- 기존 `TransparentPuzzleEngine` 테스트를 통과시킨다.
- replay 점수를 다시 확인해 실제 16개 GT에서 개선 여부를 본다.
