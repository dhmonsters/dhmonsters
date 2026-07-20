# Studio trace에서 독립 강체 신호의 선택 효과를 사후 비교합니다.
from __future__ import annotations

import json
from dataclasses import dataclass
from math import hypot
from pathlib import Path
from typing import Any, Sequence

from .studio_validation import _retained_hypothesis_points


@dataclass(frozen=True)
class LocalRigidGateConfig:
    min_residual: float
    min_advantage: float
    min_shift_px: float


@dataclass(frozen=True)
class LocalRigidShadowFrame:
    run_id: str
    run_index: int
    frame_id: int
    solver_frame_index: int
    base_point: tuple[float, float] | None
    shadow_point: tuple[float, float] | None
    base_distance_px: float | None
    shadow_distance_px: float | None
    base_passed: bool
    shadow_passed: bool
    selected: bool
    selected_candidate_id: str
    reason: str
    base_residual: float | None
    selected_residual: float | None
    residual_advantage: float | None
    shift_px: float | None


@dataclass(frozen=True)
class LocalRigidShadowResult:
    total_frames: int
    base_passed_frames: int
    shadow_passed_frames: int
    improved_frames: int
    regressed_frames: int
    selected_frames: int
    frames: tuple[LocalRigidShadowFrame, ...]


@dataclass(frozen=True)
class LocalRigidSweepRow:
    config: LocalRigidGateConfig
    total_frames: int
    base_passed_frames: int
    shadow_passed_frames: int
    improved_frames: int
    regressed_frames: int
    selected_frames: int
    delta_frames: int
    regressed_runs: int
    run_deltas: tuple[int, ...]


def score_local_rigid_shadow(
    gt_jsonl: str | Path,
    trace_jsonl: str | Path,
    config: LocalRigidGateConfig,
    *,
    pass_distance_px: float = 24.0,
) -> LocalRigidShadowResult:
    events = _events_by_frame(_read_jsonl(Path(trace_jsonl)))
    gt_rows = _read_jsonl(Path(gt_jsonl))
    return _score_loaded_rows(
        gt_rows,
        events,
        config,
        pass_distance_px=pass_distance_px,
    )


def sweep_local_rigid_shadow(
    sessions: Sequence[tuple[str | Path, str | Path]],
    configs: Sequence[LocalRigidGateConfig],
    *,
    pass_distance_px: float = 24.0,
) -> tuple[LocalRigidSweepRow, ...]:
    loaded = [
        (
            _read_jsonl(Path(gt_jsonl)),
            _events_by_frame(_read_jsonl(Path(trace_jsonl))),
        )
        for gt_jsonl, trace_jsonl in sessions
    ]
    rows: list[LocalRigidSweepRow] = []
    for config in configs:
        results = [
            _score_loaded_rows(
                gt_rows,
                events,
                config,
                pass_distance_px=pass_distance_px,
            )
            for gt_rows, events in loaded
        ]
        run_deltas = tuple(
            result.shadow_passed_frames - result.base_passed_frames
            for result in results
        )
        base_passed = sum(result.base_passed_frames for result in results)
        shadow_passed = sum(result.shadow_passed_frames for result in results)
        rows.append(
            LocalRigidSweepRow(
                config=config,
                total_frames=sum(result.total_frames for result in results),
                base_passed_frames=base_passed,
                shadow_passed_frames=shadow_passed,
                improved_frames=sum(result.improved_frames for result in results),
                regressed_frames=sum(result.regressed_frames for result in results),
                selected_frames=sum(result.selected_frames for result in results),
                delta_frames=shadow_passed - base_passed,
                regressed_runs=sum(delta < 0 for delta in run_deltas),
                run_deltas=run_deltas,
            )
        )
    return tuple(rows)


def _score_loaded_rows(
    gt_rows: list[dict[str, Any]],
    events: dict[tuple[int, str], dict[str, Any]],
    config: LocalRigidGateConfig,
    *,
    pass_distance_px: float,
) -> LocalRigidShadowResult:
    frames = tuple(
        _score_frame(gt, events, config, pass_distance_px=pass_distance_px)
        for gt in gt_rows
        if gt.get("solver_frame_index") is not None
    )
    return LocalRigidShadowResult(
        total_frames=len(frames),
        base_passed_frames=sum(frame.base_passed for frame in frames),
        shadow_passed_frames=sum(frame.shadow_passed for frame in frames),
        improved_frames=sum(frame.shadow_passed and not frame.base_passed for frame in frames),
        regressed_frames=sum(frame.base_passed and not frame.shadow_passed for frame in frames),
        selected_frames=sum(frame.selected for frame in frames),
        frames=frames,
    )


