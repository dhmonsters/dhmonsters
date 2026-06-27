# Task47 8/16 상승 후보 진단 노트

## 현재 기준선

- Task46 이후 `_fast_gt_score.py` 기준 `temporal_identity`는 7/16, 평균 68.9px이다.
- 새로 성공한 판은 `000_0615_022618`이다.
- 남은 실패판 중 raw center oracle이 성공하는 판은 여전히 많다.

## 실패판 관찰

- `000_0614_124417`은 짧은 점프가 아니라 긴 드리프트다.
- 66프레임 이후 기존 경로가 위쪽 데칼 흐름에 붙고, raw 후보에는 정답 근처 후보가 계속 존재한다.
- `background_id`는 대부분 None이라 기존 run penalty가 충분히 걸리지 않는다.
- `000_0614_233218`도 비슷하게 temporal 경로가 한쪽 데칼 흐름에 고정된다.

## 시도한 실험

- 단순 가중치 변경은 8/16을 만들지 못했다.
- `target_support_weight`를 70, 100, 140, 200, 300, 500까지 올려도 성공 개수 상승으로 이어지지 않았다.
- `background_run_weight`, `score_weight`, `accel_weight`, `continuity_weight` 단독 변경도 실패판을 40px 아래로 내리지 못했다.
- expected background 중심 거리 penalty를 추가하는 실험도 `124417`을 64.3px 근처까지만 낮췄다.
- keep, branch, gate, max_candidates를 크게 늘려도 결과가 바뀌지 않았다.
- live `balanced_viterbi` 단일 family는 temporal과 성공 판이 다르지만, 현재 JSONL 재생 경로에서는 단독으로 8/16을 만들지 못했다.
- GT-free runtime selector는 현재 live path pool feature와 맞지 않아 초반부터 raw local-box 계열을 크게 잘못 골랐다.

## 다음 판단

Task47의 다음 구현은 selector 본체를 더 튜닝하는 것이 아니라, 빠르게 반복 가능한 source/family 채점 캐시를 먼저 만드는 것이다.

그 다음 `temporal_identity`, `balanced_viterbi`, `strict_transition_viterbi`, `phase_catalog`, `raw_candidate`의 실제 path를 같은 feature 테이블에 올려 selector 후보를 다시 학습하거나 규칙화한다.

중요한 기준은 GT label을 직접 쓰지 않고도 8/16 이상을 만드는 것이다.
