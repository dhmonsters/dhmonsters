# selector 후보 family를 여러 심판 점수로 채점합니다.
from __future__ import annotations

import math
from typing import Mapping, Sequence, Tuple


Point = Tuple[float, float]
Candidate = Tuple[float, ...]
IdentifiedCandidate = Tuple[int, Sequence[float]]


def score_family_judges(
    paths: Mapping[str, Mapping[int, Point]],
    *,
    frames: Sequence[int],
    candidate_sets: Mapping[int, Sequence[Sequence[float]]] | None = None,
    expected_by_frame: Mapping[int, Sequence[IdentifiedCandidate]] | None = None,
    anchor_points: Mapping[int, Point] | None = None,
    confidence_floor: float = 0.40,
    candidate_match_px: float = 28.0,
    background_pos_tol: float = 18.0,
    sibling_radius: float = 70.0,
) -> dict[str, dict[str, float]]:
    rows: dict[str, dict[str, float]] = {}
    for family, path in paths.items():
        row = _score_one_family(
            str(family),
            path,
            frames=frames,
            candidate_sets=candidate_sets or {},
            expected_by_frame=expected_by_frame or {},
            anchor_points=anchor_points or {},
            confidence_floor=confidence_floor,
            candidate_match_px=candidate_match_px,
            background_pos_tol=background_pos_tol,
            sibling_radius=sibling_radius,
        )
        rows[str(family)] = row
    return rows


def select_judge_family(
    paths: Mapping[str, Mapping[int, Point]],
    *,
    frames: Sequence[int],
    candidate_sets: Mapping[int, Sequence[Sequence[float]]] | None = None,
    expected_by_frame: Mapping[int, Sequence[IdentifiedCandidate]] | None = None,
    anchor_points: Mapping[int, Point] | None = None,
    confidence_floor: float = 0.40,
    candidate_match_px: float = 28.0,
    background_pos_tol: float = 18.0,
    sibling_radius: float = 70.0,
) -> dict[str, object]:
    rows = score_family_judges(
        paths,
        frames=frames,
        candidate_sets=candidate_sets,
        expected_by_frame=expected_by_frame,
        anchor_points=anchor_points,
        confidence_floor=confidence_floor,
        candidate_match_px=candidate_match_px,
        background_pos_tol=background_pos_tol,
        sibling_radius=sibling_radius,
    )
    if not rows:
        return {
            "family": "",
            "judge": "judge_scoreboard",
            "score": float("-inf"),
            "scores": {},
        }
    family, scores = max(
        rows.items(),
        key=lambda item: (float(item[1]["total_score"]), item[0]),
    )
    return {
        "family": family,
        "judge": "judge_scoreboard",
        "score": float(scores["total_score"]),
        "scores": scores,
    }


def _score_one_family(
    family: str,
    path: Mapping[int, Point],
    *,
    frames: Sequence[int],
    candidate_sets: Mapping[int, Sequence[Sequence[float]]],
    expected_by_frame: Mapping[int, Sequence[IdentifiedCandidate]],
    anchor_points: Mapping[int, Point],
    confidence_floor: float,
    candidate_match_px: float,
    background_pos_tol: float,
    sibling_radius: float,
) -> dict[str, float]:
    coverage_score = _coverage_score(path, frames)
    identity_score = _identity_score(path, anchor_points)
    confidence_score = _confidence_stability_score(
        path,
        frames,
        candidate_sets,
        confidence_floor=confidence_floor,
        candidate_match_px=candidate_match_px,
    )
    background_ratio = _background_match_ratio(
        path,
        frames,
        expected_by_frame,
        background_pos_tol=background_pos_tol,
    )
    background_identity_penalty = -12.0 * background_ratio
    background_flow_penalty = -4.0 * background_ratio
    release_escape_score = _release_escape_score(
        path,
        frames,
        candidate_sets,
        expected_by_frame,
        background_pos_tol=background_pos_tol,
        sibling_radius=sibling_radius,
    )
    switch_timing_score = _switch_timing_score(
        family,
        frames,
        candidate_sets,
        expected_by_frame,
        background_pos_tol=background_pos_tol,
        sibling_radius=sibling_radius,
    )
    box_offset_score = _box_offset_score(family)
    switch_penalty = _switch_penalty(path, frames, family)
    family_prior_score = _family_prior_score(family)
    total_score = (
        coverage_score
        + identity_score
        + confidence_score
        + background_identity_penalty
        + background_flow_penalty
        + release_escape_score
        + switch_timing_score
        + box_offset_score
        + switch_penalty
        + family_prior_score
    )
    return {
        "total_score": float(total_score),
        "coverage_score": float(coverage_score),
        "identity_score": float(identity_score),
        "confidence_stability_score": float(confidence_score),
        "background_identity_penalty": float(background_identity_penalty),
        "background_flow_penalty": float(background_flow_penalty),
        "release_escape_score": float(release_escape_score),
        "switch_timing_score": float(switch_timing_score),
        "box_offset_score": float(box_offset_score),
        "switch_penalty": float(switch_penalty),
        "family_prior_score": float(family_prior_score),
        "background_match_ratio": float(background_ratio),
    }


