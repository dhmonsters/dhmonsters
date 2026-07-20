# Studio trace를 재생해 시간축 가설 보관 전략의 정답 후보 보존율을 비교합니다.
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from math import hypot
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from core.puzzle.hypothesis_challenge import HypothesisChallengeGuard
from core.puzzle.models import Candidate, CandidateEvidence
from core.puzzle.planet_live import (
    _choose_kinematic_local_rigid_target,
    _choose_kinematic_wide_beam_target,
)
from core.vision.transparent_kinematic_shape import TransparentKinematicBeamTracker

from .studio_validation import _read_jsonl, _retained_hypothesis_points


@dataclass(frozen=True)
class HypothesisReplaySummary:
    total_frames: int
    candidate_center_frames: int
    recorded_hit_frames: int
    replay_hit_frames: int
    improved_frames: int
    regressed_frames: int
    recorded_hypothesis_generation_errors: int
    replay_hypothesis_generation_errors: int


@dataclass(frozen=True)
class HypothesisSelectionReplaySummary:
    total_frames: int
    recorded_passed_frames: int
    replay_passed_frames: int
    improved_frames: int
    regressed_frames: int
    changed_frames: int
    wide_selected_frames: int
    local_rigid_selected_frames: int


@dataclass(frozen=True)
class HypothesisVariant:
    name: str
    width: int
    branch: int
    diverse_first: bool


DEFAULT_VARIANTS = (
    HypothesisVariant("baseline", 16, 5, False),
    HypothesisVariant("branch8", 16, 8, False),
    HypothesisVariant("width24", 24, 5, False),
    HypothesisVariant("width24_branch8", 24, 8, False),
    HypothesisVariant("diverse", 16, 5, True),
    HypothesisVariant("diverse_branch8", 16, 8, True),
    HypothesisVariant("diverse_width18", 18, 5, True),
    HypothesisVariant("diverse_width20", 20, 5, True),
    HypothesisVariant("diverse_width24", 24, 5, True),
)


def replay_hypothesis_tracker(
    score_jsonl: str | Path,
    trace_jsonl: str | Path,
    *,
    width: int = 16,
    branch: int = 5,
    diverse_first: bool = False,
    pass_distance_px: float = 24.0,
) -> HypothesisReplaySummary:
    return _replay_rows(
        _read_jsonl(Path(score_jsonl)),
        _read_jsonl(Path(trace_jsonl)),
        width=width,
        branch=branch,
        diverse_first=diverse_first,
        pass_distance_px=pass_distance_px,
    )


