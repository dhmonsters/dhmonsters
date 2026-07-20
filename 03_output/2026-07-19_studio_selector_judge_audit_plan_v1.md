# Studio Selector Judge Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** selector 오류 211프레임에서 현재 심판 신호의 중복과 정답 가설 판별력을 측정한다.

**Architecture:** `TEMPORAL_SELECTOR`의 보류 가설 중 GT 반경 안의 가설을 정답 가설로만 사후 지정한다. 정답 가설과 실제 선택을 각각 가장 가까운 raw 후보 및 evidence에 연결한 뒤, 후보별 심판 상관도와 쌍별 우세율을 보고한다.

**Tech Stack:** Python 3.14, JSONL, dataclass, openpyxl, unittest/pytest.

## Global Constraints

- GT는 audit의 사후 정답 표시와 채점에만 사용한다.
- solver 선택 로직과 가중치는 이번 audit에서 수정하지 않는다.
- 심판 값이 같은지와 실제 판별력이 있는지를 분리해서 보고한다.
- Markdown와 XLSX를 모두 생성한다.

---

### Task 1: 심판 감사 테스트

**Files:**
- Create: `maple_bot/tests/test_studio_judge_audit.py`
- Create: `maple_bot/core/puzzle/studio_judge_audit.py`

**Interfaces:**
- Consumes: `audit_studio_selector(gt_jsonl, trace_jsonl, output_dir, pass_distance_px=24.0)`.
- Produces: summary dataclass, Markdown, XLSX.

- [ ] selector 오류 한 프레임과 selector 성공 한 프레임이 포함된 synthetic trace 테스트를 작성한다.
- [ ] 테스트가 모듈 부재로 실패하는지 확인한다.
- [ ] selector 오류만 pair audit에 포함하는 최소 구현을 작성한다.

### Task 2: 독립성 및 판별력 집계

**Files:**
- Modify: `maple_bot/core/puzzle/studio_judge_audit.py`
- Test: `maple_bot/tests/test_studio_judge_audit.py`

**Interfaces:**
- Consumes: candidate score와 `bg_score`, `motion_divergence`, `rigid_violation`, `phase_similarity`, `texture_bg_score`, `merge_likelihood`.
- Produces: 심판별 정답 우세율, 평균 차이, Pearson 상관도, exact duplicate 비율.

- [ ] 정답 가설과 실제 선택 후보의 심판 차이를 계산한다.
- [ ] 전체 후보 표본에서 심판 상관도를 계산한다.
- [ ] `motion == rigid`와 `phase == 1-motion` 비율을 계산한다.
- [ ] Markdown와 XLSX에 summary, pair rows, correlations를 기록한다.

### Task 3: 실제 selector 오류 211프레임 감사

**Files:**
- Read: 고정 시드 970점 GT와 trace.
- Create: `03_output/2026-07-19_studio_selector_judge_audit_v1/`.

**Interfaces:**
- Consumes: 실제 1500프레임 trace.
- Produces: 다음 selector 구현 분기 결정 근거.

- [ ] audit 테스트 전체를 실행한다.
- [ ] 실제 trace audit를 실행한다.
- [ ] selector pair 수가 실패 분해의 211과 일치하는지 확인한다.
- [ ] 중복 심판은 한 표로 줄이고 판별력이 있는 독립 신호만 다음 구현 후보로 기록한다.