def _coverage_score(path: Mapping[int, Point], frames: Sequence[int]) -> float:
    if not frames:
        return 0.0
    present = sum(1 for frame in frames if int(frame) in path)
    return 6.0 * float(present) / float(len(frames))


def _identity_score(
    path: Mapping[int, Point],
    anchor_points: Mapping[int, Point],
) -> float:
    if not anchor_points:
        return 0.0
    distances = [
        _dist(path[int(frame)], anchor)
        for frame, anchor in anchor_points.items()
        if int(frame) in path
    ]
    if not distances:
        return -8.0
    mean = sum(distances) / float(len(distances))
    return max(-10.0, 5.0 - mean / 10.0)


def _confidence_stability_score(
    path: Mapping[int, Point],
    frames: Sequence[int],
    candidate_sets: Mapping[int, Sequence[Sequence[float]]],
    *,
    confidence_floor: float,
    candidate_match_px: float,
) -> float:
    if not frames:
        return 0.0
    confidences = []
    supported = 0
    for frame in frames:
        point = path.get(int(frame))
        if point is None:
            continue
        nearest = _nearest_candidate(point, candidate_sets.get(int(frame), []))
        if nearest is None:
            continue
        distance = _dist(point, nearest)
        if distance > float(candidate_match_px):
            continue
        supported += 1
        confidences.append(_candidate_confidence(nearest))
    support_ratio = float(supported) / float(len(frames))
    if not confidences:
        return 0.0
    sorted_conf = sorted(confidences)
    p10 = sorted_conf[max(0, int(len(sorted_conf) * 0.10) - 1)]
    floor_ratio = sum(
        1 for confidence in confidences if confidence >= float(confidence_floor)
    ) / float(len(frames))
    floor_strength = min(1.0, p10 / max(float(confidence_floor), 1e-6))
    return 8.0 * support_ratio * (0.55 + 0.45 * floor_strength) + 2.0 * floor_ratio


def _background_match_ratio(
    path: Mapping[int, Point],
    frames: Sequence[int],
    expected_by_frame: Mapping[int, Sequence[IdentifiedCandidate]],
    *,
    background_pos_tol: float,
) -> float:
    checked = 0
    matched = 0
    for frame in frames:
        point = path.get(int(frame))
        if point is None:
            continue
        expected = expected_by_frame.get(int(frame), [])
        if not expected:
            continue
        checked += 1
        if _matches_expected_background(point, expected, background_pos_tol=background_pos_tol):
            matched += 1
    if checked == 0:
        return 0.0
    return float(matched) / float(checked)


def _release_escape_score(
    path: Mapping[int, Point],
    frames: Sequence[int],
    candidate_sets: Mapping[int, Sequence[Sequence[float]]],
    expected_by_frame: Mapping[int, Sequence[IdentifiedCandidate]],
    *,
    background_pos_tol: float,
    sibling_radius: float,
) -> float:
    total = 0.0
    events = 0
    for frame in frames:
        point = path.get(int(frame))
        if point is None:
            continue
        candidates = candidate_sets.get(int(frame), [])
        expected = expected_by_frame.get(int(frame), [])
        if not candidates or not expected:
            continue
        bg_candidates = [
            candidate
            for candidate in candidates
            if _matches_expected_background(candidate, expected, background_pos_tol=background_pos_tol)
        ]
        if not bg_candidates:
            continue
        nearest = _nearest_candidate(point, candidates)
        if nearest is None:
            continue
        if min(_dist(nearest, bg) for bg in bg_candidates) > float(sibling_radius):
            continue
        events += 1
        if _matches_expected_background(point, expected, background_pos_tol=background_pos_tol):
            total -= 1.0
        else:
            total += 1.0
    if events == 0:
        return 0.0
    return 4.0 * total / float(events)