def replay_hypothesis_selection(
    score_jsonl: str | Path,
    trace_jsonl: str | Path,
    *,
    width: int = 24,
    branch: int = 5,
    diverse_first: bool = True,
    pass_distance_px: float = 24.0,
    judge_hypothesis_limit: int | None = None,
    challenge_confirm_frames: int | None = None,
    challenge_max_step_px: float = 90.0,
    protect_incumbent_sources: tuple[str, ...] = (),
    _details: list[dict[str, object]] | None = None,
) -> HypothesisSelectionReplaySummary:
    score_rows = _read_jsonl(Path(score_jsonl))
    trace_rows = _read_jsonl(Path(trace_jsonl))
    scores = {
        frame_index: row
        for row in score_rows
        if (frame_index := _optional_int(row.get("solver_frame_index"))) is not None
    }
    events = _events_by_frame(trace_rows)
    candidate_frames = sorted(
        frame_index
        for frame_index, event_type in events
        if event_type == "CANDIDATES"
    )
    tracker = TransparentKinematicBeamTracker(
        width=width,
        branch=branch,
        cost_decay=1.0,
        acceleration_weight=0.5,
        yolo_penalty_weight=0.0,
        diverse_first=diverse_first,
    )
    challenge_guard = (
        HypothesisChallengeGuard(
            confirm_frames=challenge_confirm_frames,
            max_step_px=challenge_max_step_px,
        )
        if challenge_confirm_frames is not None else None
    )
    frame_shape = _board_frame_shape(trace_rows)
    total_frames = 0
    recorded_passed_frames = 0
    replay_passed_frames = 0
    improved_frames = 0
    regressed_frames = 0
    changed_frames = 0
    wide_selected_frames = 0
    local_rigid_selected_frames = 0

    for frame_index in candidate_frames:
        candidate_payload = events[(frame_index, "CANDIDATES")]
        temporal_payload = events.get((frame_index, "TEMPORAL_SELECTOR"), {})
        candidate_rows = [
            row
            for candidate in candidate_payload.get("candidates", [])
            if isinstance(candidate, dict) and (row := _candidate_row(candidate)) is not None
        ]
        wide_debug = _wide_debug(temporal_payload)
        anchor = _point(wide_debug.get("point")) if wide_debug.get("reason") == "white_anchor" else None
        tracker.update(candidate_rows, white_anchor=anchor)
        hypothesis_points = tracker.hypothesis_points
        if judge_hypothesis_limit is not None:
            judge_points = hypothesis_points[:max(1, int(judge_hypothesis_limit))]
        else:
            judge_points = hypothesis_points

        score = scores.get(frame_index)
        target = _target_point(score)
        target_selection = events.get((frame_index, "TARGET_SELECTION"), {})
        recorded_point = _point(target_selection.get("point"))
        if score is None or target is None or recorded_point is None:
            continue

        replay_point = recorded_point
        replay_source = str(target_selection.get("source", "recorded"))
        challenge_debug: dict[str, object] = {}
        wide_gate: dict[str, object] = {}
        local_rigid_gate: dict[str, object] = {}
        candidates = _candidate_models(frame_index, candidate_payload)
        evidence = _evidence_models(events.get((frame_index, "EVIDENCE"), {}))
        identity_payload = events.get((frame_index, "IDENTITY_STATE"), {})
        identity_state = str(identity_payload.get("state", ""))
        wide_gate_payload = target_selection.get("kinematic_wide_beam_gate")
        if isinstance(wide_gate_payload, dict):
            base_point = _point(wide_gate_payload.get("base_point"))
        else:
            base_point = None
        if base_point is not None and candidates and evidence:
            replay_source = "pre_wide"
            replay_point, wide_gate = _choose_kinematic_wide_beam_target(
                base_point=base_point,
                hypothesis_points=judge_points,
                candidates=candidates,
                evidence=evidence,
                identity_state=identity_state,
                frame_shape=frame_shape,
            )
            replay_point, local_rigid_gate = _choose_kinematic_local_rigid_target(
                base_point=replay_point,
                hypothesis_points=judge_points,
                candidates=candidates,
                evidence=evidence,
                identity_state=identity_state,
            )
            wide_selected_frames += int(bool(wide_gate.get("selected")))
            local_rigid_selected_frames += int(bool(local_rigid_gate.get("selected")))
            if bool(local_rigid_gate.get("selected")):
                replay_source = "kinematic_local_rigid"
            elif bool(wide_gate.get("selected")):
                replay_source = "kinematic_wide_beam"

        if replay_point is None:
            replay_point = recorded_point
        if challenge_guard is not None:
            challenger_point = replay_point
            replay_point, challenge_debug = challenge_guard.update(
                incumbent_point=recorded_point,
                challenger_point=challenger_point,
                protect_incumbent=str(target_selection.get("source", "")) in protect_incumbent_sources,
            )
            if not bool(challenge_debug.get("selected")):
                replay_source = str(target_selection.get("source", "recorded"))
        if replay_point is None:
            replay_point = recorded_point
        recorded_passed = _distance(recorded_point, target) <= pass_distance_px
        replay_passed = _distance(replay_point, target) <= pass_distance_px
        total_frames += 1
        recorded_passed_frames += int(recorded_passed)
        replay_passed_frames += int(replay_passed)
        improved_frames += int(replay_passed and not recorded_passed)
        regressed_frames += int(recorded_passed and not replay_passed)
        changed_frames += int(_distance(recorded_point, replay_point) > 1e-6)
        if _details is not None:
            replay_rank = (
                min(range(len(judge_points)), key=lambda index: _distance(judge_points[index], replay_point))
                if judge_points else None
            )
            _details.append({
                "frame_index": frame_index,
                "target_point": [target[0], target[1]],
                "recorded_point": [recorded_point[0], recorded_point[1]],
                "replay_point": [replay_point[0], replay_point[1]],
                "recorded_passed": recorded_passed,
                "replay_passed": replay_passed,
                "improved": replay_passed and not recorded_passed,
                "regressed": recorded_passed and not replay_passed,
                "changed": _distance(recorded_point, replay_point) > 1e-6,
                "recorded_source": str(target_selection.get("source", "")),
                "replay_source": replay_source,
                "identity_state": identity_state,
                "candidate_count": len(candidates),
                "hypothesis_count": len(hypothesis_points),
                "judge_hypothesis_count": len(judge_points),
                "replay_hypothesis_rank": replay_rank,
                "wide_gate": dict(wide_gate),
                "local_rigid_gate": dict(local_rigid_gate),
                "challenge_guard": dict(challenge_debug),
            })

    return HypothesisSelectionReplaySummary(
        total_frames=total_frames,
        recorded_passed_frames=recorded_passed_frames,
        replay_passed_frames=replay_passed_frames,
        improved_frames=improved_frames,
        regressed_frames=regressed_frames,
        changed_frames=changed_frames,
        wide_selected_frames=wide_selected_frames,
        local_rigid_selected_frames=local_rigid_selected_frames,
    )


