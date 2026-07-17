# Studio Puzzle Visual Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Studio가 만든 테스트 판을 `puzzle.py`가 마우스 출력 없이 추적하고, 정답 경로와 선택 표적 경로를 자동 비교하는 검증 하네스를 만든다.

**Architecture:** 기존 `LiveRecordingRuntime`은 그대로 사용하고, 검증용 trace event와 Studio GT export를 추가한다. 이후 `studio_validation.py`가 두 JSONL을 비교하고, `retention.py`가 대용량 영상을 정리한다.

**Tech Stack:** Python 3, pytest, OpenCV, openpyxl, JSONL, 기존 `puzzle.py` CLI, Lie Captcha Studio 단일 HTML.

## Global Constraints

- 메모리 읽기, DLL 주입, 커널 드라이버, 원격 코드 실행은 사용하지 않는다.
- 검증 중 마우스 제어는 항상 OFF로 강제한다.
- 영상은 임시 증거로 취급하고, 최종 기록은 간략 보고서와 핵심 이미지 중심으로 남긴다.
- 전체 영상은 최신 N개 세션과 사용자가 잠금 표시한 세션만 보존한다.
- 기존 대량 변경과 삭제 staged 상태는 건드리지 않고, 각 task 파일만 `git commit --only`로 커밋한다.

---

## File Structure

- Modify `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/core/puzzle/live_recording.py`.
  - 검증 모드에서 매 프레임 `SOLVER_VISUAL_TRACE`와 `VISUAL_CHECK_GUARD` event를 남긴다.

- Modify `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/puzzle.py`.
  - 시각 검증 채점 CLI와 보존 정책 CLI를 연결한다.

- Modify `C:/Users/PC/Desktop/02_work/05_AI/.claude/worktrees/video-file-analysis-7e6ee6/lie_captcha_studio/index.html`.
  - Studio 내부 정답 경로를 테스트 API와 console JSONL 형태로 노출한다.

- Create `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/core/puzzle/studio_validation.py`.
  - Studio GT JSONL, solver visual trace, score JSONL, xlsx report를 담당한다.

- Create `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/core/puzzle/retention.py`.
  - 세션 영상 보존과 삭제 후보 계산을 담당한다.

- Modify tests under `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/tests`.
  - 검증 trace, Studio export marker, score report, retention policy, CLI wiring을 검증한다.

---

### Task 1: Visual Trace Guard

**Files:**
- Modify: `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/core/puzzle/live_recording.py`
- Test: `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/tests/test_puzzle_target_visual_check.py`

**Interfaces:**
- Consumes: `PlanetLiveResult.decision`, `PlanetLiveResult.temporal_decision`, `PlanetLiveResult.mouse_move`, `PlanetLiveResult.candidates`.
- Produces: trace events `SOLVER_VISUAL_TRACE` and `VISUAL_CHECK_GUARD`.

- [ ] **Step 1: Write the failing test for visual trace payload.**

Add this test to `test_puzzle_target_visual_check.py`.

```python
def test_visual_check_writes_solver_trace_and_mouse_guard(tmp_path):
    from types import SimpleNamespace
    from core.puzzle.models import Candidate
    from core.puzzle.planet_live import MouseMoveResult, PlanetLiveResult

    class _FakeSolver:
        mouse_enabled = False

        def analyze(self, packet, *, solver_running: bool):
            return PlanetLiveResult(
                candidates=[
                    Candidate(
                        candidate_id="c0",
                        frame_index=packet.frame_index,
                        bbox=(10.0, 20.0, 30.0, 40.0),
                        center=(20.0, 30.0),
                        score=0.9,
                        source="test",
                    )
                ],
                decision=SimpleNamespace(
                    point=(20.0, 30.0),
                    candidate_id="c0",
                    confidence=0.75,
                    reason="unit_test",
                ),
                temporal_decision=SimpleNamespace(
                    point=(21.0, 31.0),
                    family="unit_family",
                    reason="temporal_unit",
                ),
                mouse_move=MouseMoveResult(
                    moved=False,
                    abs_point=None,
                    client_point=None,
                    det_point=(20.0, 30.0),
                    offset=(0.0, 0.0),
                    reason="disabled",
                ),
            )

    runtime = LiveRecordingRuntime(
        output_root=tmp_path,
        frame_grabber=lambda: np.zeros((80, 120, 3), dtype=np.uint8),
        fps=10.0,
        sleeper=lambda _seconds: None,
        live_solver=_FakeSolver(),
        mouse_enabled=True,
        visual_check_mode=True,
    )

    session = runtime.start()
    runtime.stop_recording(reason="unit")
    runtime.finish(reason="unit")

    events = _events(session.trace_path)
    visual = [event for event in events if event["type"] == "SOLVER_VISUAL_TRACE"]
    guard = [event for event in events if event["type"] == "VISUAL_CHECK_GUARD"]
    assert visual[0]["payload"]["selected_x"] == 20.0
    assert visual[0]["payload"]["selected_y"] == 30.0
    assert visual[0]["payload"]["candidate_count"] == 1
    assert visual[0]["payload"]["mouse_enabled"] is False
    assert visual[0]["payload"]["mouse_reason"] == "disabled"
    assert guard[0]["payload"]["mouse_enabled"] is False
    assert guard[0]["payload"]["safe"] is True
```