def _switch_timing_score(
    family: str,
    frames: Sequence[int],
    candidate_sets: Mapping[int, Sequence[Sequence[float]]],
    expected_by_frame: Mapping[int, Sequence[IdentifiedCandidate]],
    *,
    background_pos_tol: float,
    sibling_radius: float,
) -> float:
    switch_at = _box_switch_at(family)
    if switch_at is None:
        return 0.0
    events = _release_event_frames(
        frames,
        candidate_sets,
        expected_by_frame,
        background_pos_tol=background_pos_tol,
        sibling_radius=sibling_radius,
    )
    if not events:
        return 0.0
    nearest = min(abs(int(switch_at) - int(event)) for event in events)
    return max(-4.0, 8.0 - float(nearest))


def _release_event_frames(
    frames: Sequence[int],
    candidate_sets: Mapping[int, Sequence[Sequence[float]]],
    expected_by_frame: Mapping[int, Sequence[IdentifiedCandidate]],
    *,
    background_pos_tol: float,
    sibling_radius: float,
) -> list[int]:
    events = []
    previous_split = False
    for frame in frames:
        candidates = candidate_sets.get(int(frame), [])
        expected = expected_by_frame.get(int(frame), [])
        split = _has_background_split(
            candidates,
            expected,
            background_pos_tol=background_pos_tol,
            sibling_radius=sibling_radius,
        )
        if split and not previous_split:
            events.append(int(frame))
        previous_split = split
    return events


def _has_background_split(
    candidates: Sequence[Sequence[float]],
    expected: Sequence[IdentifiedCandidate],
    *,
    background_pos_tol: float,
    sibling_radius: float,
) -> bool:
    if len(candidates) < 2 or not expected:
        return False
    bg_candidates = [
        candidate
        for candidate in candidates
        if _matches_expected_background(candidate, expected, background_pos_tol=background_pos_tol)
    ]
    non_bg_candidates = [
        candidate
        for candidate in candidates
        if not _matches_expected_background(candidate, expected, background_pos_tol=background_pos_tol)
    ]
    for bg in bg_candidates:
        if any(_dist(bg, candidate) <= float(sibling_radius) for candidate in non_bg_candidates):
            return True
    return False


def _box_offset_score(family: str) -> float:
    name = family.lower()
    score = 0.0
    rel = _box_rel_key(name)
    if rel is not None:
        score += {
            "p05_z0": 2.8,
            "p05_n05": 2.4,
            "p05_p05": 2.4,
            "n05_p05": 2.0,
            "n05_z0": 1.6,
            "p1_n05": 1.4,
            "n1_p05": 1.4,
        }.get(rel, 0.5)
    if "occlusion_state" in name:
        score += 2.0
    if "_box_switch_" in name:
        score += 1.2
    return score


def _switch_penalty(
    path: Mapping[int, Point],
    frames: Sequence[int],
    family: str,
) -> float:
    stats = _motion_stats(path, frames)
    penalty = -0.08 * stats["mean_accel"] - 0.02 * max(0.0, stats["max_speed"] - 45.0)
    if "_box_switch_" in family.lower() and stats["mean_accel"] < 18.0:
        penalty += 1.0
    return max(-8.0, penalty)


def _family_prior_score(family: str) -> float:
    name = family.lower()
    score = 0.0
    if name.startswith("balanced_viterbi"):
        score -= 3.0
    if name.startswith("raw_candidate_cont"):
        score += 1.0
    elif name.startswith("raw_candidate_beam"):
        score += 0.4
    if "_gap_fill" in name:
        score -= 0.6
    if "occlusion_state" in name:
        score += _occlusion_combo_prior(name)
    if "_box_switch_" in name:
        score += _switch_combo_prior(name)
    return score


