# Studio Bottleneck Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 현재 970/1500 trace의 실패 530개를 selector, hypothesis generation, box center, candidate absent 네 단계로 완전 분해한다.

**Architecture:** 기존 Studio 채점기의 `CandidateCoverageSummary`를 확장한다. `TEMPORAL_SELECTOR.debug.kinematic_wide_beam_points`를 보류 가설로 읽고, 실패 프레임마다 보류 가설, raw 중심, raw 박스 순서로 판정한다.

**Tech Stack:** Python 3.14, dataclass, JSONL trace, unittest/pytest, openpyxl.

## Global Constraints

- GT는 실행 후 채점에서만 사용한다.
- solver 선택 로직과 후보 생성 로직은 이번 작업에서 수정하지 않는다.
- 기존 candidate coverage 필드는 유지한다.
- 네 실패 분류의 합은 `failed_frames`와 같아야 한다.
- 산출물은 `C:/Users/PC/Desktop/02_work/05_AI/03_output`에 저장한다.

---

### Task 1: 네 단계 분해 회귀 테스트

**Files:**
- Modify: `maple_bot/tests/test_studio_validation.py`
- Test: `maple_bot/tests/test_studio_validation.py`

**Interfaces:**
- Consumes: `score_studio_session(gt_jsonl, trace_jsonl, output_dir, pass_distance_px=...)`.
- Produces: `CandidateCoverageSummary.failed_selector_frames`, `failed_hypothesis_generation_frames`.

- [ ] 네 종류의 실패 프레임을 하나씩 만드는 테스트를 작성한다.
- [ ] 테스트를 실행해 새 필드가 없어 실패하는지 확인한다.
- [ ] 기존 center, box, absent 집계도 같은 테스트에서 유지되는지 확인한다.

### Task 2: TEMPORAL_SELECTOR 보류 가설 집계

**Files:**
- Modify: `maple_bot/core/puzzle/studio_validation.py`
- Test: `maple_bot/tests/test_studio_validation.py`

**Interfaces:**
- Consumes: `TEMPORAL_SELECTOR.payload.debug.kinematic_wide_beam_points`.
- Produces: frame index별 `tuple[(x, y), ...]` 보류 가설.

- [ ] trace에서 보류 가설 점을 안전하게 읽는 작은 helper를 추가한다.
- [ ] 실패 프레임을 retained hypothesis, raw center, raw box, absent 순서로 분류한다.
- [ ] `failed_selector_frames + failed_hypothesis_generation_frames`가 기존 `failed_center_recoverable_frames`와 같은지 검증한다.
- [ ] Markdown와 XLSX candidate coverage에 새 필드를 자동 노출한다.

### Task 3: 실제 970 trace 검증

**Files:**
- Read: `maple_bot/03_output/2026-07-19_studio_fixed_seed_observation_consensus_v1/20260719_220837_studio/studio_gt.jsonl`
- Read: `maple_bot/03_output/2026-07-19_studio_fixed_seed_observation_consensus_v1/20260719_220837_studio/sessions/2026-07-19_transparent_puzzle_sessions/20260719_220839_001/trace.jsonl`
- Create: `03_output/2026-07-19_studio_bottleneck_decomposition_v1/`

**Interfaces:**
- Consumes: 고정 시드 1500프레임 GT와 solver trace.
- Produces: `studio_validation.md`, `studio_validation.xlsx`, `studio_score.jsonl`.

- [ ] 관련 Studio validation 테스트 전체를 실행한다.
- [ ] 실제 trace를 새 output 경로에 재채점한다.
- [ ] 네 실패 분류 합이 530인지 확인한다.
- [ ] 가장 큰 분류를 다음 구현 분기로 문서에 기록한다.
- [ ] 변경 파일만 경로 제한 커밋한다.