- [ ] **Step 2: Run the test to verify it fails.**

Run from `C:/Users/PC/Desktop/02_work/05_AI/maple_bot`.

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests/test_puzzle_target_visual_check.py::PuzzleTargetVisualCheckTest::test_runtime_visual_check_mode_disables_mouse tests/test_puzzle_target_visual_check.py::test_visual_check_writes_solver_trace_and_mouse_guard -q
```

Expected: FAIL because `SOLVER_VISUAL_TRACE` is not written yet.

- [ ] **Step 3: Add trace payload helpers.**

Add these helpers near `_analyze_live_frame` in `live_recording.py`.

```python
def _solver_visual_trace_payload(result: PlanetLiveResult, *, mouse_enabled: bool) -> dict[str, object]:
    decision = result.decision
    temporal = result.temporal_decision
    mouse = result.mouse_move
    point = _result_point(decision)
    temporal_point = _result_point(temporal)
    return {
        "selected_x": point[0] if point is not None else None,
        "selected_y": point[1] if point is not None else None,
        "candidate_id": str(getattr(decision, "candidate_id", "") or ""),
        "confidence": _optional_float(getattr(decision, "confidence", None)),
        "reason": str(getattr(decision, "reason", "") or ""),
        "candidate_count": len(result.candidates),
        "temporal_x": temporal_point[0] if temporal_point is not None else None,
        "temporal_y": temporal_point[1] if temporal_point is not None else None,
        "temporal_family": str(getattr(temporal, "family", "") or ""),
        "temporal_reason": str(getattr(temporal, "reason", "") or ""),
        "mouse_enabled": bool(mouse_enabled),
        "mouse_moved": bool(getattr(mouse, "moved", False)),
        "mouse_reason": str(getattr(mouse, "reason", "") or ""),
    }


def _visual_check_guard_payload(*, visual_check_mode: bool, mouse_enabled: bool, result: PlanetLiveResult) -> dict[str, object]:
    mouse = result.mouse_move
    mouse_moved = bool(getattr(mouse, "moved", False))
    safe = (not visual_check_mode) or ((not mouse_enabled) and (not mouse_moved))
    return {
        "visual_check_mode": bool(visual_check_mode),
        "mouse_enabled": bool(mouse_enabled),
        "mouse_moved": mouse_moved,
        "safe": safe,
    }


def _result_point(value: object) -> tuple[float, float] | None:
    point = getattr(value, "point", None)
    if isinstance(point, (list, tuple)) and len(point) >= 2:
        return (float(point[0]), float(point[1]))
    return None


def _optional_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None
```

- [ ] **Step 4: Write the events from `_analyze_live_frame`.**

At the end of `_analyze_live_frame`, after existing `result.trace_events` are written, add this block.

```python
        self.trace.write_event(
            "SOLVER_VISUAL_TRACE",
            packet.frame_index,
            _solver_visual_trace_payload(result, mouse_enabled=self.mouse_enabled),
        )
        self.trace.write_event(
            "VISUAL_CHECK_GUARD",
            packet.frame_index,
            _visual_check_guard_payload(
                visual_check_mode=self.visual_check_mode,
                mouse_enabled=self.mouse_enabled,
                result=result,
            ),
        )
```

- [ ] **Step 5: Run tests and commit.**

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests/test_puzzle_target_visual_check.py tests/test_puzzle_live_recording.py -q
git add -- core/puzzle/live_recording.py tests/test_puzzle_target_visual_check.py
git commit --only -m "검증 모드 표적 trace 추가" -- core/puzzle/live_recording.py tests/test_puzzle_target_visual_check.py
```

