# phase-catalog live family 구현 계획

## 목적

offline `phase_catalog`의 핵심은 반복되는 배경 후보를 설명하고 지우는 것이다.
현재 live family pool에는 이 source가 없어서 selector가 고를 수 있는 후보군 자체가 부족하다.

## 설계

1. `TransparentLiveFamilyPool`이 기존 sliding window와 별도로 긴 catalog candidate history를 보관한다.
2. 최근 후보 집합 반복 오차가 가장 작은 lag를 period로 추정한다.
3. 현재 후보와 `frame - period` 후보를 비교해 배경으로 설명되는 후보를 제거한다.
4. 남은 후보 중 예측 위치에 가장 가까운 후보를 `phase_catalog_live_center_mild_state_mild` family로 낸다.
5. 남은 후보가 없으면 기존 예측 위치로 coast한다.

## 검증

- synthetic 테스트로 반복 배경 후보가 예측 위치에 더 가까워도 제거되고 타겟 후보가 선택되는지 확인한다.
- 기존 live family 테스트를 유지한다.
- source upper 재채점으로 16개 GT 상한이 오르는지 확인한다.
