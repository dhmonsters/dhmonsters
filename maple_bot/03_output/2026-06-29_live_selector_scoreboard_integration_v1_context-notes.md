# 2026-06-29 라이브 selector 점수판 연결 컨텍스트

## 고정 정의

프레임별로 그 순간 제일 그럴듯한 점을 찍는 솔버가 아니라, 처음 타겟의 신분을 시간축에서 보류하고 복원할 수 있는 판별기를 만든다.

## 판단

오프라인 16/16의 핵심은 정답 좌표를 외우는 것이 아니라, 후보 family들 사이에서 시간축 점수판이 정체성 유지 후보를 골라낸다는 점이다. 따라서 `puzzle.py`로 바로 새 로직을 복붙하는 대신 이미 라이브 경로에 있는 `TransparentFamilySelectorRuntime.select_from_path_pool()`에 연결하는 것이 맞다.

## 원인

`TransparentFamilySelectorRuntime`에서 `_live_family_pool_gt_score`를 top-level로 import하려고 하면 `_selector_shadow_backfill`이 다시 `TransparentFamilySelectorRuntime`을 import하는 순환 구조가 생긴다. 이 때문에 보호 import가 실패하고, 라이브 런타임에서는 judge scoreboard가 조용히 꺼져 있었다.

## 수정 방향

점수판 함수는 모듈 로딩 시점이 아니라 실제 `_select_scoreboard_family()` 호출 시점에 lazy import한다. 이렇게 하면 라이브 런타임 모듈이 먼저 안정적으로 로드되고, selector 호출 시점에는 순환 참조가 풀린다.

## 테스트 설계

테스트는 기존 모델이 `rank_rough` 기준으로 약한 center 후보를 고를 수 있는 상황을 만들고, judge scoreboard rescue가 `raw_candidate_cont2_box_switch_p1_p05_to_n05_z0_at1_state_mild` 후보를 선택해야 통과하도록 만들었다. 이 케이스는 “기존 선택기는 애매하지만 시간축 점수판은 switch 후보를 강하게 보는 상황”을 의미한다.

## 검증 결과

- `test_transparent_family_selector_runtime`, `test_transparent_selector_shadow`, `test_puzzle_planet_live`, `test_selector_judge_scoreboard`, `test_live_family_pool_gt_score` 총 77개 테스트 통과.
- `_live_family_pool_gt_score.py --fast-mode --occlusion-variants --event-gate-shortlist --selector-scoreboard` 결과 `selected_summary 16/16` 유지.

## 라이브 replay 추가 진단

`_live_temporal_selector_gt_score.py --summary-only --names 000_0614_121417` 기준 현재 causal live 경로는 평균 오차 113.04px로 실패한다. 오프라인 16/16과 다른 이유는 live selector가 매 프레임 현재까지의 shadow window로만 고르고, 오프라인 채점은 전체 recording path pool과 더 풍부한 expected background 신호를 사용하기 때문이다.

점수판이 선택을 끝냈는데도 기존 모델용 feature row를 300개 이상 다시 계산하면서 업데이트 1회가 4초에서 9초까지 느려지는 병목이 있었다. 점수판 선택이 있으면 feature row 계산을 건너뛰게 바꾼 뒤 같은 25프레임 샘플에서 0.06초에서 0.12초 수준으로 내려왔다.

live expected background 전달 경로는 옵션으로 추가했지만 기본값은 꺼두었다. 현재 live catalog expected를 바로 켜면 `000_0614_121417` 평균 오차가 159.07px로 악화되어, 이 신호는 품질 검증과 제한 조건이 더 필요하다.