Expected: PASS.

---

### Task 2: Studio GT Export Surface

**Files:**
- Modify: `C:/Users/PC/Desktop/02_work/05_AI/.claude/worktrees/video-file-analysis-7e6ee6/lie_captcha_studio/index.html`
- Test: `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/tests/test_studio_gt_export_static.py`

**Interfaces:**
- Produces: browser global `window.__lieCaptchaGtFrames`.
- Produces: browser global function `window.__lieCaptchaExportGt()`.
- Produces: console line prefix `__LIE_GT__`.

- [ ] **Step 1: Write static tests for Studio export markers.**

Create `test_studio_gt_export_static.py`.

```python
# Lie Captcha Studio GT export 표면이 유지되는지 정적으로 확인한다.
from pathlib import Path


STUDIO_HTML = Path(__file__).resolve().parents[2] / ".claude" / "worktrees" / "video-file-analysis-7e6ee6" / "lie_captcha_studio" / "index.html"


def test_studio_exposes_gt_export_api():
    text = STUDIO_HTML.read_text(encoding="utf-8")

    assert "window.__lieCaptchaGtFrames" in text
    assert "window.__lieCaptchaExportGt" in text
    assert "__LIE_GT__" in text
    assert "emitGtFrame" in text
```

- [ ] **Step 2: Run the test to verify it fails.**

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests/test_studio_gt_export_static.py -q
```

Expected: FAIL because the Studio HTML does not expose the GT export API yet.

- [ ] **Step 3: Add GT export state to `index.html`.**

Near the existing `state` object and `targetPos(f)` function, add this script code.

```javascript
const TEST_PARAMS = new URLSearchParams(window.location.search);
const GT_EXPORT_ENABLED = TEST_PARAMS.get('export_gt') === '1';
window.__lieCaptchaGtFrames = window.__lieCaptchaGtFrames || [];

function currentGtFrame(){
  const f = state.frame;
  const [tx, ty] = targetPos(f);
  const rect = cv.getBoundingClientRect();
  return {
    run_id: TEST_PARAMS.get('run_id') || 'manual',
    frame_id: f,
    target_x: tx,
    target_y: ty,
    canvas_rect: [rect.left, rect.top, rect.width, rect.height],
    shape: SHAPES[state.shapeIdx] || '',
    level: state.level,
    seed: TEST_PARAMS.get('seed') || '',
  };
}

function emitGtFrame(){
  if(!GT_EXPORT_ENABLED) return;
  const record = currentGtFrame();
  window.__lieCaptchaGtFrames.push(record);
  window.dispatchEvent(new CustomEvent('lieCaptchaGtFrame', {detail: record}));
  console.log('__LIE_GT__' + JSON.stringify(record));
}

window.__lieCaptchaExportGt = function(){
  return window.__lieCaptchaGtFrames.slice();
};
```

- [ ] **Step 4: Emit GT after render changes.**

At the end of `render()`, after drawing completes, call `emitGtFrame()`.

```javascript
  emitGtFrame();
```

- [ ] **Step 5: Add optional autoplay query params.**

After the existing UI setup, add this block.

```javascript
if(TEST_PARAMS.get('autoplay') === '1'){
  const requestedFps = Number(TEST_PARAMS.get('fps') || state.fps);
  if(Number.isFinite(requestedFps) && requestedFps > 0){
    state.fps = requestedFps;
    fpsEl.value = String(requestedFps);
    fpsVal.textContent = String(requestedFps);
  }
  if(!state.playing){
    btnPlay.click();
  }
}
```

- [ ] **Step 6: Run tests and commit.**

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests/test_studio_gt_export_static.py -q
git add -- .claude/worktrees/video-file-analysis-7e6ee6/lie_captcha_studio/index.html maple_bot/tests/test_studio_gt_export_static.py
git commit --only -m "Studio GT export 표면 추가" -- .claude/worktrees/video-file-analysis-7e6ee6/lie_captcha_studio/index.html maple_bot/tests/test_studio_gt_export_static.py
```

Expected: PASS.

---

### Task 3: Validation Scorer And Excel Report

**Files:**
- Create: `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/core/puzzle/studio_validation.py`
- Test: `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/tests/test_studio_validation.py`