def replay_hypothesis_selection_details(
    score_jsonl: str | Path,
    trace_jsonl: str | Path,
    *,
    width: int = 24,
    branch: int = 5,
    diverse_first: bool = True,
    pass_distance_px: float = 24.0,
    judge_hypothesis_limit: int | None = None,
    challenge_confirm_frames: int | None = None,
    challenge_max_step_px: float = 90.0,
    protect_incumbent_sources: tuple[str, ...] = (),
) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    replay_hypothesis_selection(
        score_jsonl,
        trace_jsonl,
        width=width,
        branch=branch,
        diverse_first=diverse_first,
        pass_distance_px=pass_distance_px,
        judge_hypothesis_limit=judge_hypothesis_limit,
        challenge_confirm_frames=challenge_confirm_frames,
        challenge_max_step_px=challenge_max_step_px,
        protect_incumbent_sources=protect_incumbent_sources,
        _details=details,
    )
    return details


def sweep_hypothesis_suite(
    suite_root: str | Path,
    output_dir: str | Path,
    *,
    pass_distance_px: float = 24.0,
    variants: tuple[HypothesisVariant, ...] = DEFAULT_VARIANTS,
) -> dict[str, object]:
    root = Path(suite_root)
    seed_rows: list[dict[str, object]] = []
    for seed_dir in sorted(root.glob("seed_[0-9][0-9]")):
        score_path = next(seed_dir.rglob("score.jsonl"), None)
        trace_path = next(seed_dir.rglob("trace.jsonl"), None)
        if score_path is None or trace_path is None:
            continue
        score_rows = _read_jsonl(score_path)
        trace_rows = _read_jsonl(trace_path)
        for variant in variants:
            summary = _replay_rows(
                score_rows,
                trace_rows,
                width=variant.width,
                branch=variant.branch,
                diverse_first=variant.diverse_first,
                pass_distance_px=pass_distance_px,
            )
            seed_rows.append({
                "seed": seed_dir.name,
                "variant": variant.name,
                "width": variant.width,
                "branch": variant.branch,
                "diverse_first": variant.diverse_first,
                **asdict(summary),
            })

    variant_rows: list[dict[str, object]] = []
    for variant in variants:
        rows = [row for row in seed_rows if row["variant"] == variant.name]
        variant_rows.append({
            "variant": variant.name,
            "width": variant.width,
            "branch": variant.branch,
            "diverse_first": variant.diverse_first,
            **{
                field: sum(int(row[field]) for row in rows)
                for field in HypothesisReplaySummary.__dataclass_fields__
            },
        })

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "studio_hypothesis_shadow.md"
    xlsx_path = output / "studio_hypothesis_shadow.xlsx"
    report_path.write_text(_render_report(variant_rows, seed_rows), encoding="utf-8")
    _write_xlsx(xlsx_path, variant_rows, seed_rows)
    return {
        "variants": variant_rows,
        "seeds": seed_rows,
        "report_path": report_path,
        "xlsx_path": xlsx_path,
    }


