# 2026-06-29 라이브 identity carryover 컨텍스트

## 고정 정의

프레임별로 그 순간 제일 그럴듯한 점을 찍는 솔버가 아니라, 처음 타겟의 신분을 시간축에서 보류하고 복원할 수 있는 판별기를 만든다.

## 현재 사실

오프라인 `_live_family_pool_gt_score.py --fast-mode --occlusion-variants --event-gate-shortlist --selector-scoreboard`는 16/16을 유지한다. 하지만 실제 `LiveTemporalSelector`를 replay하는 `_live_temporal_selector_gt_score.py --summary-only --names 000_0614_121417`는 평균 오차 113.04px로 실패한다.

이 차이는 live 경로가 아직 오프라인 전체 path pool의 정보를 충분히 causal하게 복원하지 못한다는 뜻이다. 다음 진단은 오프라인 성공 후보가 live window 안에 존재하는지부터 확인하는 것이다.

## 2026-06-29 진행 메모

가상 family 좌표 누락을 확인했다. selector runtime은 `box_switch`처럼 점수판에서 새로 만든 family를 고를 수 있었지만, selector shadow는 원래 path pool에서만 좌표를 찾아서 선택 family와 실제 point가 어긋났다.

runtime이 augmented path pool의 최신 좌표를 `point`와 `rescue_point`로 내려주게 했고, shadow는 이 좌표를 원본 path 조회보다 우선 사용하게 했다.

live 기본 family pool을 오프라인 fast 검증 경로와 맞췄다. phase catalog와 guarded decal은 기본 live 경로에서 끄고, raw continuity 20개와 제한된 box-relative pair만 사용한다.

box_grid가 cont12에 잠기는 구간을 풀기 위해 trusted rescue 순서를 추가했다. cont2 switch, cont2 rel, cont0 center, cont0 switch 순서로 살펴본다. cont2 rel이 살아 있으면 cont0 fallback은 막고, cont2 rel 점수가 너무 안정적인 경우는 배경 후보로 보고 rescue하지 않는다.

검증 결과 `000_0614_111417`과 `000_0614_121417`은 기본 live replay에서 성공했다. 전체 16개 GT는 2/16이다. 오프라인 score selector는 여전히 16/16이므로 다음 문제는 최종 후보 부족이 아니라 live causal window에서 언제 가족을 갈아탈지 정하는 상태 유지 문제다.

관련 단위 테스트 52개가 통과했다. 오프라인 fast selector score는 `summary 16/16`, `selected_summary 16/16`을 유지했다. 기본 live replay 전체는 `success 2/16`, 평균 246.80px이다.

다음 우선 대상은 `000_0614_220518`이다. 현재 평균 65.62px이고, 56~69프레임은 성공권이지만 70프레임 이후 cont2 rel/switch로 다시 넘어가며 실패한다. 이 판은 cont12 p05_z0 보호 또는 family 상태 유지 규칙을 추가하면 가장 먼저 성공권에 들어올 가능성이 높다.