**Interfaces:**
- Consumes: Studio GT JSONL records with `frame_id`, `target_x`, `target_y`.
- Consumes: solver trace event JSONL records with type `SOLVER_VISUAL_TRACE`.
- Produces: `score.jsonl`, `studio_validation.xlsx`, `studio_validation.md`.

- [ ] **Step 1: Write failing tests for scoring and xlsx report.**

Create `test_studio_validation.py`.

```python
# Studio GT와 solver trace를 비교하는 채점기를 검증한다.
import json

from openpyxl import load_workbook

from core.puzzle.studio_validation import score_studio_session


def _write_jsonl(path, rows):
    with path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row, ensure_ascii=False))
            fp.write("\n")


def test_score_studio_session_writes_jsonl_xlsx_and_summary(tmp_path):
    gt_path = tmp_path / "gt.jsonl"
    trace_path = tmp_path / "trace.jsonl"
    out_dir = tmp_path / "report"
    _write_jsonl(gt_path, [
        {"run_id": "r1", "frame_id": 0, "target_x": 10, "target_y": 10},
        {"run_id": "r1", "frame_id": 1, "target_x": 20, "target_y": 20},
    ])
    _write_jsonl(trace_path, [
        {"type": "SOLVER_VISUAL_TRACE", "frame_index": 0, "payload": {"selected_x": 13, "selected_y": 14, "mouse_enabled": False, "candidate_count": 2}},
        {"type": "SOLVER_VISUAL_TRACE", "frame_index": 1, "payload": {"selected_x": 80, "selected_y": 80, "mouse_enabled": False, "candidate_count": 1}},
    ])

    result = score_studio_session(gt_path, trace_path, out_dir, pass_distance_px=10.0)

    assert result.summary.total_frames == 2
    assert result.summary.passed_frames == 1
    assert result.summary.failed_frames == 1
    assert result.score_jsonl.exists()
    assert result.xlsx_path.exists()
    assert result.report_path.exists()
    workbook = load_workbook(result.xlsx_path)
    assert "summary" in workbook.sheetnames
    assert "frames" in workbook.sheetnames
```

- [ ] **Step 2: Run the test to verify it fails.**

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests/test_studio_validation.py -q
```

Expected: FAIL because `core.puzzle.studio_validation` does not exist.

- [ ] **Step 3: Create `studio_validation.py`.**

Implement this minimal module.

```python
# Studio 정답 경로와 puzzle.py 선택 표적 경로를 비교해 검증 리포트를 만든다.
from __future__ import annotations

import json
from dataclasses import dataclass
from math import hypot
from pathlib import Path
from typing import Any

from openpyxl import Workbook


@dataclass(frozen=True)
class ScoreFrame:
    run_id: str
    frame_id: int
    distance_px: float | None
    passed: bool
    fail_reason: str
    target_x: float | None
    target_y: float | None
    selected_x: float | None
    selected_y: float | None
    candidate_count: int
    mouse_enabled: bool


@dataclass(frozen=True)
class ScoreSummary:
    total_frames: int
    passed_frames: int
    failed_frames: int
    max_distance_px: float
    pass_rate: float


@dataclass(frozen=True)
class StudioValidationResult:
    summary: ScoreSummary
    frames: list[ScoreFrame]
    score_jsonl: Path
    xlsx_path: Path
    report_path: Path


def score_studio_session(
    gt_jsonl: str | Path,
    solver_trace_jsonl: str | Path,
    output_dir: str | Path,
    *,
    pass_distance_px: float = 24.0,
) -> StudioValidationResult:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    gt_rows = {int(row["frame_id"]): row for row in _read_jsonl(Path(gt_jsonl))}
    solver_rows = _solver_rows_by_frame(Path(solver_trace_jsonl))
    frames = [
        _score_frame(frame_id, gt_rows.get(frame_id), solver_rows.get(frame_id), pass_distance_px=pass_distance_px)
        for frame_id in sorted(gt_rows)
    ]
    summary = _summary(frames)
    score_jsonl = output / "score.jsonl"
    xlsx_path = output / "studio_validation.xlsx"
    report_path = output / "studio_validation.md"
    _write_score_jsonl(score_jsonl, frames)
    _write_xlsx(xlsx_path, summary, frames)
    report_path.write_text(_render_report(summary), encoding="utf-8")
    return StudioValidationResult(summary, frames, score_jsonl, xlsx_path, report_path)
