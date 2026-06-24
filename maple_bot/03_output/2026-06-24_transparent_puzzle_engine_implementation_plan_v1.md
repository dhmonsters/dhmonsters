# Transparent Puzzle Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `planet_solver_noauth.py`의 추적 판단부를 새 투명 도형 퍼즐 엔진으로 분리하고, 오프라인 replay 검증 후 live 연결까지 진행한다.

**Architecture:** `planet_solver_noauth.py`는 UI, 캡처, YOLO 후보 생성, 마우스 이동만 담당한다. 새 파일 `core/vision/transparent_puzzle_engine.py`가 후보 선택, 배경 catalog, merged blob, coast, 재획득 상태를 관리한다. `_transparent_engine_replay_score.py`는 live와 같은 엔진 입력 adapter로 `_record_debug`와 `_gt_frames`를 재생한다.

**Tech Stack:** Python 3, NumPy, OpenCV, 기존 `_phase_catalog_score.py`, 기존 unittest 기반 테스트.

## Global Constraints

- 새 source 파일 첫 줄은 파일 역할을 설명하는 한국어 주석이어야 한다.
- 수동 파일 수정은 `apply_patch`를 사용한다.
- 산출물은 `03_output`에 저장한다.
- 기존 사용자 변경과 무관한 파일은 되돌리지 않는다.
- 오프라인 replay에서 기존 consensus 9/16보다 좋아지기 전까지 새 엔진을 live 기본 경로로 켜지 않는다.
- `planet_solver_noauth.py`는 UI, 캡처, YOLO, 마우스, 녹화 기능을 유지한다.

---

### Task 1: Engine Data Contract

**Files:**
- Create: `core/vision/transparent_puzzle_engine.py`
- Create: `tests/test_transparent_puzzle_engine.py`

**Interfaces:**
- Produces: `PuzzleCandidate(cx: float, cy: float, score: float, w: float = nan, h: float = nan)`.
- Produces: `PuzzleEngineInput(frame_index: int, candidates: list[PuzzleCandidate], white_anchor: tuple[float, float] | None = None, gray_frame: object | None = None)`.
- Produces: `PuzzleEngineOutput(x: float | None, y: float | None, confidence: float, candidate_index: int | None, state: str, debug: dict)`.
- Produces: `TransparentPuzzleEngine.reset() -> None`.
- Produces: `TransparentPuzzleEngine.update(inp: PuzzleEngineInput) -> PuzzleEngineOutput`.

- [ ] **Step 1: Write the failing data contract test.**

```python
def test_white_anchor_wins_during_prep():
    engine = TransparentPuzzleEngine()
    out = engine.update(PuzzleEngineInput(
        frame_index=0,
        candidates=[PuzzleCandidate(100.0, 100.0, 0.8, 40.0, 40.0)],
        white_anchor=(220.0, 180.0),
    ))

    self.assertEqual((out.x, out.y), (220.0, 180.0))
    self.assertEqual(out.state, "white_anchor")
    self.assertIsNone(out.candidate_index)
```

- [ ] **Step 2: Run the test to verify it fails.**

Run: `python -m unittest tests.test_transparent_puzzle_engine`

Expected: FAIL because `core.vision.transparent_puzzle_engine` does not exist.

- [ ] **Step 3: Implement the minimal data classes and white anchor behavior.**

```python
@dataclass(frozen=True)
class PuzzleCandidate:
    cx: float
    cy: float
    score: float
    w: float = float("nan")
    h: float = float("nan")

@dataclass(frozen=True)
class PuzzleEngineInput:
    frame_index: int
    candidates: Sequence[PuzzleCandidate]
    white_anchor: Optional[Point] = None
    gray_frame: object | None = None

@dataclass(frozen=True)
class PuzzleEngineOutput:
    x: Optional[float]
    y: Optional[float]
    confidence: float
    candidate_index: Optional[int]
    state: str
    debug: Dict[str, object]
```

- [ ] **Step 4: Run the test to verify it passes.**

