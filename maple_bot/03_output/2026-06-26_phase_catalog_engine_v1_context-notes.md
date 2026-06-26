# phase-catalog engine 컨텍스트 노트

## 2026-06-26 시작

- `TransparentPuzzleEngine`에는 `BackgroundCatalog` 클래스가 있지만 `update()` 후보 선택에는 쓰이지 않는다.
- `planet_solver_noauth.py`에서는 이 엔진 결과를 `phase_catalog_center_mild_state_mild` 이름으로 selector shadow에 넣고 있다.
- 따라서 현재 live의 `phase_catalog`는 이름과 달리 offline `phase_catalog` 방식이 아니다.
- 다음 수정은 엔진 내부에 catalog 기반 배경 후보 제거를 붙이는 것이다.

## 2026-06-26 결과

- synthetic 테스트에서는 catalog 배경 후보 제거가 의도대로 동작했다.
- 하지만 실제 16개 replay에서는 단순 catalog 제거를 기본 ON으로 두면 위험하다.
- 그래서 `EngineConfig.use_background_catalog`를 추가하고 기본값은 `False`로 두었다.
- 더 큰 발견은 `_transparent_engine_replay_score.py`가 prep_end 이후에도 계속 `white_anchor`를 넣고 있었다는 점이다.
- replay 어댑터를 고쳐 prep_end 이전에만 white anchor를 넘기게 했다.
- 그 결과 엔진이 실제 후보 선택 단계에 들어가자 `transparent_engine`은 0/16, 평균은 `inf`로 매우 나빴다.
- 따라서 현재 엔진 결과를 `phase_catalog_center_mild_state_mild`로 믿고 selector shadow에 넣는 것은 위험하다.
- 다음 단계는 엔진을 selector의 강한 source로 쓰기보다, offline `phase_catalog.run_clip`에 가까운 후보 제거 MHT family를 live family pool에 새로 만드는 쪽이 맞다.