```

Also add helper functions `_read_jsonl`, `_solver_rows_by_frame`, `_score_frame`, `_summary`, `_write_score_jsonl`, `_write_xlsx`, and `_render_report`.
The helper code must keep `mouse_enabled=True` as a failure even when distance is small.

- [ ] **Step 4: Run tests and commit.**

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests/test_studio_validation.py -q
git add -- core/puzzle/studio_validation.py tests/test_studio_validation.py
git commit --only -m "Studio 시각 검증 채점기 추가" -- core/puzzle/studio_validation.py tests/test_studio_validation.py
```

Expected: PASS.

---

### Task 4: Retention Policy

**Files:**
- Create: `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/core/puzzle/retention.py`
- Test: `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/tests/test_puzzle_retention.py`

**Interfaces:**
- Consumes: session root path containing `*_transparent_puzzle_sessions`.
- Produces: dry-run deletion candidates and optional deletion summary.

- [ ] **Step 1: Write failing retention tests.**

Create `test_puzzle_retention.py`.

```python
# 검증 영상 보존 정책이 최신 세션과 잠금 세션을 보호하는지 검증한다.
from pathlib import Path

from core.puzzle.retention import apply_video_retention, plan_video_retention


def _session(root: Path, name: str, *, locked: bool = False) -> Path:
    path = root / name
    path.mkdir(parents=True)
    for filename in ("raw_cctv.mkv", "board_crop.mkv", "overlay.mkv"):
        (path / filename).write_bytes(b"video")
    if locked:
        (path / ".keep_videos").write_text("keep\n", encoding="utf-8")
    return path


def test_plan_video_retention_keeps_latest_and_locked(tmp_path):
    root = tmp_path / "2026-07-17_transparent_puzzle_sessions"
    old = _session(root, "20260717_010000_001")
    locked = _session(root, "20260717_020000_001", locked=True)
    latest = _session(root, "20260717_030000_001")

    plan = plan_video_retention(root, keep_latest=1)

    delete_paths = {item.path for item in plan.delete_candidates}
    assert old / "raw_cctv.mkv" in delete_paths
    assert locked / "raw_cctv.mkv" not in delete_paths
    assert latest / "raw_cctv.mkv" not in delete_paths


def test_apply_video_retention_deletes_only_video_files(tmp_path):
    root = tmp_path / "2026-07-17_transparent_puzzle_sessions"
    old = _session(root, "20260717_010000_001")
    (old / "report.md").write_text("# keep\n", encoding="utf-8")

    result = apply_video_retention(root, keep_latest=0, dry_run=False)

    assert result.deleted_count == 3
    assert not (old / "raw_cctv.mkv").exists()
    assert (old / "report.md").exists()
```

- [ ] **Step 2: Run the test to verify it fails.**

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests/test_puzzle_retention.py -q
```

Expected: FAIL because `core.puzzle.retention` does not exist.

- [ ] **Step 3: Implement retention module.**

Create `retention.py`.

```python
# 검증 세션의 대용량 영상 파일 보존과 정리를 담당한다.
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


VIDEO_NAMES = frozenset({"raw_cctv.mkv", "board_crop.mkv", "overlay.mkv"})


@dataclass(frozen=True)
class RetentionItem:
    path: Path
    reason: str


@dataclass(frozen=True)
class RetentionPlan:
    root: Path
    keep_latest: int
    delete_candidates: list[RetentionItem]


@dataclass(frozen=True)
class RetentionResult:
    plan: RetentionPlan
    deleted_count: int
    deleted_bytes: int
```

Implement `plan_video_retention(root, keep_latest=3)` and `apply_video_retention(root, keep_latest=3, dry_run=True)`.
Only files named in `VIDEO_NAMES` may be deleted.
Sessions containing `.keep_videos` must never have videos deleted.

- [ ] **Step 4: Run tests and commit.**

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests/test_puzzle_retention.py -q
git add -- core/puzzle/retention.py tests/test_puzzle_retention.py
git commit --only -m "검증 영상 보존 정책 추가" -- core/puzzle/retention.py tests/test_puzzle_retention.py
```

Expected: PASS.

---

### Task 5: CLI Wiring

**Files:**
- Modify: `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/puzzle.py`
- Test: `C:/Users/PC/Desktop/02_work/05_AI/maple_bot/tests/test_puzzle_target_visual_check.py`

