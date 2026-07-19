# Studio 정답 경로와 puzzle.py 선택 경로를 시간축으로 맞춰 검증 리포트를 만든다.
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace
from math import hypot
from pathlib import Path
from typing import Any

from openpyxl import Workbook


@dataclass(frozen=True)
class ScoreFrame:
    run_id: str
    run_index: int
    frame_id: int
    solver_frame_index: int | None
    gt_timestamp_ms: int | None
    solver_timestamp_ms: int | None
    timestamp_delta_ms: float | None
    distance_px: float | None
    passed: bool
    fail_reason: str
    failure_class: str
    puzzle_phase: str
    failure_stage: str
    target_white: float | None
    target_overlap: bool
    target_x: float | None
    target_y: float | None
    selected_x: float | None
    selected_y: float | None
    candidate_count: int
    candidate_id: str
    confidence: float | None
    solver_reason: str
    temporal_reason: str
    temporal_family: str
    mouse_enabled: bool


@dataclass(frozen=True)
class ScoreSummary:
    total_frames: int
    aligned_frames: int
    alignment_missing_frames: int
    passed_frames: int
    failed_frames: int
    max_distance_px: float
    alignment_rate: float
    pass_rate: float
    aligned_pass_rate: float


@dataclass(frozen=True)
class RunScoreSummary:
    run_id: str
    run_index: int
    total_frames: int
    aligned_frames: int
    alignment_missing_frames: int
    passed_frames: int
    failed_frames: int
    alignment_rate: float
    pass_rate: float
    aligned_pass_rate: float
    max_distance_px: float


@dataclass(frozen=True)
class FailureCluster:
    run_id: str
    run_index: int
    failure_class: str
    start_frame: int
    end_frame: int
    frame_count: int


@dataclass(frozen=True)
class CandidateDiagnostic:
    run_id: str
    run_index: int
    frame_id: int
    puzzle_phase: str
    failure_stage: str
    role: str
    candidate_id: str
    center_x: float | None
    center_y: float | None
    gt_distance_px: float | None
    yolo_score: float | None
    source: str
    predicted_distance_px: float | None
    total_cost: float | None
    cost_parts: str
    judge_shares: str
    bg_score: float | None
    motion_divergence: float | None
    rigid_violation: float | None
    phase_similarity: float | None
    texture_bg_score: float | None
    color_residual: float | None
    merge_likelihood: float | None


@dataclass(frozen=True)
class CandidateCoverageSummary:
    aligned_target_frames: int
    center_oracle_frames: int
    box_oracle_frames: int
    failed_center_recoverable_frames: int
    failed_box_only_frames: int
    failed_candidate_absent_frames: int


@dataclass(frozen=True)
class StudioValidationResult:
    summary: ScoreSummary
    candidate_coverage: CandidateCoverageSummary
    frames: list[ScoreFrame]
    runs: list[RunScoreSummary]
    failure_clusters: list[FailureCluster]
    candidate_diagnostics: list[CandidateDiagnostic]
    score_jsonl: Path
    xlsx_path: Path
    report_path: Path
    diagnostic_image_dir: Path