Run: `python -m unittest tests.test_transparent_puzzle_engine`

Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add core/vision/transparent_puzzle_engine.py tests/test_transparent_puzzle_engine.py
git commit -m "feat: add transparent puzzle engine contract"
```

### Task 2: Background Catalog And Period

**Files:**
- Modify: `core/vision/transparent_puzzle_engine.py`
- Modify: `tests/test_transparent_puzzle_engine.py`

**Interfaces:**
- Consumes: `PuzzleCandidate`, `PuzzleEngineInput`.
- Produces: `BackgroundCatalog.add_frame(frame_index: int, candidates: Sequence[PuzzleCandidate]) -> None`.
- Produces: `BackgroundCatalog.estimate_period(prep_end: int) -> tuple[int, float]`.
- Produces: `BackgroundCatalog.expected_candidates(frame_index: int, period: int, local_search: int = 8) -> list[PuzzleCandidate]`.

- [ ] **Step 1: Write period test that rejects `prep_end` as a blind period.**

```python
def test_period_is_measured_from_candidate_repetition():
    catalog = BackgroundCatalog()
    for frame in range(8):
        x = float((frame % 5) * 10)
        catalog.add_frame(frame, [PuzzleCandidate(x, 0.0, 1.0, 20.0, 20.0)])

    period, score = catalog.estimate_period(prep_end=6, min_lag=3, max_lag=6)

    self.assertEqual(period, 5)
    self.assertLess(score, 1.0)
```

- [ ] **Step 2: Run the test to verify it fails.**

Run: `python -m unittest tests.test_transparent_puzzle_engine`

Expected: FAIL because `BackgroundCatalog` is not defined.

- [ ] **Step 3: Implement candidate matching period estimation.**

Use greedy nearest-neighbor matching between candidate centers and choose the lag with the smallest median matched distance.

- [ ] **Step 4: Run the test to verify it passes.**

Run: `python -m unittest tests.test_transparent_puzzle_engine`

Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add core/vision/transparent_puzzle_engine.py tests/test_transparent_puzzle_engine.py
git commit -m "feat: measure transparent puzzle background period"
```

### Task 3: Candidate Score And Coast State

**Files:**
- Modify: `core/vision/transparent_puzzle_engine.py`
- Modify: `tests/test_transparent_puzzle_engine.py`

**Interfaces:**
- Consumes: `TransparentPuzzleEngine.update`.
- Produces: `EngineConfig(max_candidate_jump: float = 115.0, coast_frames: int = 12)`.
- Produces: `state == "candidate"` when a candidate is selected.
- Produces: `state == "coast"` when no candidate is safe and prediction is used.

- [ ] **Step 1: Write candidate continuity test.**

```python
def test_engine_prefers_continuous_candidate():
    engine = TransparentPuzzleEngine()
    engine.update(PuzzleEngineInput(0, [], white_anchor=(100.0, 100.0)))
    out = engine.update(PuzzleEngineInput(1, [
        PuzzleCandidate(108.0, 100.0, 0.4, 30.0, 30.0),
        PuzzleCandidate(220.0, 100.0, 0.99, 30.0, 30.0),
    ]))

    self.assertEqual(out.candidate_index, 0)
    self.assertEqual(out.state, "candidate")
```

- [ ] **Step 2: Write coast test.**

```python
def test_engine_coasts_when_candidates_jump_too_far():
    engine = TransparentPuzzleEngine(EngineConfig(max_candidate_jump=50.0, coast_frames=3))
    engine.update(PuzzleEngineInput(0, [], white_anchor=(100.0, 100.0)))
    engine.update(PuzzleEngineInput(1, [PuzzleCandidate(110.0, 100.0, 0.8, 30.0, 30.0)]))
    out = engine.update(PuzzleEngineInput(2, [PuzzleCandidate(300.0, 300.0, 0.99, 30.0, 30.0)]))

    self.assertEqual(out.state, "coast")
    self.assertAlmostEqual(out.x, 120.0, delta=1.0)
```

- [ ] **Step 3: Run tests to verify failure.**

Run: `python -m unittest tests.test_transparent_puzzle_engine`

Expected: FAIL because continuity and coast are not implemented.

- [ ] **Step 4: Implement velocity state, candidate gate, and coast prediction.**

The engine keeps `last_point`, `velocity`, and `coast_left`. Candidates outside `max_candidate_jump` from predicted point are rejected unless no prior point exists.

- [ ] **Step 5: Run tests to verify pass.**