def _replay_rows(
    score_rows: list[dict[str, Any]],
    trace_rows: list[dict[str, Any]],
    *,
    width: int,
    branch: int,
    diverse_first: bool,
    pass_distance_px: float,
) -> HypothesisReplaySummary:
    scores = {
        frame_index: row
        for row in score_rows
        if (frame_index := _optional_int(row.get("solver_frame_index"))) is not None
    }
    events = _events_by_frame(trace_rows)
    candidate_frames = sorted(
        frame_index
        for frame_index, event_type in events
        if event_type == "CANDIDATES"
    )
    tracker = TransparentKinematicBeamTracker(
        width=width,
        branch=branch,
        cost_decay=1.0,
        acceleration_weight=0.5,
        yolo_penalty_weight=0.0,
        diverse_first=diverse_first,
    )
    total_frames = 0
    candidate_center_frames = 0
    recorded_hit_frames = 0
    replay_hit_frames = 0
    improved_frames = 0
    regressed_frames = 0
    recorded_generation_errors = 0
    replay_generation_errors = 0

    for frame_index in candidate_frames:
        candidate_payload = events[(frame_index, "CANDIDATES")]
        temporal_payload = events.get((frame_index, "TEMPORAL_SELECTOR"), {})
        candidates = [
            row
            for candidate in candidate_payload.get("candidates", [])
            if isinstance(candidate, dict) and (row := _candidate_row(candidate)) is not None
        ]
        wide_debug = _wide_debug(temporal_payload)
        anchor = _point(wide_debug.get("point")) if wide_debug.get("reason") == "white_anchor" else None
        tracker.update(candidates, white_anchor=anchor)
        replay_points = tracker.hypothesis_points
        recorded_points = _retained_hypothesis_points(temporal_payload)
        score = scores.get(frame_index)
        target = _target_point(score)
        if score is None or target is None:
            continue
        total_frames += 1
        center_hit = any(_distance(candidate[:2], target) <= pass_distance_px for candidate in candidates)
        recorded_hit = any(_distance(point, target) <= pass_distance_px for point in recorded_points)
        replay_hit = any(_distance(point, target) <= pass_distance_px for point in replay_points)
        candidate_center_frames += int(center_hit)
        recorded_hit_frames += int(recorded_hit)
        replay_hit_frames += int(replay_hit)
        improved_frames += int(replay_hit and not recorded_hit)
        regressed_frames += int(recorded_hit and not replay_hit)
        failed = not bool(score.get("passed"))
        recorded_generation_errors += int(failed and center_hit and not recorded_hit)
        replay_generation_errors += int(failed and center_hit and not replay_hit)

    return HypothesisReplaySummary(
        total_frames=total_frames,
        candidate_center_frames=candidate_center_frames,
        recorded_hit_frames=recorded_hit_frames,
        replay_hit_frames=replay_hit_frames,
        improved_frames=improved_frames,
        regressed_frames=regressed_frames,
        recorded_hypothesis_generation_errors=recorded_generation_errors,
        replay_hypothesis_generation_errors=replay_generation_errors,
    )


def _events_by_frame(rows: list[dict[str, Any]]) -> dict[tuple[int, str], dict[str, Any]]:
    events: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows:
        frame_index = _optional_int(row.get("frame_index"))
        payload = row.get("payload")
        if frame_index is not None and isinstance(payload, dict):
            events[(frame_index, str(row.get("type", "")))] = payload
    return events


def _candidate_row(candidate: dict[str, Any]) -> tuple[float, float, float, float, float] | None:
    center = _point(candidate.get("center"))
    if center is None:
        return None
    bbox = candidate.get("bbox")
    width = 24.0
    height = 24.0
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        try:
            width = max(1.0, float(bbox[2]) - float(bbox[0]))
            height = max(1.0, float(bbox[3]) - float(bbox[1]))
        except (TypeError, ValueError):
            pass
    return (center[0], center[1], _float(candidate.get("score")), width, height)


def _candidate_models(frame_index: int, payload: dict[str, Any]) -> list[Candidate]:
    candidates: list[Candidate] = []
    for row in payload.get("candidates", []):
        if not isinstance(row, dict):
            continue
        center = _point(row.get("center"))
        bbox = row.get("bbox")
        if center is None or not isinstance(bbox, (list, tuple)) or len(bbox) < 4:
            continue
        try:
            candidate_bbox = tuple(float(value) for value in bbox[:4])
        except (TypeError, ValueError):
            continue
        candidates.append(Candidate(
            candidate_id=str(row.get("candidate_id", "")),
            frame_index=frame_index,
            bbox=candidate_bbox,
            center=center,
            score=_float(row.get("score")),
            source=str(row.get("source", "")),
            class_name=str(row.get("class_name", "")),
        ))
    return candidates


