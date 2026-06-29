# 2026-06-29 라이브 경로 게이트 결과

## 완료한 내용

1. 16/16 기준선을 다시 확인했다.
2. `puzzle.py` 라이브 경로가 `PlanetLiveSolver`와 `LiveTemporalSelector`를 통해 judge scoreboard 계열을 쓰는지 테스트로 고정했다.
3. 캡처 ROI와 메인 모니터 선택, F2 solver 정지 후 녹화 유지, F3 녹화 종료 흐름을 테스트로 확인했다.
4. dry-run용 `mouse_enabled` 스위치와 `--live-dry-run` CLI 옵션을 추가했다.

## 검증 결과

- `test_puzzle_planet_live`, `test_puzzle_live_watch`는 17개 테스트 통과.
- `test_transparent_family_selector_runtime`, `test_transparent_selector_shadow`는 70개 테스트 통과.
- 직접 호출 방식의 캡처, ROI, 녹화, CLI dry-run 검증 통과.
- `_live_family_pool_gt_score.py --fast-mode --occlusion-variants --event-gate-shortlist --selector-scoreboard` 결과 `selected_summary 16/16`.
- `_live_temporal_selector_gt_score.py --summary-only` 결과 `summary 16/16`, 평균 오차 `26.3176px`.

## 남은 주의점

현재 Codex 셸에서는 실제 화면 캡처가 실패했다. 실패 내용은 `mss` 모듈 없음과 `ImageGrab` 화면 접근 실패다. 사용자가 실행하는 일반 콘솔에서는 이전처럼 CCTV가 잡혔으므로, 인게임 첫 dry-run은 사용자 콘솔에서 다시 확인해야 한다.
