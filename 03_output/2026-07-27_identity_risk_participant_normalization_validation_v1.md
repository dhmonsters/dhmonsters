# Identity-Risk Participant Normalization Representative Gate

## 판정

`FAIL`.

- Failing stage: `event_detection`.
- Direct reason: `premerge_identity_untrusted`.
- Expansion allowed: `false`.

## 선행 Suite

관련 전체 non-CLI suite를 대표 실행 전에 먼저 수행했다.

```powershell
& 'C:\Users\PC\AppData\Local\Programs\Python\Python314\python.exe' -m pytest tests\test_binary_merge_candidates.py tests\test_binary_merge_background.py tests\test_binary_merge_identity.py tests\test_binary_merge_shadow.py tests\test_puzzle_identity.py tests\test_puzzle_evidence.py tests\test_studio_shadow_validation.py -k 'not cli' -q -p no:cacheprovider
```

결과는 `171 passed, 2 deselected in 1.19s`다.

## 대표 사건

suite 통과 뒤 기존 `core.puzzle.binary_merge_shadow` entrypoint를 `--event-limit 1`로 정확히 한 번 실행했다. visible contact 뒤 첫 제한 단위는 scoreable 물리 사건이 아니라 extraction diagnostic으로 종료됐다.

| 항목 | 결과 |
|---|---|
| JSONL rows | 1 |
| Physical identity-risk events | 0 |
| Extraction diagnostics | 1 |
| Event ID | -1 |
| Premerge/split frame | 70 / 70 |
| Candidate count | 35 |
| Runtime reason | `premerge_identity_untrusted` |
| Split observations evaluated | 0 |
| Merged-state target decisions | 0 |
| Correct transfer | 0 |
| Safe HOLD | 0 |
| Wrong switches | 0 |

정확히 한 개의 물리 identity-risk 사건이 추출되지 않았고, correct transfer 또는 specific reason이 있는 safe HOLD에도 도달하지 못했다. 따라서 Gate 요구를 충족하지 못했다.

## 중단 범위

실패 뒤 두 번째 사건, 파라미터 스윕, Studio batch, selection authority 연결을 수행하지 않았다. post-hoc score는 runtime 사건 검출이나 결정 입력으로 사용하지 않았다.

Compact event JSONL은 `03_output/2026-07-27_identity_risk_participant_normalization_validation_v1/representative_event_001/binary_merge_events.jsonl`에 있다.

## 최종 리뷰 보완 이후 상태

- 최종 리뷰의 Important 4건을 커밋 `643e40f`에서 수정했다.
- 관련 전체 non-CLI suite를 다시 실행해 `178 passed, 2 deselected in 1.52s`를 확인했다.
- 대표 사건은 실험 규칙에 따라 두 번째로 실행하지 않았다.
- 따라서 위의 `premerge_identity_untrusted` Gate FAIL 기록은 유효하며 `expand_allowed=false`도 유지한다.
- 최종 수정은 합성 및 회귀 테스트에서 승인됐지만, 새 코드의 대표 trace Gate 통과를 의미하지 않는다.