**Interfaces:**
- Consumes: `score_studio_session()`.
- Consumes: `apply_video_retention()`.
- Produces: CLI options `--studio-gt-jsonl`, `--validate-studio-trace`, `--retention-root`, `--retention-keep-videos`, `--retention-apply`.

- [ ] **Step 1: Write failing CLI tests.**

Add these tests to `test_puzzle_target_visual_check.py`.

```python
def test_validate_studio_trace_cli_calls_scorer(tmp_path):
    gt = tmp_path / "gt.jsonl"
    trace = tmp_path / "trace.jsonl"
    gt.write_text("", encoding="utf-8")
    trace.write_text("", encoding="utf-8")
    calls = []

    def fake_score(**kwargs):
        calls.append(kwargs)
        out = Path(kwargs["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        report = out / "studio_validation.md"
        report.write_text("# ok\n", encoding="utf-8")
        return type("Result", (), {"report_path": report})()

    with patch.object(puzzle, "score_studio_session", fake_score):
        code = puzzle.run_gui([
            "--validate-studio-trace",
            "--studio-gt-jsonl",
            str(gt),
            "--replay",
            str(trace),
            "--output-root",
            str(tmp_path / "out"),
        ])

    assert code == 0
    assert calls[0]["gt_jsonl"] == gt
    assert calls[0]["solver_trace_jsonl"] == trace


def test_retention_cli_defaults_to_dry_run(tmp_path):
    calls = []

    def fake_apply(root, *, keep_latest, dry_run):
        calls.append((Path(root), keep_latest, dry_run))
        return type("Result", (), {"deleted_count": 0, "deleted_bytes": 0})()

    with patch.object(puzzle, "apply_video_retention", fake_apply):
        code = puzzle.run_gui([
            "--retention-root",
            str(tmp_path),
            "--retention-keep-videos",
            "2",
        ])

    assert code == 0
    assert calls == [(tmp_path, 2, True)]
```

- [ ] **Step 2: Run the tests to verify they fail.**

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests/test_puzzle_target_visual_check.py -q
```

Expected: FAIL because the CLI options are not wired.

- [ ] **Step 3: Add imports and CLI args.**

In `puzzle.py`, add imports.

```python
from core.puzzle.retention import apply_video_retention
from core.puzzle.studio_validation import score_studio_session
```

Add parser args.

```python
    parser.add_argument("--validate-studio-trace", action="store_true", help="Studio GT와 solver trace를 비교한다")
    parser.add_argument("--studio-gt-jsonl", default="", help="Studio 정답 JSONL 경로")
    parser.add_argument("--score-distance-px", type=float, default=24.0, help="Studio 검증 성공 거리 기준")
    parser.add_argument("--retention-root", default="", help="영상 보존 정책을 적용할 세션 루트")
    parser.add_argument("--retention-keep-videos", type=int, default=3, help="보존할 최신 영상 세션 수")
    parser.add_argument("--retention-apply", action="store_true", help="dry-run이 아니라 실제로 영상 파일을 삭제한다")
```

- [ ] **Step 4: Add CLI branches before GUI creation.**

In `run_gui()`, before `if args.live_capture_check`, add this block.

```python
    if args.validate_studio_trace:
        if not args.studio_gt_jsonl:
            parser.error("--validate-studio-trace requires --studio-gt-jsonl")
        if not args.replay:
            parser.error("--validate-studio-trace requires --replay as solver trace path")
        result = score_studio_session(
            Path(args.studio_gt_jsonl),
            Path(args.replay),
            Path(args.output_root or Path(args.replay).parent / "studio_validation"),
            pass_distance_px=args.score_distance_px,
        )
        print(result.report_path)
        return 0

    if args.retention_root:
        result = apply_video_retention(
            Path(args.retention_root),
            keep_latest=args.retention_keep_videos,
            dry_run=not args.retention_apply,
        )
        print(f"deleted_count={result.deleted_count}")
        print(f"deleted_bytes={result.deleted_bytes}")
        return 0
```

- [ ] **Step 5: Run tests and commit.**

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests/test_puzzle_target_visual_check.py tests/test_studio_validation.py tests/test_puzzle_retention.py -q
git add -- puzzle.py tests/test_puzzle_target_visual_check.py
git commit --only -m "Studio 검증 CLI 연결" -- puzzle.py tests/test_puzzle_target_visual_check.py
```

Expected: PASS.

---

### Task 6: End-To-End Smoke And Documentation

