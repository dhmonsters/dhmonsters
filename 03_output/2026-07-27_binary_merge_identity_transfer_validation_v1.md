# 이진 병합 대표 사건 Gate 1 검증 보고서

## 판정

- 최종 verdict. `GATE_FAILED`.
- 실패 단계. `candidate normalization`.
- 직접 원인. `duplicate_detection_unresolved`.
- 후속 처리. 사건 확장과 threshold 조정을 즉시 중단했다.

대표 실행의 유일한 JSONL row는 물리 병합 사건이 아니라 `event_id=-1`인 추출 진단이다. 후보 30개를 두 물리 자식으로 정규화하지 못했으므로 Gate 1의 첫 조건을 충족하지 못했다.

## 기계 판정

| Gate 조건 | 측정값 | 결과 |
|---|---:|---|
| 물리 이진 병합 사건 1개 감지 | 0개 | FAIL |
| 병합 중 target 결정 없음 | 결정 frame 없음 | PASS |
| 올바른 split child에 target identity 전달 | 판정 불가 | FAIL |
| wrong switch | 0개 | PASS |
| GT 변경 시 runtime replay 동일 | focused test 통과 | PASS |

기계 판정 결과는 `GATE_FAILED`이며 실패 단계 매핑은 `duplicate_detection_unresolved`에서 `candidate normalization`이다.

## 대표 사건 Counts

| 항목 | 값 |
|---|---:|
| event rows | 1 |
| physical events | 0 |
| extraction diagnostics | 1 |
| duplicate detection unresolved | 1 |
| candidate count | 30 |
| resolved events | 0 |
| correct transfer | 0 |
| wrong switches | 0 |
| safe hold | 0 |
| late recovery | 0 |
| target not in candidates | 0 |
| event detection failure | 0 |

## 출력 계약

- `runtime_decision`이 존재하며 `hold=true`, `reason=duplicate_detection_unresolved`이다.
- `post_hoc_score`가 존재하며 outcome은 `duplicate_detection_unresolved`이다.
- `judge_diagnostics`가 존재하며 source, extraction reason, candidate count를 기록했다.
- candidate normalization 단계에서 중단되어 H1/H2 judge decision은 생성되지 않았다.
- mouse action field는 없다.
- 생성 파일은 2개이며 비디오 0개, 이미지 0개다.

생성 파일은 다음 두 개다.

- `C:\Users\PC\Desktop\02_work\05_AI\03_output\2026-07-27_binary_merge_identity_transfer_validation_v1\representative_event_001\binary_merge_events.jsonl`.
- `C:\Users\PC\Desktop\02_work\05_AI\03_output\2026-07-27_binary_merge_identity_transfer_validation_v1\representative_event_001\binary_merge_validation.md`.

## 입력과 실행

- trace. `C:\Users\PC\Desktop\02_work\05_AI\03_output\2026-07-20_studio_hypothesis_live_validation_v1\20260720_143934_studio\sessions\2026-07-20_transparent_puzzle_sessions\20260720_143937_001\trace.jsonl`.
- score. `C:\Users\PC\Desktop\02_work\05_AI\03_output\2026-07-20_studio_hypothesis_live_validation_v1\20260720_143934_studio\validation_partial\score.jsonl`.
- output. `C:\Users\PC\Desktop\02_work\05_AI\03_output\2026-07-27_binary_merge_identity_transfer_validation_v1\representative_event_001`.
- event limit. `1`.
- 대표 사건 실행 횟수. 정확히 1회.

## 코드 검증

- focused suite. `270 passed, 37 subtests passed in 6.65s`.
- CLI dry-run RED. CLI 진입점 부재로 출력 디렉터리가 생성되지 않아 실패했다.
- CLI dry-run GREEN. `1 passed in 0.51s`.
- runtime GT separation. `test_event_replay_stays_byte_equivalent_when_post_hoc_gt_changes`가 focused suite에서 통과했다.
- 코드와 테스트 커밋. `1f111cee68c662c65d1eb895cc025c0e41e72148`.

## 중단 기록

Gate 실패 후 두 번째 사건을 실행하지 않았고 event detection, judge, ancestry 관련 threshold를 변경하지 않았다. Task 6 이후 확장은 수행하지 않는다.

## 검증 후 CLI 계약 보완

대표 사건은 다시 실행하지 않았다. 합성 회귀 테스트에서 `--event-limit 1`이 첫 사건 또는 진단 이후 extraction과 resolver 계산 자체를 중단하는지 확인했다. CLI 출력에는 `gate_verdict`, canonical `failure_stage`, `expand_allowed`를 추가했다.

보완 커밋은 `0cf0f835c7a0f80d9bbd538dda8bf6842317c556`이다. 최종 관련 테스트는 `273 passed, 37 subtests passed`다. 이 보완은 기존 대표 사건의 `GATE_FAILED`, `candidate normalization` 판정을 바꾸지 않는다.