Run: `python -m unittest tests.test_transparent_puzzle_engine`

Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add core/vision/transparent_puzzle_engine.py tests/test_transparent_puzzle_engine.py
git commit -m "feat: add transparent puzzle continuity coast state"
```

### Task 4: Merged Blob Internal Point State

**Files:**
- Modify: `core/vision/transparent_puzzle_engine.py`
- Modify: `tests/test_transparent_puzzle_engine.py`

**Interfaces:**
- Consumes: `PuzzleCandidate.w`, `PuzzleCandidate.h`.
- Produces: `internal_points(candidate: PuzzleCandidate, grid_size: int = 5, shrink: float = 0.76) -> list[Point]`.
- Produces: `state == "merged_internal"` when the engine uses an internal box point instead of candidate center.

- [ ] **Step 1: Write internal point test.**

```python
def test_internal_points_include_center_and_box_offsets():
    pts = internal_points(PuzzleCandidate(100.0, 100.0, 0.8, 40.0, 20.0), grid_size=3, shrink=0.5)

    self.assertIn((100.0, 100.0), pts)
    self.assertIn((90.0, 95.0), pts)
    self.assertIn((110.0, 105.0), pts)
```

- [ ] **Step 2: Write merged internal selection test.**

```python
def test_merged_candidate_uses_predicted_internal_point():
    engine = TransparentPuzzleEngine(EngineConfig(max_candidate_jump=100.0))
    engine.update(PuzzleEngineInput(0, [], white_anchor=(100.0, 100.0)))
    engine.update(PuzzleEngineInput(1, [PuzzleCandidate(110.0, 100.0, 0.8, 60.0, 60.0)]))
    out = engine.update(PuzzleEngineInput(2, [PuzzleCandidate(160.0, 100.0, 0.8, 120.0, 60.0)]))

    self.assertEqual(out.state, "merged_internal")
    self.assertLess(abs(out.x - 120.0), abs(out.x - 160.0))
```

- [ ] **Step 3: Run tests to verify failure.**

Run: `python -m unittest tests.test_transparent_puzzle_engine`

Expected: FAIL because internal state is not implemented.

- [ ] **Step 4: Implement internal point selection.**

When the nearest candidate box is large enough to contain the predicted point, select the internal grid point nearest to prediction and mark state as `merged_internal`.

- [ ] **Step 5: Run tests to verify pass.**

Run: `python -m unittest tests.test_transparent_puzzle_engine`

Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add core/vision/transparent_puzzle_engine.py tests/test_transparent_puzzle_engine.py
git commit -m "feat: add transparent puzzle merged internal state"
```

### Task 5: Offline Replay Scorer

**Files:**
- Create: `_transparent_engine_replay_score.py`
- Modify: `tests/test_transparent_puzzle_engine.py`

**Interfaces:**
- Consumes: `TransparentPuzzleEngine`.
- Produces: `load_engine_inputs(name: str) -> list[PuzzleEngineInput]`.
- Produces: `score_clip(name: str) -> dict`.
- Produces: CLI output with per-clip mean error and success flag.

- [ ] **Step 1: Write adapter shape test.**

```python
def test_replay_adapter_converts_candidate_tuple():
    candidate = replay.candidate_from_tuple((10.0, 20.0, 0.7, 30.0, 40.0))

    self.assertEqual(candidate.cx, 10.0)
    self.assertEqual(candidate.cy, 20.0)
    self.assertEqual(candidate.score, 0.7)
    self.assertEqual(candidate.w, 30.0)
    self.assertEqual(candidate.h, 40.0)
```

- [ ] **Step 2: Run tests to verify failure.**

Run: `python -m unittest tests.test_transparent_puzzle_engine`

Expected: FAIL because `_transparent_engine_replay_score.py` does not exist.

- [ ] **Step 3: Implement replay adapter and scorer.**

Use `_phase_catalog_score.load_frames`, `load_rows`, `load_wrows`, `detect_prep`, `candidate_sets`, and `load_gt`.

- [ ] **Step 4: Run tests to verify pass.**

Run: `python -m unittest tests.test_transparent_puzzle_engine`

Expected: PASS.

- [ ] **Step 5: Run 16 GT replay.**

Run: `python _transparent_engine_replay_score.py`