**Files:**
- Modify: `C:/Users/PC/Desktop/02_work/05_AI/03_output/2026-07-17_studio_puzzle_visual_validation_v1_checklist.md`
- Modify: `C:/Users/PC/Desktop/02_work/05_AI/03_output/2026-07-17_studio_puzzle_visual_validation_v1_context-notes.md`
- Create: `C:/Users/PC/Desktop/02_work/05_AI/03_output/2026-07-17_studio_puzzle_visual_validation_implementation_result_v1.md`

**Interfaces:**
- Consumes: outputs from Tasks 1 to 5.
- Produces: final implementation result report.

- [ ] **Step 1: Run focused tests.**

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m pytest tests/test_puzzle_target_visual_check.py tests/test_puzzle_live_recording.py tests/test_studio_gt_export_static.py tests/test_studio_validation.py tests/test_puzzle_retention.py -q
```

Expected: PASS.

- [ ] **Step 2: Run a synthetic validation score.**

Create temporary `gt.jsonl` and `trace.jsonl` under a temp directory and run.

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" puzzle.py --validate-studio-trace --studio-gt-jsonl "<temp>\gt.jsonl" --replay "<temp>\trace.jsonl" --output-root "<temp>\out"
```

Expected: prints path ending in `studio_validation.md`.

- [ ] **Step 3: Run retention dry-run.**

```powershell
& "C:\Users\PC\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" puzzle.py --retention-root "<session-root>" --retention-keep-videos 3
```

Expected: prints `deleted_count=0` when dry-run is active.

- [ ] **Step 4: Update checklist and context notes.**

Mark completed items in `2026-07-17_studio_puzzle_visual_validation_v1_checklist.md`.
Append implementation notes to `2026-07-17_studio_puzzle_visual_validation_v1_context-notes.md`.

- [ ] **Step 5: Write result report.**

Create `2026-07-17_studio_puzzle_visual_validation_implementation_result_v1.md` with this structure.

```markdown
# Studio와 puzzle.py 자동 시각 검증 구현 결과

## 변경 요약

- 마우스 OFF 검증 trace를 추가했다.
- Studio GT export 표면을 추가했다.
- Studio GT와 solver trace 채점기를 추가했다.
- 영상 보존 정책을 추가했다.
- CLI 연결을 추가했다.

## 검증 결과

- focused pytest: PASS
- synthetic validation: PASS
- retention dry-run: PASS

## 운영 방법

1. Studio를 `?export_gt=1&autoplay=1`로 실행한다.
2. puzzle.py를 `--target-visual-check`로 실행한다.
3. Studio GT JSONL과 solver trace를 `--validate-studio-trace`로 비교한다.
4. 오래된 영상은 `--retention-root`로 dry-run 확인 후 필요할 때만 `--retention-apply`를 붙인다.
```

- [ ] **Step 6: Commit.**

```powershell
git add -- 03_output/2026-07-17_studio_puzzle_visual_validation_v1_checklist.md 03_output/2026-07-17_studio_puzzle_visual_validation_v1_context-notes.md 03_output/2026-07-17_studio_puzzle_visual_validation_implementation_result_v1.md
git commit --only -m "Studio 검증 구현 결과 정리" -- 03_output/2026-07-17_studio_puzzle_visual_validation_v1_checklist.md 03_output/2026-07-17_studio_puzzle_visual_validation_v1_context-notes.md 03_output/2026-07-17_studio_puzzle_visual_validation_implementation_result_v1.md
```

Expected: commit succeeds and includes only the three documentation files.

---

## Self-Review

- Spec coverage.
  - 마우스 OFF 검증은 Task 1과 Task 5에서 다룬다.
  - Studio GT export는 Task 2에서 다룬다.
  - 자동 채점과 엑셀 리포트는 Task 3에서 다룬다.
  - 영상 보존 정책은 Task 4와 Task 5에서 다룬다.
  - 최종 보고서는 Task 6에서 다룬다.

- Placeholder scan.
  - 이 계획은 빈 항목이나 미확정 구현 지시를 사용하지 않는다.
  - 각 task는 테스트, 구현, 검증, 커밋 단위를 포함한다.

- Type consistency.
  - `score_studio_session()`은 Task 3에서 정의되고 Task 5에서 CLI로 소비된다.
  - `apply_video_retention()`은 Task 4에서 정의되고 Task 5에서 CLI로 소비된다.
  - `SOLVER_VISUAL_TRACE`는 Task 1에서 생성되고 Task 3에서 소비된다.
