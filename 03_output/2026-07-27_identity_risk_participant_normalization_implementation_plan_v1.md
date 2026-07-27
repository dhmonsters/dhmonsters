# Identity-Risk Participant Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 흰색 신분이 보이는 접촉을 비채점 처리하고, 실제 identity-risk 병합 사건의 지역 참여 후보 쌍만 기존 H1/H2 판별기에 전달한다.

**Architecture:** 관측 가능성 Gate가 scoreable event 자격을 결정한다. 순수 후보 정규화 모듈은 병합 전 두 역할 예측과 부모 영역을 이용해 사건 지역 검출 제안을 물리 후보로 묶고 가능한 두 후보 쌍을 만든다. replay는 여러 쌍이 모호하면 후속 분리 관측까지 HOLD하며, Gate 통과 전에는 기존 선택 경로를 바꾸지 않는다.

**Tech Stack:** Python 3.14, dataclass/enum/math/statistics, 기존 Candidate와 BinaryMergeIdentityResolver, pytest, Studio JSONL trace.

## Global Constraints

- 실행 중 GT를 사용하지 않는다.
- 고정 좌표, 고정 방향, 절대 프레임 번호를 규칙에 넣지 않는다.
- 병합 부모 중심으로 타겟 위치나 속도를 갱신하지 않는다.
- visible contact는 scoreable event와 실패 진단에 포함하지 않는다.
- 측정 불가 증거는 0점이 아니라 기권한다.
- 모호하면 HOLD한다.
- 마우스 출력과 실제 선택 권한은 계속 끈다.
- 새 외부 의존성을 추가하지 않는다.

---

### Task 1: Identity Observability Gate

**Files:**
- Modify: `maple_bot/core/puzzle/binary_merge_shadow.py`
- Test: `maple_bot/tests/test_binary_merge_shadow.py`

**Interfaces:**
- Consumes: `_FrameRuntime.white_anchor_point`, target selection and candidate geometry.
- Produces: visible contact suppression and the last trusted visible contact snapshot.

- [ ] Write a failing test where a selected white anchor overlaps one background candidate among 30 real candidates and extraction returns no event or failure diagnostic.
- [ ] Run the focused test and verify it fails because the current detector opens a merge.
- [ ] Add a pure `_identity_observable(frame)` predicate requiring the white anchor and selected target to resolve to the same physical candidate.
- [ ] Bypass scoreable event creation while the predicate is true, preserve the latest trusted target/background frame, and keep the detector in a non-risk state.
- [ ] Add a failing transition test where the white anchor disappears while the same contact continues and one identity-risk event opens from the last visible contact snapshot.
- [ ] Implement the transition without using a fixed frame number.
- [ ] Run `test_binary_merge_shadow.py` and commit the source and test.

### Task 2: Pure Event-Local Candidate Normalizer

**Files:**
- Create: `maple_bot/core/puzzle/binary_merge_candidates.py`
- Create: `maple_bot/tests/test_binary_merge_candidates.py`

**Interfaces:**
- Produces: `CandidateCluster`, `CandidatePairHypothesis`, `localize_candidate_pairs()`.
- Consumes: current candidates, `BinaryPremergeSnapshot` compatible role state, parent bboxes, frame shape and elapsed observations.

- [ ] Write failing tests for board distractor invariance, duplicate proposal collapse, distinct nearby-object preservation, missing candidate HOLD and multiple-pair ambiguity.
- [ ] Verify RED because the module does not exist.
- [ ] Implement event-local gates using target prediction, background prediction and parent-region ancestry normalized by stable object diagonal and uncertainty.
- [ ] Implement same-frame duplicate components requiring compatible center distance, IoU and shape; select the highest relative score only as representative.
- [ ] Generate pair hypotheses only from different physical clusters and prune pairs that cannot explain the parent or either role prediction.
- [ ] Return all non-dominated pair hypotheses in deterministic order. Do not choose a target role in this module.
- [ ] Run the new test file and commit the new source and test.

### Task 3: Multi-Pair HOLD and Role Resolution

**Files:**
- Modify: `maple_bot/core/puzzle/binary_merge_shadow.py`
- Modify: `maple_bot/tests/test_binary_merge_shadow.py`
- Test: `maple_bot/tests/test_binary_merge_candidates.py`

**Interfaces:**
- `BinarySplitObservation` stores candidate pair hypotheses and context candidates.
- replay evaluates H1/H2 inside each pair and resolves only when one pair and one role assignment have uncertainty-normalized margins.

- [ ] Write failing tests where two plausible pairs HOLD on the first split observation and a later observation leaves one valid pair that resolves under the same event ID.
- [ ] Verify RED against the current exactly-two contract.
- [ ] Extend split observations without changing GT scoring authority.
- [ ] Evaluate all pair hypotheses with the existing resolver, prune dominated pair decisions and return `pair_ambiguous` HOLD when pair selection is not unique.
- [ ] Preserve `judge_disagreement` HOLD when the pair is unique but H1/H2 roles conflict.
- [ ] Run candidate, identity and shadow tests and commit.

### Task 4: Runtime Replay Integration and Isolation

**Files:**
- Modify: `maple_bot/core/puzzle/binary_merge_shadow.py`
- Modify: `maple_bot/tests/test_binary_merge_shadow.py`

**Interfaces:**
- extraction sends only identity-risk event observations to the local normalizer.
- diagnostics distinguish `visible_contact`, `candidate_absent`, `pair_ambiguous` and `event_detection_failure`.

- [ ] Write failing end-to-end synthetic tests with 30 board candidates, one visible contact and one later identity-risk merge/split.
- [ ] Assert event-outside distractors do not change event ID, pair hypotheses or runtime decision.
- [ ] Integrate the local normalizer and multi-pair replay.
- [ ] Keep post-hoc GT association limited to the selected physical pair and prove runtime replay remains identical under changed GT.
- [ ] Run all binary merge and Studio shadow related tests and commit.

### Task 5: One Identity-Risk Representative Gate

**Files:**
- Modify: `03_output/2026-07-27_identity_risk_participant_normalization_checklist_v1.md`
- Modify: `03_output/2026-07-27_identity_risk_participant_normalization_context-notes_v1.md`
- Create: `03_output/2026-07-27_identity_risk_participant_normalization_validation_v1.md`

**Interfaces:**
- Consumes the existing representative trace and post-hoc score.
- Produces one compact event JSONL and Markdown Gate report.

- [ ] Run the complete related suite and require all tests to pass.
- [ ] Run exactly one first scoreable identity-risk event. Visible contacts do not consume the event limit.
- [ ] Pass only if one physical event is extracted, merged-state target decisions are zero, wrong switches are zero and the correct transfer or safe HOLD is explained.
- [ ] On failure, record exactly one failing stage and stop without a second event, threshold sweep or Studio integration.
- [ ] Commit the validation documents separately from product code.

## Expansion Rule

Task 5 success permits a separate design for opt-in Studio diagnostics. Failure keeps Task 6 and `puzzle.py` selection authority disconnected.