def _score_frame(
    gt: dict[str, Any],
    events: dict[tuple[int, str], dict[str, Any]],
    config: LocalRigidGateConfig,
    *,
    pass_distance_px: float,
) -> LocalRigidShadowFrame:
    frame_index = int(gt["solver_frame_index"])
    target_payload = events.get((frame_index, "TARGET_SELECTION"), {})
    base_point = _point(target_payload.get("point"))
    shadow = _select_local_rigid_point(
        base_point=base_point,
        target_payload=target_payload,
        identity_payload=events.get((frame_index, "IDENTITY_STATE"), {}),
        temporal_payload=events.get((frame_index, "TEMPORAL_SELECTOR"), {}),
        candidate_payload=events.get((frame_index, "CANDIDATES"), {}),
        evidence_payload=events.get((frame_index, "EVIDENCE"), {}),
        config=config,
    )
    gt_point = (float(gt["target_x"]), float(gt["target_y"]))
    base_distance = _optional_distance(base_point, gt_point)
    shadow_distance = _optional_distance(shadow["point"], gt_point)
    base_passed = base_distance is not None and base_distance <= pass_distance_px
    shadow_passed = shadow_distance is not None and shadow_distance <= pass_distance_px
    return LocalRigidShadowFrame(
        run_id=str(gt.get("run_id") or ""),
        run_index=int(gt.get("run_index", 0)),
        frame_id=int(gt.get("frame_id", 0)),
        solver_frame_index=frame_index,
        base_point=base_point,
        shadow_point=shadow["point"],
        base_distance_px=base_distance,
        shadow_distance_px=shadow_distance,
        base_passed=base_passed,
        shadow_passed=shadow_passed,
        selected=bool(shadow["selected"]),
        selected_candidate_id=str(shadow.get("selected_candidate_id") or ""),
        reason=str(shadow["reason"]),
        base_residual=_optional_float(shadow.get("base_residual")),
        selected_residual=_optional_float(shadow.get("selected_residual")),
        residual_advantage=_optional_float(shadow.get("residual_advantage")),
        shift_px=_optional_float(shadow.get("shift_px")),
    )


def _select_local_rigid_point(
    *,
    base_point: tuple[float, float] | None,
    target_payload: dict[str, Any],
    identity_payload: dict[str, Any],
    temporal_payload: dict[str, Any],
    candidate_payload: dict[str, Any],
    evidence_payload: dict[str, Any],
    config: LocalRigidGateConfig,
) -> dict[str, Any]:
    if base_point is None:
        return _unchanged(base_point, "missing_base_point")
    identity_state = str(identity_payload.get("state") or target_payload.get("identity_state") or "")
    if str(target_payload.get("source") or "") == "visible_lock" or identity_state == "INIT_VISIBLE":
        return _unchanged(base_point, "visible_identity_locked")

    candidates = [
        row for row in candidate_payload.get("candidates", []) if isinstance(row, dict)
    ]
    evidence_by_id = {
        str(row.get("candidate_id") or ""): row
        for row in evidence_payload.get("evidence", [])
        if isinstance(row, dict)
    }
    retained_points = _retained_hypothesis_points(temporal_payload)
    if not candidates or not evidence_by_id or not retained_points:
        return _unchanged(base_point, "missing_hypotheses_or_evidence")

    base_candidate = _nearest_candidate(candidates, base_point)
    if base_candidate is None:
        return _unchanged(base_point, "missing_base_candidate")
    base_id = str(base_candidate.get("candidate_id") or "")
    base_evidence = evidence_by_id.get(base_id)
    if base_evidence is None:
        return _unchanged(base_point, "missing_base_evidence")

    hypotheses: list[tuple[tuple[float, float], dict[str, Any], dict[str, Any]]] = []
    seen_ids: set[str] = set()
    for point in retained_points:
        candidate = _nearest_candidate(candidates, point)
        if candidate is None:
            continue
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id in seen_ids:
            continue
        candidate_evidence = evidence_by_id.get(candidate_id)
        if candidate_evidence is None:
            continue
        seen_ids.add(candidate_id)
        hypotheses.append((point, candidate, candidate_evidence))
    if not hypotheses:
        return _unchanged(base_point, "missing_hypothesis_evidence")

    selected_point, selected_candidate, selected_evidence = max(
        hypotheses,
        key=lambda row: _float(row[2].get("local_rigid_residual")),
    )
    selected_id = str(selected_candidate.get("candidate_id") or "")
    base_residual = _float(base_evidence.get("local_rigid_residual"))
    selected_residual = _float(selected_evidence.get("local_rigid_residual"))
    advantage = selected_residual - base_residual
    shift = _distance(base_point, selected_point)
    common = {
        "base_residual": base_residual,
        "selected_residual": selected_residual,
        "residual_advantage": advantage,
        "shift_px": shift,
        "selected_candidate_id": selected_id,
    }
    if base_residual <= 0.0:
        return _unchanged(base_point, "base_residual_unavailable", **common)
    if selected_id == base_id:
        return _unchanged(base_point, "same_candidate", **common)
    if selected_residual < config.min_residual:
        return _unchanged(base_point, "residual_too_weak", **common)
    if advantage < config.min_advantage:
        return _unchanged(base_point, "advantage_too_weak", **common)
    if shift < config.min_shift_px:
        return _unchanged(base_point, "paths_not_separated", **common)
    return {
        "point": selected_point,
        "selected": True,
        "reason": "local_rigid_advantage",
        **common,
    }


def _unchanged(point: tuple[float, float] | None, reason: str, **debug: Any) -> dict[str, Any]:
    return {"point": point, "selected": False, "reason": reason, **debug}


def _events_by_frame(rows: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    events: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows:
        frame_index = row.get("frame_index")
        payload = row.get("payload")
        if isinstance(frame_index, int) and isinstance(payload, dict):
            events[(frame_index, str(row.get("type") or ""))] = payload
    return events


def _nearest_candidate(
    candidates: list[dict[str, Any]],
    point: tuple[float, float],
) -> dict[str, Any] | None:
    rows = [(candidate, _point(candidate.get("center"))) for candidate in candidates]
    valid = [(candidate, center) for candidate, center in rows if center is not None]
    return min(valid, key=lambda row: _distance(row[1], point))[0] if valid else None


def _point(value: object) -> tuple[float, float] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return hypot(left[0] - right[0], left[1] - right[1])


def _optional_distance(
    left: tuple[float, float] | None,
    right: tuple[float, float],
) -> float | None:
    return _distance(left, right) if left is not None else None


def _float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    return rows
