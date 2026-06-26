# decal-filter MHT live family 컨텍스트 노트

## 2026-06-26 시작

- `phase_catalog_live`는 2/16으로 의미 있는 source지만 단일 경로라 한계가 있다.
- 기존 `core.vision.transparent_mht_solver.solve_mht`는 이미 candidate 내부 점과 hidden merge를 다룰 수 있다.
- 새 family는 solve_mht를 재사용해 active 후보 여러 갈래를 보존한다.

## 2026-06-26 결과

- `phase_catalog_mht_center_mild_state_mild` family를 구현하고 synthetic 테스트를 추가했다.
- full local-box source upper는 phase MHT 비용이 너무 커서 중단했다.
- MHT history를 최근 28프레임으로 제한했지만 full source upper는 여전히 실시간 적용 후보로 보기엔 무거웠다.
- base-only 16개 재생에서는 `phase_catalog` 성공 수가 2/16으로 기존 `phase_catalog_live`와 같았다.
- MHT가 best가 된 클립도 있었지만 성공권으로 낮추지 못했다.
- 따라서 `enable_phase_mht=False`를 기본값으로 두고, 실험용 opt-in family로만 유지한다.
- 다음 유효한 방향은 MHT를 더 키우는 것이 아니라 selector가 현재 성공 source를 안정적으로 고르는 문제와, 남은 실패 클립의 새 관측 신호를 따로 만드는 쪽이다.