def score_studio_session(
    gt_jsonl: str | Path,
    solver_trace_jsonl: str | Path,
    output_dir: str | Path,
    *,
    pass_distance_px: float = 24.0,
    max_alignment_ms: float = 80.0,
) -> StudioValidationResult:
    if pass_distance_px < 0 or max_alignment_ms < 0:
        raise ValueError("distance thresholds must be non-negative")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    gt_rows = sorted(
        _read_jsonl(Path(gt_jsonl)),
        key=lambda row: (
            int(row.get("run_index", 0)),
            int(row.get("frame_id", 0)),
        ),
    )
    trace_rows = _read_jsonl(Path(solver_trace_jsonl))
    solver_rows = _solver_rows_from_trace(trace_rows)
    matches = _match_solver_rows(gt_rows, solver_rows, max_alignment_ms=max_alignment_ms)
    base_frames = [
        _score_frame(gt, solver, pass_distance_px=pass_distance_px)
        for gt, solver in zip(gt_rows, matches)
    ]
    frames = _classify_failures(base_frames, pass_distance_px=pass_distance_px)
    summary = _summary(frames)
    runs = _run_summaries(frames)
    failure_clusters = _failure_clusters(frames)
    candidate_coverage = _candidate_coverage_summary(
        gt_rows,
        frames,
        trace_rows,
        pass_distance_px=pass_distance_px,
    )
    candidate_diagnostics = _candidate_diagnostic_rows(gt_rows, frames, trace_rows)
    score_jsonl = output / "score.jsonl"
    xlsx_path = output / "studio_validation.xlsx"
    report_path = output / "studio_validation.md"
    diagnostic_image_dir = output / "diagnostic_images"
    _write_score_jsonl(score_jsonl, frames)
    _write_xlsx(
        xlsx_path,
        summary,
        candidate_coverage,
        runs,
        failure_clusters,
        frames,
        candidate_diagnostics,
    )
    report_path.write_text(
        _render_report(summary, candidate_coverage, runs, failure_clusters, frames),
        encoding="utf-8",
    )
    _write_failure_diagnostic_images(
        Path(solver_trace_jsonl).parent / "board_crop.mkv",
        diagnostic_image_dir,
        frames,
        failure_clusters,
        candidate_diagnostics,
        trace_rows,
    )
    return StudioValidationResult(
        summary=summary,
        candidate_coverage=candidate_coverage,
        frames=frames,
        runs=runs,
        failure_clusters=failure_clusters,
        candidate_diagnostics=candidate_diagnostics,
        score_jsonl=score_jsonl,
        xlsx_path=xlsx_path,
        report_path=report_path,
        diagnostic_image_dir=diagnostic_image_dir,
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as fp:
        for line in fp:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _solver_rows(path: Path) -> list[dict[str, Any]]:
    return _solver_rows_from_trace(_read_jsonl(path))


def _solver_rows_from_trace(trace_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    target_points: dict[int, tuple[float, float]] = {}
    for row in trace_rows:
        if row.get("type") != "TARGET_SELECTION" or row.get("frame_index") is None:
            continue
        payload = row.get("payload")
        point = payload.get("point") if isinstance(payload, dict) else None
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        x = _optional_float(point[0])
        y = _optional_float(point[1])
        if x is not None and y is not None:
            target_points[int(row["frame_index"])] = (x, y)

    rows: list[dict[str, Any]] = []
    for row in trace_rows:
        if row.get("type") != "SOLVER_VISUAL_TRACE":
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict) or row.get("frame_index") is None:
            continue
        merged = dict(payload)
        merged["_frame_index"] = int(row["frame_index"])
        merged["_timestamp_ms"] = _optional_int(row.get("timestamp_ms"))
        target_point = target_points.get(merged["_frame_index"])
        if target_point is not None:
            merged["selected_x"], merged["selected_y"] = target_point
        rows.append(merged)
    return rows


def _match_solver_rows(
    gt_rows: list[dict[str, Any]],
    solver_rows: list[dict[str, Any]],
    *,
    max_alignment_ms: float,
) -> list[dict[str, Any] | None]:
    by_frame = {int(row["_frame_index"]): row for row in solver_rows}
    timestamped = sorted(
        [row for row in solver_rows if row.get("_timestamp_ms") is not None],
        key=lambda row: int(row["_timestamp_ms"]),
    )
    matches: list[dict[str, Any] | None] = []
    used_solver_frames: set[int] = set()
    for gt in gt_rows:
        explicit_frame_index = _optional_int(gt.get("solver_frame_index"))
        if explicit_frame_index is not None:
            matched = by_frame.get(explicit_frame_index)
            if matched is not None and explicit_frame_index in used_solver_frames:
                matched = None
            matches.append(matched)
            if matched is not None:
                used_solver_frames.add(explicit_frame_index)
            continue
        gt_timestamp = _optional_int(gt.get("timestamp_ms"))
        if gt_timestamp is not None and timestamped:
            candidates = [
                row
                for row in timestamped
                if int(row["_frame_index"]) not in used_solver_frames
            ]
            nearest = min(
                candidates,
                key=lambda row: abs(int(row["_timestamp_ms"]) - gt_timestamp),
                default=None,
            )
            if nearest is not None and abs(int(nearest["_timestamp_ms"]) - gt_timestamp) <= max_alignment_ms:
                matches.append(nearest)
                used_solver_frames.add(int(nearest["_frame_index"]))
            else:
                matches.append(None)
            continue
        matched = by_frame.get(int(gt.get("frame_id", -1)))
        if matched is not None and int(matched["_frame_index"]) in used_solver_frames:
            matched = None
        matches.append(matched)
        if matched is not None:
            used_solver_frames.add(int(matched["_frame_index"]))
    return matches


def _score_frame(
    gt: dict[str, Any],
    solver: dict[str, Any] | None,
    *,
    pass_distance_px: float,
) -> ScoreFrame:
    run_id = str(gt.get("run_id", ""))
    run_index = int(gt.get("run_index", 0))
    frame_id = int(gt.get("frame_id", 0))
    gt_timestamp = _optional_int(gt.get("timestamp_ms"))
    solver_timestamp = _optional_int(solver.get("_timestamp_ms") if solver is not None else None)
    solver_frame_index = _optional_int(solver.get("_frame_index") if solver is not None else None)
    target_x = _optional_float(gt.get("target_x"))
    target_y = _optional_float(gt.get("target_y"))
    selected_x = _optional_float(solver.get("selected_x") if solver is not None else None)
    selected_y = _optional_float(solver.get("selected_y") if solver is not None else None)
    candidate_count = int(solver.get("candidate_count", 0) if solver is not None else 0)
    mouse_enabled = bool(solver.get("mouse_enabled", False) if solver is not None else False)
    distance = _distance(target_x, target_y, selected_x, selected_y)
    fail_reason = _fail_reason(
        distance,
        target_x=target_x,
        target_y=target_y,
        selected_x=selected_x,
        selected_y=selected_y,
        mouse_enabled=mouse_enabled,
        pass_distance_px=pass_distance_px,
    )
    return ScoreFrame(
        run_id=run_id,
        run_index=run_index,
        frame_id=frame_id,
        solver_frame_index=solver_frame_index,
        gt_timestamp_ms=gt_timestamp,
        solver_timestamp_ms=solver_timestamp,
        timestamp_delta_ms=(
            float(abs(solver_timestamp - gt_timestamp))
            if solver_timestamp is not None and gt_timestamp is not None
            else None
        ),
        distance_px=distance,
        passed=fail_reason == "",
        fail_reason=fail_reason,
        failure_class="",
        puzzle_phase=_puzzle_phase(gt),
        failure_stage="",
        target_white=_optional_float(gt.get("target_white")),
        target_overlap=bool(gt.get("target_decoy_overlap", False)),
        target_x=target_x,
        target_y=target_y,
        selected_x=selected_x,
        selected_y=selected_y,
        candidate_count=candidate_count,
        candidate_id=str(solver.get("candidate_id", "") if solver is not None else ""),
        confidence=_optional_float(solver.get("confidence") if solver is not None else None),
        solver_reason=str(solver.get("reason", "") if solver is not None else ""),
        temporal_reason=str(solver.get("temporal_reason", "") if solver is not None else ""),
        temporal_family=str(solver.get("temporal_family", "") if solver is not None else ""),
        mouse_enabled=mouse_enabled,
    )


def _classify_failures(frames: list[ScoreFrame], *, pass_distance_px: float) -> list[ScoreFrame]:
    previous_by_run: dict[str, tuple[float, float]] = {}
    classified: list[ScoreFrame] = []
    jump_threshold = max(80.0, pass_distance_px * 4.0)
    for frame in frames:
        previous = previous_by_run.get(frame.run_id)
        failure_class = _failure_class(frame, previous=previous, jump_threshold=jump_threshold)
        classified.append(
            replace(
                frame,
                failure_class=failure_class,
                failure_stage=_failure_stage(frame, failure_class=failure_class),
            )
        )
        if frame.selected_x is not None and frame.selected_y is not None:
            previous_by_run[frame.run_id] = (frame.selected_x, frame.selected_y)
    return classified


def _failure_class(
    frame: ScoreFrame,
    *,
    previous: tuple[float, float] | None,
    jump_threshold: float,
) -> str:
    if frame.passed:
        return ""
    if frame.fail_reason == "mouse_enabled":
        return "safety_guard"
    if frame.fail_reason == "missing_gt":
        return "missing_gt"
    if frame.fail_reason == "missing_selection":
        if frame.solver_frame_index is None:
            return "alignment_missing"
        return "candidate_missing" if frame.candidate_count == 0 else "selector_no_choice"
    if previous is not None and frame.selected_x is not None and frame.selected_y is not None:
        jump = hypot(frame.selected_x - previous[0], frame.selected_y - previous[1])
        if jump > jump_threshold:
            return "path_jump"
    reasons = f"{frame.solver_reason} {frame.temporal_reason}".lower()
    if any(token in reasons for token in ("hold", "reacquire", "lost", "occlusion", "no_identity")):
        return "reacquire_failure"
    return "wrong_candidate"


def _puzzle_phase(gt: dict[str, Any]) -> str:
    explicit = str(gt.get("puzzle_phase", "") or "").strip().lower()
    if explicit:
        return explicit
    motion_started = gt.get("target_motion_started")
    if motion_started is False:
        return "initialization"
    target_white = _optional_float(gt.get("target_white"))
    if target_white is None:
        return "unknown"
    return "fade" if target_white > 0.0 else "transparent"


def _failure_stage(frame: ScoreFrame, *, failure_class: str) -> str:
    if not failure_class:
        return ""
    reasons = f"{failure_class} {frame.solver_reason} {frame.temporal_reason}".lower()
    if any(token in reasons for token in ("reacquire", "lost", "hold", "occlusion", "no_identity")):
        return "reacquire"
    if frame.target_overlap:
        return "overlap"
    return frame.puzzle_phase


def _candidate_diagnostic_rows(
    gt_rows: list[dict[str, Any]],
    frames: list[ScoreFrame],
    trace_rows: list[dict[str, Any]],
) -> list[CandidateDiagnostic]:
    events: dict[tuple[int, str], dict[str, Any]] = {}
    for row in trace_rows:
        frame_index = _optional_int(row.get("frame_index"))
        payload = row.get("payload")
        if frame_index is None or not isinstance(payload, dict):
            continue
        events[(frame_index, str(row.get("type", "")))] = payload

    diagnostics: list[CandidateDiagnostic] = []
    for gt, frame in zip(gt_rows, frames):
        if frame.solver_frame_index is None:
            continue
        frame_index = frame.solver_frame_index
        candidate_payload = events.get((frame_index, "CANDIDATES"), {})
        identity_payload = events.get((frame_index, "IDENTITY_STATE"), {})
        evidence_payload = events.get((frame_index, "EVIDENCE"), {})
        candidates = [item for item in candidate_payload.get("candidates", []) if isinstance(item, dict)]
        evidence = {
            str(item.get("candidate_id", "")): item
            for item in evidence_payload.get("evidence", [])
            if isinstance(item, dict)
        }
        debug = identity_payload.get("debug")
        ranking = debug.get("ranking", []) if isinstance(debug, dict) else []
        ranking_by_id = {
            str(item.get("candidate_id", "")): item
            for item in ranking
            if isinstance(item, dict)
        }
        selected_id = str(identity_payload.get("candidate_id", "") or frame.candidate_id)
        selected = next(
            (item for item in candidates if str(item.get("candidate_id", "")) == selected_id),
            None,
        )
        nearest = min(
            candidates,
            key=lambda item: _candidate_gt_distance(item, gt),
            default=None,
        )
        if selected is not None:
            diagnostics.append(
                _candidate_diagnostic(
                    frame,
                    "selected_identity",
                    selected,
                    evidence.get(selected_id, {}),
                    ranking_by_id.get(selected_id, {}),
                )
            )
        if nearest is not None:
            nearest_id = str(nearest.get("candidate_id", ""))
            diagnostics.append(
                _candidate_diagnostic(
                    frame,
                    "nearest_gt",
                    nearest,
                    evidence.get(nearest_id, {}),
                    ranking_by_id.get(nearest_id, {}),
                )
            )
    return diagnostics


def _candidate_coverage_summary(
    gt_rows: list[dict[str, Any]],
    frames: list[ScoreFrame],
    trace_rows: list[dict[str, Any]],
    *,
    pass_distance_px: float,
) -> CandidateCoverageSummary:
    candidates_by_frame = {
        int(row["frame_index"]): list(row.get("payload", {}).get("candidates", []))
        for row in trace_rows
        if row.get("type") == "CANDIDATES"
        and row.get("frame_index") is not None
        and isinstance(row.get("payload"), dict)
    }
    aligned_target_frames = 0
    center_oracle_frames = 0
    box_oracle_frames = 0
    failed_center_recoverable_frames = 0
    failed_box_only_frames = 0
    failed_candidate_absent_frames = 0
    for gt, frame in zip(gt_rows, frames):
        if frame.solver_frame_index is None or frame.target_x is None or frame.target_y is None:
            continue
        aligned_target_frames += 1
        candidates = [
            candidate
            for candidate in candidates_by_frame.get(frame.solver_frame_index, [])
            if isinstance(candidate, dict)
        ]
        center_hit = any(
            _candidate_gt_distance(candidate, gt) <= pass_distance_px
            for candidate in candidates
        )
        box_hit = any(_candidate_contains_gt(candidate, gt) for candidate in candidates)
        center_oracle_frames += int(center_hit)
        box_oracle_frames += int(box_hit)
        if frame.passed:
            continue
        if center_hit:
            failed_center_recoverable_frames += 1
        elif box_hit:
            failed_box_only_frames += 1
        else:
            failed_candidate_absent_frames += 1
    return CandidateCoverageSummary(
        aligned_target_frames=aligned_target_frames,
        center_oracle_frames=center_oracle_frames,
        box_oracle_frames=box_oracle_frames,
        failed_center_recoverable_frames=failed_center_recoverable_frames,
        failed_box_only_frames=failed_box_only_frames,
        failed_candidate_absent_frames=failed_candidate_absent_frames,
    )


def _candidate_diagnostic(
    frame: ScoreFrame,
    role: str,
    candidate: dict[str, Any],
    evidence: dict[str, Any],
    ranking: dict[str, Any],
) -> CandidateDiagnostic:
    center = candidate.get("center")
    center_x = _optional_float(center[0]) if isinstance(center, (list, tuple)) and len(center) >= 2 else None
    center_y = _optional_float(center[1]) if isinstance(center, (list, tuple)) and len(center) >= 2 else None
    cost_parts = ranking.get("cost_parts") if isinstance(ranking.get("cost_parts"), dict) else {}
    judge_shares = ranking.get("judge_shares") if isinstance(ranking.get("judge_shares"), dict) else {}
    return CandidateDiagnostic(
        run_id=frame.run_id,
        run_index=frame.run_index,
        frame_id=frame.frame_id,
        puzzle_phase=frame.puzzle_phase,
        failure_stage=frame.failure_stage,
        role=role,
        candidate_id=str(candidate.get("candidate_id", "")),
        center_x=center_x,
        center_y=center_y,
        gt_distance_px=_distance(frame.target_x, frame.target_y, center_x, center_y),
        yolo_score=_optional_float(candidate.get("score")),
        source=str(candidate.get("source", "")),
        predicted_distance_px=_optional_float(ranking.get("distance")),
        total_cost=_optional_float(ranking.get("total_cost")),
        cost_parts=json.dumps(cost_parts, ensure_ascii=False, sort_keys=True),
        judge_shares=json.dumps(judge_shares, ensure_ascii=False, sort_keys=True),
        bg_score=_optional_float(evidence.get("bg_score")),
        motion_divergence=_optional_float(evidence.get("motion_divergence")),
        rigid_violation=_optional_float(evidence.get("rigid_violation")),
        phase_similarity=_optional_float(evidence.get("phase_similarity")),
        texture_bg_score=_optional_float(evidence.get("texture_bg_score")),
        color_residual=_optional_float(evidence.get("color_residual")),
        merge_likelihood=_optional_float(evidence.get("merge_likelihood")),
    )


def _candidate_gt_distance(candidate: dict[str, Any], gt: dict[str, Any]) -> float:
    center = candidate.get("center")
    if not isinstance(center, (list, tuple)) or len(center) < 2:
        return float("inf")
    distance = _distance(
        _optional_float(gt.get("target_x")),
        _optional_float(gt.get("target_y")),
        _optional_float(center[0]),
        _optional_float(center[1]),
    )
    return distance if distance is not None else float("inf")


def _candidate_contains_gt(candidate: dict[str, Any], gt: dict[str, Any]) -> bool:
    bbox = candidate.get("bbox")
    target_x = _optional_float(gt.get("target_x"))
    target_y = _optional_float(gt.get("target_y"))
    if not isinstance(bbox, (list, tuple)) or len(bbox) < 4 or target_x is None or target_y is None:
        return False
    values = [_optional_float(value) for value in bbox[:4]]
    if any(value is None for value in values):
        return False
    left, top, right, bottom = (float(value) for value in values)
    return left <= target_x <= right and top <= target_y <= bottom


def _write_failure_diagnostic_images(
    video_path: Path,
    output_dir: Path,
    frames: list[ScoreFrame],
    failure_clusters: list[FailureCluster],
    diagnostics: list[CandidateDiagnostic],
    trace_rows: list[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not video_path.is_file() or not failure_clusters:
        return

    frames_by_key = {(frame.run_id, frame.frame_id): frame for frame in frames}
    representative_keys = _representative_failure_keys(frames)

    candidate_events = {
        int(row["frame_index"]): row.get("payload", {})
        for row in trace_rows
        if row.get("type") == "CANDIDATES"
        and row.get("frame_index") is not None
        and isinstance(row.get("payload"), dict)
    }
    diagnostic_by_key_role = {
        (item.run_id, item.frame_id, item.role): item
        for item in diagnostics
    }

    cv2 = _cv2()
    capture = cv2.VideoCapture(str(video_path))
    try:
        for run_id, frame_id in dict.fromkeys(representative_keys):
            frame = frames_by_key.get((run_id, frame_id))
            if frame is None or frame.solver_frame_index is None:
                continue
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame.solver_frame_index)
            ok, image = capture.read()
            if not ok or image is None:
                continue
            selected_diag = diagnostic_by_key_role.get((run_id, frame_id, "selected_identity"))
            nearest_diag = diagnostic_by_key_role.get((run_id, frame_id, "nearest_gt"))
            payload = candidate_events.get(frame.solver_frame_index, {})
            candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
            selected_bbox = _candidate_bbox(candidates, selected_diag.candidate_id if selected_diag else "")
            nearest_bbox = _candidate_bbox(candidates, nearest_diag.candidate_id if nearest_diag else "")
            annotated = _annotate_diagnostic_frame(
                image,
                frame_id=frame.frame_id,
                puzzle_phase=frame.puzzle_phase,
                failure_stage=frame.failure_stage,
                distance_px=frame.distance_px,
                selected_point=_point(frame.selected_x, frame.selected_y),
                gt_point=_point(frame.target_x, frame.target_y),
                selected_bbox=selected_bbox,
                nearest_bbox=nearest_bbox,
            )
            safe_run_id = "".join(char if char.isalnum() else "_" for char in run_id)[-32:]
            filename = f"{safe_run_id}_f{frame.frame_id:06d}_{frame.failure_stage or 'failure'}.png"
            cv2.imwrite(str(output_dir / filename), annotated)
    finally:
        capture.release()


def _representative_failure_keys(frames: list[Any]) -> list[tuple[str, int]]:
    grouped: dict[str, list[Any]] = {}
    for frame in frames:
        if str(getattr(frame, "failure_stage", "") or ""):
            grouped.setdefault(str(frame.run_id), []).append(frame)

    selected: list[tuple[str, int]] = []
    for run_id, run_frames in grouped.items():
        ordered = sorted(run_frames, key=lambda frame: int(frame.frame_id))
        choices = [
            ordered[0],
            max(ordered, key=lambda frame: float(frame.distance_px or 0.0)),
            next((frame for frame in ordered if frame.failure_stage == "overlap"), None),
            next((frame for frame in ordered if frame.failure_stage == "reacquire"), None),
        ]
        for frame in choices:
            if frame is None:
                continue
            key = (run_id, int(frame.frame_id))
            if key not in selected:
                selected.append(key)
    return selected


def _annotate_diagnostic_frame(
    frame: Any,
    *,
    frame_id: int,
    puzzle_phase: str,
    failure_stage: str,
    distance_px: float | None,
    selected_point: tuple[float, float] | None,
    gt_point: tuple[float, float] | None,
    selected_bbox: tuple[float, float, float, float] | None,
    nearest_bbox: tuple[float, float, float, float] | None,
) -> Any:
    cv2 = _cv2()
    image = frame.copy()
    if nearest_bbox is not None:
        _draw_bbox(image, nearest_bbox, (0, 255, 255), cv2=cv2)
    if selected_bbox is not None:
        _draw_bbox(image, selected_bbox, (0, 0, 255), cv2=cv2)
    if gt_point is not None:
        cv2.circle(image, _int_point(gt_point), 9, (255, 255, 0), 2, cv2.LINE_AA)
    if selected_point is not None:
        x, y = _int_point(selected_point)
        cv2.line(image, (x - 10, y), (x + 10, y), (0, 255, 0), 2, cv2.LINE_AA)
        cv2.line(image, (x, y - 10), (x, y + 10), (0, 255, 0), 2, cv2.LINE_AA)
    distance_text = "-" if distance_px is None else f"{distance_px:.1f}px"
    label = f"f{frame_id} {puzzle_phase}/{failure_stage or 'pass'} err={distance_text}"
    cv2.rectangle(image, (0, 0), (min(image.shape[1] - 1, 410), 24), (0, 0, 0), -1)
    cv2.putText(image, label, (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    return image


def _candidate_bbox(candidates: Any, candidate_id: str) -> tuple[float, float, float, float] | None:
    if not candidate_id or not isinstance(candidates, list):
        return None
    for candidate in candidates:
        if not isinstance(candidate, dict) or str(candidate.get("candidate_id", "")) != candidate_id:
            continue
        bbox = candidate.get("bbox")
        if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
            values = tuple(_optional_float(value) for value in bbox[:4])
            if all(value is not None for value in values):
                return tuple(float(value) for value in values)  # type: ignore[arg-type]
    return None


def _draw_bbox(frame: Any, bbox: tuple[float, float, float, float], color: tuple[int, int, int], *, cv2: Any) -> None:
    x1, y1, x2, y2 = bbox
    cv2.rectangle(frame, (int(round(x1)), int(round(y1))), (int(round(x2)), int(round(y2))), color, 2)


def _point(x: float | None, y: float | None) -> tuple[float, float] | None:
    if x is None or y is None:
        return None
    return (float(x), float(y))


def _int_point(point: tuple[float, float]) -> tuple[int, int]:
    return (int(round(point[0])), int(round(point[1])))


def _cv2() -> Any:
    import cv2

    return cv2


def _fail_reason(
    distance: float | None,
    *,
    target_x: float | None,
    target_y: float | None,
    selected_x: float | None,
    selected_y: float | None,
    mouse_enabled: bool,
    pass_distance_px: float,
) -> str:
    if mouse_enabled:
        return "mouse_enabled"
    if target_x is None or target_y is None:
        return "missing_gt"
    if selected_x is None or selected_y is None:
        return "missing_selection"
    if distance is None or distance > pass_distance_px:
        return "distance"
    return ""


def _summary(frames: list[ScoreFrame]) -> ScoreSummary:
    total = len(frames)
    aligned = sum(1 for frame in frames if frame.solver_frame_index is not None)
    passed = sum(1 for frame in frames if frame.passed)
    distances = [frame.distance_px for frame in frames if frame.distance_px is not None]
    return ScoreSummary(
        total_frames=total,
        aligned_frames=aligned,
        alignment_missing_frames=total - aligned,
        passed_frames=passed,
        failed_frames=total - passed,
        max_distance_px=float(max(distances, default=0.0)),
        alignment_rate=(aligned / total) if total else 0.0,
        pass_rate=(passed / total) if total else 0.0,
        aligned_pass_rate=(passed / aligned) if aligned else 0.0,
    )


def _run_summaries(frames: list[ScoreFrame]) -> list[RunScoreSummary]:
    grouped: dict[tuple[int, str], list[ScoreFrame]] = {}
    for frame in frames:
        grouped.setdefault((frame.run_index, frame.run_id), []).append(frame)
    rows: list[RunScoreSummary] = []
    for (run_index, run_id), run_frames in sorted(grouped.items()):
        summary = _summary(run_frames)
        rows.append(
            RunScoreSummary(
                run_id=run_id,
                run_index=run_index,
                total_frames=summary.total_frames,
                aligned_frames=summary.aligned_frames,
                alignment_missing_frames=summary.alignment_missing_frames,
                passed_frames=summary.passed_frames,
                failed_frames=summary.failed_frames,
                alignment_rate=summary.alignment_rate,
                pass_rate=summary.pass_rate,
                aligned_pass_rate=summary.aligned_pass_rate,
                max_distance_px=summary.max_distance_px,
            )
        )
    return rows


def _failure_clusters(frames: list[ScoreFrame]) -> list[FailureCluster]:
    clusters: list[FailureCluster] = []
    current: list[ScoreFrame] = []
    for frame in frames:
        continues = bool(
            current
            and frame.failure_class
            and frame.run_id == current[-1].run_id
            and frame.failure_class == current[-1].failure_class
            and frame.frame_id == current[-1].frame_id + 1
        )
        if not continues:
            if current:
                clusters.append(_cluster(current))
            current = [frame] if frame.failure_class else []
        else:
            current.append(frame)
    if current:
        clusters.append(_cluster(current))
    return clusters


def _cluster(frames: list[ScoreFrame]) -> FailureCluster:
    first = frames[0]
    return FailureCluster(
        run_id=first.run_id,
        run_index=first.run_index,
        failure_class=first.failure_class,
        start_frame=first.frame_id,
        end_frame=frames[-1].frame_id,
        frame_count=len(frames),
    )


def _write_score_jsonl(path: Path, frames: list[ScoreFrame]) -> None:
    with path.open("w", encoding="utf-8") as fp:
        for frame in frames:
            fp.write(json.dumps(asdict(frame), ensure_ascii=False))
            fp.write("\n")


def _write_xlsx(
    path: Path,
    summary: ScoreSummary,
    candidate_coverage: CandidateCoverageSummary,
    runs: list[RunScoreSummary],
    failure_clusters: list[FailureCluster],
    frames: list[ScoreFrame],
    candidate_diagnostics: list[CandidateDiagnostic],
) -> None:
    workbook = Workbook()
    summary_sheet = workbook.active
    summary_sheet.title = "summary"
    for row in asdict(summary).items():
        summary_sheet.append(row)
    _write_dataclass_sheet(
        workbook,
        "candidate_coverage",
        [candidate_coverage],
        CandidateCoverageSummary,
    )
    _write_dataclass_sheet(workbook, "runs", runs, RunScoreSummary)
    _write_dataclass_sheet(workbook, "failure_clusters", failure_clusters, FailureCluster)
    _write_dataclass_sheet(workbook, "frames", frames, ScoreFrame)
    _write_dataclass_sheet(
        workbook,
        "candidate_diagnostics",
        candidate_diagnostics,
        CandidateDiagnostic,
    )
    workbook.save(path)


def _write_dataclass_sheet(workbook: Workbook, name: str, rows: list[Any], row_type: type[Any]) -> None:
    sheet = workbook.create_sheet(name)
    headers = list(asdict(rows[0]).keys()) if rows else list(row_type.__dataclass_fields__)
    sheet.append(headers)
    for row in rows:
        values = asdict(row)
        sheet.append([values.get(header) for header in headers])


def _render_report(
    summary: ScoreSummary,
    candidate_coverage: CandidateCoverageSummary,
    runs: list[RunScoreSummary],
    failure_clusters: list[FailureCluster],
    frames: list[ScoreFrame],
) -> str:
    stage_counts: dict[str, int] = {}
    for frame in frames:
        if frame.failure_stage:
            stage_counts[frame.failure_stage] = stage_counts.get(frame.failure_stage, 0) + 1
    lines = [
        "# Studio Validation",
        "",
        f"- total_frames: {summary.total_frames}",
        f"- aligned_frames: {summary.aligned_frames}",
        f"- alignment_missing_frames: {summary.alignment_missing_frames}",
        f"- passed_frames: {summary.passed_frames}",
        f"- failed_frames: {summary.failed_frames}",
        f"- alignment_rate: {summary.alignment_rate:.4f}",
        f"- pass_rate: {summary.pass_rate:.4f}",
        f"- aligned_pass_rate: {summary.aligned_pass_rate:.4f}",
        f"- max_distance_px: {summary.max_distance_px:.3f}",
        "",
        "## Candidate Coverage",
        "",
        f"- aligned_target_frames: {candidate_coverage.aligned_target_frames}",
        f"- center_oracle_frames: {candidate_coverage.center_oracle_frames}",
        f"- box_oracle_frames: {candidate_coverage.box_oracle_frames}",
        f"- failed_center_recoverable_frames: {candidate_coverage.failed_center_recoverable_frames}",
        f"- failed_box_only_frames: {candidate_coverage.failed_box_only_frames}",
        f"- failed_candidate_absent_frames: {candidate_coverage.failed_candidate_absent_frames}",
        "",
        "## Runs",
        "",
    ]
    lines.extend(
        (
            f"- {run.run_id}: pass={run.pass_rate:.4f}, "
            f"alignment={run.alignment_rate:.4f}, aligned_pass={run.aligned_pass_rate:.4f}"
        )
        for run in runs
    )
    lines.extend(["", "## Failure Clusters", ""])
    lines.extend(
        f"- {cluster.run_id} {cluster.start_frame}-{cluster.end_frame}: {cluster.failure_class}"
        for cluster in failure_clusters
    )
    lines.extend(["", "## Failure Stages", ""])
    lines.extend(f"- {stage}: {count}" for stage, count in sorted(stage_counts.items()))
    lines.append("")
    return "\n".join(lines)


def _distance(
    target_x: float | None,
    target_y: float | None,
    selected_x: float | None,
    selected_y: float | None,
) -> float | None:
    if None in (target_x, target_y, selected_x, selected_y):
        return None
    return float(hypot(float(target_x) - float(selected_x), float(target_y) - float(selected_y)))


def _optional_float(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _optional_int(value: Any) -> int | None:
    if isinstance(value, (int, float)):
        return int(value)
    return None