def _evidence_models(payload: dict[str, Any]) -> dict[str, CandidateEvidence]:
    evidence: dict[str, CandidateEvidence] = {}
    for row in payload.get("evidence", []):
        if not isinstance(row, dict):
            continue
        candidate_id = str(row.get("candidate_id", ""))
        if not candidate_id:
            continue
        notes = row.get("notes")
        evidence[candidate_id] = CandidateEvidence(
            candidate_id=candidate_id,
            bg_score=_float(row.get("bg_score")),
            motion_divergence=_float(row.get("motion_divergence")),
            rigid_violation=_float(row.get("rigid_violation")),
            local_rigid_residual=_float(row.get("local_rigid_residual")),
            phase_similarity=_float(row.get("phase_similarity")),
            texture_bg_score=_float(row.get("texture_bg_score")),
            color_residual=_float(row.get("color_residual")),
            merge_likelihood=_float(row.get("merge_likelihood")),
            notes=tuple(str(note) for note in notes) if isinstance(notes, (list, tuple)) else (),
        )
    return evidence


def _board_frame_shape(rows: list[dict[str, Any]]) -> tuple[int, int] | None:
    for row in rows:
        if row.get("type") != "SESSION_START":
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        board_roi = payload.get("board_roi")
        if not isinstance(board_roi, dict):
            continue
        width = _optional_int(board_roi.get("w"))
        height = _optional_int(board_roi.get("h"))
        if width is not None and height is not None and width > 0 and height > 0:
            return (height, width)
    return None


def _wide_debug(payload: dict[str, Any]) -> dict[str, Any]:
    debug = payload.get("debug")
    if not isinstance(debug, dict):
        return {}
    wide_debug = debug.get("kinematic_wide_beam_debug")
    return wide_debug if isinstance(wide_debug, dict) else {}


def _target_point(score: dict[str, Any] | None) -> tuple[float, float] | None:
    if score is None:
        return None
    return _point((score.get("target_x"), score.get("target_y")))


def _point(value: object) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _distance(left: tuple[float, float], right: tuple[float, float]) -> float:
    return hypot(left[0] - right[0], left[1] - right[1])


def _optional_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _render_report(
    variants: list[dict[str, object]],
    seeds: list[dict[str, object]],
) -> str:
    lines = [
        "# Studio 시간축 가설 보관 A/B",
        "",
        "|variant|width|branch|diverse|retained|improved|regressed|generation errors|",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in variants:
        lines.append(
            f"|{row['variant']}|{row['width']}|{row['branch']}|{row['diverse_first']}|"
            f"{row['replay_hit_frames']}|{row['improved_frames']}|{row['regressed_frames']}|"
            f"{row['replay_hypothesis_generation_errors']}|"
        )
    lines.extend(["", "## Seed별 결과", ""])
    for row in seeds:
        lines.append(
            f"- {row['seed']} / {row['variant']}: retained {row['replay_hit_frames']}, "
            f"improved {row['improved_frames']}, regressed {row['regressed_frames']}"
        )
    return "\n".join(lines) + "\n"


def _write_xlsx(
    path: Path,
    variants: list[dict[str, object]],
    seeds: list[dict[str, object]],
) -> None:
    workbook = Workbook()
    variant_sheet = workbook.active
    variant_sheet.title = "variants"
    variant_fields = list(variants[0]) if variants else ["variant"]
    variant_sheet.append(variant_fields)
    for row in variants:
        variant_sheet.append([row.get(field) for field in variant_fields])
    seed_sheet = workbook.create_sheet("seeds")
    seed_fields = list(seeds[0]) if seeds else ["seed"]
    seed_sheet.append(seed_fields)
    for row in seeds:
        seed_sheet.append([row.get(field) for field in seed_fields])
    workbook.save(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Studio 시간축 가설 보관 전략을 A/B 합니다.")
    parser.add_argument("--suite-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--pass-distance-px", type=float, default=24.0)
    args = parser.parse_args(argv)
    result = sweep_hypothesis_suite(
        args.suite_root,
        args.output_dir,
        pass_distance_px=args.pass_distance_px,
    )
    print(json.dumps(result["variants"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
