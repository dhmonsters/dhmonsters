# GT 성능 확인 결과

## 실행 목적
- 실전 녹화 테스트 전에 현재 추적 성능 수준을 먼저 확인했다.
- 대상은 기존 16개 빨간점 GT다.

## 실행 결과

### 1. live selector shadow replay
- 명령: `_selector_shadow_gt_replay_score.py`
- full local-box 포함 실행은 3분 이상 걸려 중단했다.
- `--no-local-box` 실행도 90초 이상 걸려 중단했다.
- 결론: 현재 이 러너는 즉시 성능 점검용으로 너무 무겁다. 빠른 리포트용 별도 경량화가 필요하다.

### 2. live source 상한 빠른 채점
- 명령: `_live_source_upper_score.py --raw-fast --no-local-box`
- 성공 기준: 평균 오차 40px 이하, GT frame coverage 90% 이상.
- 결과.
  - `raw_candidate`: 5/16.
  - `balanced_viterbi`: 2/16.
  - `strict_transition_viterbi`: 1/16.
  - `panel_default`: 0/16.
- 해석: 현재 live family 단독 경로는 아직 실전 추적기로 보기 어렵다.

### 3. 캐시 기반 offline teacher
- 명령: `solve_cached_16gt(DEFAULT_CACHE_PATH)`.
- 결과: 16/16, 평균 30.81px.
- 해석: 저장된 16GT feature cache와 GT label을 쓰는 teacher 상한은 좋다.
- 단, 이 결과는 실시간 live 최종 selector 성능이 아니라 cache 기반 재현 성능이다.

### 4. GT-free cached selector
- `select_cached_rows_without_gt`는 offline teacher와 같은 family 이름을 고른다.
- 출력 row에는 `mean`, `success` label이 없어서 `summarize_selected_rows` 결과는 성능값으로 해석하면 안 된다.

## 현재 판단
- 검출 후보와 캐시 기반 선택 재료는 충분히 강하다.
- 지금 병목은 live replay에서 candidate family를 빠르게 만들고, 그중 올바른 family를 실시간으로 고르는 부분이다.
- 다음 작업은 GT 성능을 UI/CLI에서 빠르게 볼 수 있는 경량 GT 러너를 만드는 것이다.

## 다음 우선순위
1. `_selector_shadow_gt_replay_score.py`를 빠른 모드로 분해한다.
2. local-box 후보 family 수, frame stride, clip limit을 명시 옵션으로 넣는다.
3. UI에 `GT 테스트` 버튼을 붙이기 전에 CLI에서 16개 GT 결과가 1분 이내에 나오게 한다.