Expected: prints all 16 clips and summary. The first implementation is allowed to be below 16/16, but it must not crash.

- [ ] **Step 6: Commit.**

```bash
git add core/vision/transparent_puzzle_engine.py tests/test_transparent_puzzle_engine.py _transparent_engine_replay_score.py
git commit -m "feat: add transparent puzzle replay scorer"
```

### Task 6: Live Shadow Integration

**Files:**
- Modify: `planet_solver_noauth.py`
- Modify: `03_output/2026-06-24_transparent_puzzle_engine_context_notes_v1.md`

**Interfaces:**
- Consumes: `TransparentPuzzleEngine.update`.
- Produces: live debug log showing ByteTracker point and new engine point without changing default mouse target until replay improves.

- [ ] **Step 1: Add engine import and construction near existing tracker setup.**

```python
from core.vision.transparent_puzzle_engine import (
    PuzzleCandidate,
    PuzzleEngineInput,
    TransparentPuzzleEngine,
)
```

- [ ] **Step 2: Convert YOLO candidates to engine candidates inside the tracking loop.**

```python
engine_candidates = [
    PuzzleCandidate(float(cx), float(cy), float(score), float(w), float(h))
    for cx, cy, score, w, h in normalized_candidates
]
```

- [ ] **Step 3: Call engine in shadow mode.**

```python
engine_out = _transparent_engine.update(PuzzleEngineInput(
    frame_index=preview_cnt,
    candidates=engine_candidates,
    white_anchor=white_center,
    gray_frame=gray_for_engine,
))
```

- [ ] **Step 4: Keep existing mouse target unchanged.**

The shadow output is logged and optionally drawn, but it does not replace the existing target until replay score improves.

- [ ] **Step 5: Run syntax check.**

Run: `python -c "import ast, pathlib; ast.parse(pathlib.Path('planet_solver_noauth.py').read_text(encoding='utf-8-sig'))"`

Expected: `ast ok`.

- [ ] **Step 6: Commit.**

```bash
git add planet_solver_noauth.py 03_output/2026-06-24_transparent_puzzle_engine_context_notes_v1.md
git commit -m "feat: shadow transparent puzzle engine in live solver"
```

### Task 7: Remove Dead Live Tracking Options

**Files:**
- Modify: `planet_solver_noauth.py`
- Modify: `03_output/2026-06-24_transparent_puzzle_engine_context_notes_v1.md`

**Interfaces:**
- Consumes: shadow engine from Task 6.
- Produces: smaller live file with obsolete tracking option UI and branch code removed.

- [ ] **Step 1: Remove unused checkbox references.**

Remove live UI and constructor parameters for already obsolete tracking toggles. Keep sound alarm and recording controls.

- [ ] **Step 2: Remove unreachable old experimental branches.**

Only remove branches no longer reachable after the shadow engine path exists.

- [ ] **Step 3: Run syntax check.**

Run: `python -c "import ast, pathlib; ast.parse(pathlib.Path('planet_solver_noauth.py').read_text(encoding='utf-8-sig')); print('ast ok')"`

Expected: `ast ok`.

- [ ] **Step 4: Run focused tests.**

Run: `python -m unittest tests.test_transparent_puzzle_engine tests.test_tracking_alert_gate tests.test_box_grid_viterbi_selector`

Expected: PASS.

- [ ] **Step 5: Commit.**

```bash
git add planet_solver_noauth.py 03_output/2026-06-24_transparent_puzzle_engine_context_notes_v1.md
git commit -m "refactor: remove obsolete transparent tracking controls"
```

## Self-Review

- Spec coverage: 새 엔진 분리, replay 우선, live shadow mode, 불필요 옵션 제거가 각각 Task 1부터 Task 7에 포함됐다.
- Placeholder scan: `TBD`, `TODO`, `implement later` 표현은 사용하지 않았다.
- Type consistency: `PuzzleCandidate`, `PuzzleEngineInput`, `PuzzleEngineOutput`, `TransparentPuzzleEngine.update` 이름을 모든 task에서 동일하게 사용했다.
- Scope check: live 기본 추적 교체는 이번 계획에 넣지 않았다. 오프라인 replay 개선 전에는 shadow mode까지만 진행한다.
