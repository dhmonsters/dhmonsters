# phase-catalog live family 컨텍스트 노트

## 2026-06-26 시작

- `TransparentPuzzleEngine`은 단독 replay에서 0/16으로 실사용 source가 되기 어렵다.
- 대신 offline `phase_catalog`의 핵심 규칙을 live family pool에 직접 넣는 쪽이 더 적절하다.
- 목표는 최종 선택을 바꾸는 것이 아니라 selector가 고를 수 있는 source 후보군을 늘리는 것이다.

## 2026-06-26 결과

- `TransparentLiveFamilyPool`에 `phase_catalog_live_center_mild_state_mild` family를 추가했다.
- synthetic 테스트에서는 반복 배경 후보가 제거되고 타겟 후보가 선택된다.
- 16개 GT source upper 기준 `phase_catalog` source는 2/16이다.
- 새로 강하게 해결된 대표 클립은 `000_0615_025624`이고 평균 오차는 local-box 후 12.4px이다.
- `000_0615_042024`도 12.1px로 성공하지만 이미 다른 source도 성공하던 클립이다.
- 전체 source 후보군의 고유 성공은 약 9/16 수준으로 보인다.
- 단일 phase-catalog 경로만으로는 부족하다. 다음은 `decal_filter_mht`처럼 active 후보 여러 갈래를 유지하는 MHT family가 필요하다.