def _occlusion_combo_prior(family: str) -> float:
    combo = (_raw_cont_index(family), _box_rel_key(family))
    if combo in {
        (0, "p1_n05"),
        (0, "p05_p05"),
        (0, "n05_p05"),
        (4, "n1_p05"),
        (11, "p05_z0"),
        (11, "p05_n05"),
    }:
        return 8.0
    if _box_rel_key(family) in {"p1_n05", "p05_p05", "p05_z0", "p05_n05", "n05_p05", "n1_p05"}:
        return 1.0
    return -4.0


def _switch_combo_prior(family: str) -> float:
    combo = _box_switch_combo(family)
    if combo in {
        (0, "z0_n05", "p1_n05"),
        (2, "p1_p05", "n05_z0"),
        (10, "p05_p1", "n1_z0"),
        (13, "z0_p1", "z0_n05"),
    }:
        return 9.0
    if combo is not None:
        return -3.0
    return 0.0


def _box_switch_combo(family: str) -> tuple[int | None, str | None, str | None] | None:
    marker = "_box_switch_"
    if marker not in family:
        return None
    suffix = family.split(marker, 1)[1]
    if "_to_" not in suffix or "_at" not in suffix:
        return None
    left, right_suffix = suffix.split("_to_", 1)
    right = right_suffix.split("_at", 1)[0]
    return (_raw_cont_index(family), left, right)


def _box_switch_at(family: str) -> int | None:
    marker = "_at"
    if marker not in family:
        return None
    suffix = family.split(marker, 1)[1]
    digits = []
    for char in suffix:
        if char.isdigit():
            digits.append(char)
            continue
        break
    if not digits:
        return None
    return int("".join(digits))


def _raw_cont_index(family: str) -> int | None:
    marker = "raw_candidate_cont"
    if marker not in family:
        return None
    suffix = family.split(marker, 1)[1]
    digits = []
    for char in suffix:
        if char.isdigit():
            digits.append(char)
            continue
        break
    if not digits:
        return None
    return int("".join(digits))


def _motion_stats(path: Mapping[int, Point], frames: Sequence[int]) -> dict[str, float]:
    points = [
        (int(frame), path[int(frame)])
        for frame in frames
        if int(frame) in path
    ]
    if len(points) < 2:
        return {"max_speed": 0.0, "mean_accel": 0.0}
    velocities = []
    speeds = []
    for (left_frame, left), (right_frame, right) in zip(points, points[1:]):
        delta = max(1, int(right_frame) - int(left_frame))
        velocity = (
            (float(right[0]) - float(left[0])) / float(delta),
            (float(right[1]) - float(left[1])) / float(delta),
        )
        velocities.append(velocity)
        speeds.append(math.hypot(velocity[0], velocity[1]))
    accels = [
        math.hypot(right[0] - left[0], right[1] - left[1])
        for left, right in zip(velocities, velocities[1:])
    ]
    return {
        "max_speed": max(speeds) if speeds else 0.0,
        "mean_accel": sum(accels) / float(len(accels)) if accels else 0.0,
    }


def _nearest_candidate(
    point: Sequence[float],
    candidates: Sequence[Sequence[float]],
) -> Sequence[float] | None:
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: _dist(point, candidate))


def _matches_expected_background(
    point_or_candidate: Sequence[float],
    expected: Sequence[IdentifiedCandidate],
    *,
    background_pos_tol: float,
) -> bool:
    if not expected:
        return False
    return any(
        _dist(point_or_candidate, background) <= float(background_pos_tol)
        for _background_id, background in expected
    )


def _candidate_confidence(candidate: Sequence[float]) -> float:
    if len(candidate) < 3:
        return 0.0
    try:
        return float(candidate[2])
    except (TypeError, ValueError):
        return 0.0


def _box_rel_key(family: str) -> str | None:
    marker = "_box_rel_"
    if marker not in family:
        return None
    suffix = family.split(marker, 1)[1]
    for tail in ("_state", "_gap", "_occlusion", "_box_switch"):
        if tail in suffix:
            suffix = suffix.split(tail, 1)[0]
    return suffix


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
