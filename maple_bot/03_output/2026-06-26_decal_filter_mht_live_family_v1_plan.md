# decal-filter MHT live family 구현 계획

## 목적

`phase_catalog_live`는 반복 배경 후보를 지우는 데 효과가 있지만 단일 경로라 초반 선택이 틀리면 회복이 어렵다.
offline `decal_filter_mht`처럼 배경으로 확정되는 후보는 감점 또는 제거하고, 남은 후보 여러 갈래를 MHT로 유지하는 live family를 추가한다.

## 설계

1. 기존 `TransparentLiveFamilyPool`의 catalog history와 period 추정을 재사용한다.
2. 각 프레임 후보를 `frame - lag` 배경 후보와 비교해 confirmed decal과 active 후보로 나눈다.
3. active 후보를 `MhtCandidate`로 변환하고, confirmed decal은 기본적으로 제외한다.
4. active 후보가 없을 때만 confirmed decal을 약한 fallback으로 넣는다.
5. `solve_mht`로 최근 window의 최종 path를 풀어 `phase_catalog_mht_center_mild_state_mild` family로 낸다.

## 검증

- synthetic 테스트로 반복 배경 후보가 더 높은 score라도 MHT family가 타겟 후보를 고르는지 확인한다.
- 기존 live family 테스트를 유지한다.
- 16개 GT source upper를 다시 채점한다.
