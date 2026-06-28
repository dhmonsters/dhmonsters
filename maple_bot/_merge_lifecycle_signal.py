# 겹침 뒤 분리되는 사건의 전후 흐름을 family별 신호로 계산합니다.
from __future__ import annotations

import math
from typing import Dict, Sequence, Tuple

import numpy as np

import _background_identity_signal as background_identity


Point = Tuple[float, float]
Candidate = Tuple[float, float, float, float, float]
IdentifiedCandidate = Tuple[int, Candidate]


def _dist(a: Sequence[float], b: Sequence[float]) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _nearest_candidate(point: Sequence[float], candidates: Sequence[Candidate]) -> Candidate | None:
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: _dist(point, candidate))


def _is_background(
    candidate: Sequence[float],
    expected_background: Sequence[IdentifiedCandidate],
    *,
    pos_tol: float,
    shape_weight: float,
) -> bool:
    bg_id, _cost = background_identity.match_background_id(
        candidate,
        expected_background,
        pos_tol=pos_tol,
        shape_weight=shape_weight,
    )
    return bg_id is not None


def _background_id(
    candidate: Sequence[float],
    expected_background: Sequence[IdentifiedCandidate],
    *,
    pos_tol: float,
    shape_weight: float,
) -> int | None:
    bg_id, _cost = background_identity.match_background_id(
        candidate,
        expected_background,
        pos_tol=pos_tol,
        shape_weight=shape_weight,
    )
    return bg_id


def _has_background_split(
    candidates: Sequence[Candidate],
    expected_background: Sequence[IdentifiedCandidate],
    *,
    sibling_radius: float,
    pos_tol: float,
    shape_weight: float,
) -> bool:
    if len(candidates) < 2:
        return False

    for selected in candidates:
        nearby = [
            candidate
            for candidate in candidates
            if _dist(selected, candidate) <= float(sibling_radius)
        ]
        if len(nearby) < 2:
            continue
        bg_ids = [
            _background_id(
                candidate,
                expected_background,
                pos_tol=pos_tol,
                shape_weight=shape_weight,
            )
            for candidate in nearby
        ]
        flags = [bg_id is not None for bg_id in bg_ids]
        if any(flags) and not all(flags):
            return True
        matched_ids = [bg_id for bg_id in bg_ids if bg_id is not None]
        if len(matched_ids) != len(set(matched_ids)):
            return True
    return False


def _nearest_background_candidate(
    candidates: Sequence[Candidate],
    expected_background: Sequence[IdentifiedCandidate],
    *,
    pos_tol: float,
    shape_weight: float,
) -> Candidate | None:
    matched = [
        candidate
        for candidate in candidates
        if _is_background(
            candidate,
            expected_background,
            pos_tol=pos_tol,
            shape_weight=shape_weight,
        )
    ]
    if not matched:
        return None
    return min(
        matched,
        key=lambda candidate: background_identity.match_background_id(
            candidate,
            expected_background,
            pos_tol=pos_tol,
            shape_weight=shape_weight,
        )[1],
    )


def background_flow_escape_frame_score(
    selected_candidate: Candidate,
    candidates: Sequence[Candidate],
    expected_background: Sequence[IdentifiedCandidate],
    *,
    sibling_radius: float = 70.0,
    pos_tol: float = 26.0,
    shape_weight: float = 0.25,
    escape_scale: float = 36.0,
) -> float:
    nearby = [
        candidate
        for candidate in candidates
        if _dist(selected_candidate, candidate) <= float(sibling_radius)
    ]
    if len(nearby) < 2:
        return 0.0

    background_candidate = _nearest_background_candidate(
        nearby,
        expected_background,
        pos_tol=pos_tol,
        shape_weight=shape_weight,
    )
    if background_candidate is None:
        return 0.0

    if _is_background(
        selected_candidate,
        expected_background,
        pos_tol=pos_tol,
        shape_weight=shape_weight,
    ):
        return -1.0

    escape_distance = _dist(selected_candidate, background_candidate)
    return min(1.0, escape_distance / max(float(escape_scale), 1e-6))


def background_flow_escape_point_score(
    point: Point,
    candidates: Sequence[Candidate],
    expected_background: Sequence[IdentifiedCandidate],
    *,
    sibling_radius: float = 70.0,
    pos_tol: float = 26.0,
    shape_weight: float = 0.25,
    escape_scale: float = 36.0,
) -> float:
    nearest = _nearest_candidate(point, candidates)
    if nearest is None:
        return 0.0

    nearby = [
        candidate
        for candidate in candidates
        if _dist(point, candidate) <= float(sibling_radius)
        or _dist(nearest, candidate) <= float(sibling_radius)
    ]
    if len(nearby) < 1:
        return 0.0

    background_candidate = _nearest_background_candidate(
        nearby,
        expected_background,
        pos_tol=pos_tol,
        shape_weight=shape_weight,
    )
    if background_candidate is None:
        return 0.0

    if _is_background(
        (float(point[0]), float(point[1]), nearest[2], nearest[3], nearest[4]),
        expected_background,
        pos_tol=pos_tol,
        shape_weight=shape_weight,
    ):
        return -1.0

    escape_distance = _dist(point, background_candidate)
    return min(1.0, escape_distance / max(float(escape_scale), 1e-6))


def release_event_frames(
    candidate_sets: Dict[int, Sequence[Candidate]],
    expected_by_frame: Dict[int, Sequence[IdentifiedCandidate]],
    *,
    frames: Sequence[int],
    sibling_radius: float = 70.0,
    pos_tol: float = 26.0,
    shape_weight: float = 0.25,
) -> list[int]:
    events = []
    previous_was_split = False
    for frame in frames:
        candidates = candidate_sets.get(int(frame), [])
        is_split = _has_background_split(
            candidates,
            expected_by_frame.get(int(frame), []),
            sibling_radius=sibling_radius,
            pos_tol=pos_tol,
            shape_weight=shape_weight,
        )
        if is_split and not previous_was_split:
            events.append(int(frame))
        previous_was_split = is_split
    return events


def _predict_from_history(
    path: Dict[int, Point],
    frames: Sequence[int],
    frame: int,
    *,
    lookback: int,
) -> Point | None:
    previous = [
        int(prev)
        for prev in frames
        if int(prev) < int(frame) and path.get(int(prev)) is not None
    ][-int(lookback):]
    if not previous:
        return None
    if len(previous) == 1:
        return path[previous[-1]]
    a = previous[-2]
    b = previous[-1]
    pa = path[a]
    pb = path[b]
    dt = max(1.0, float(b - a))
    vx = (float(pb[0]) - float(pa[0])) / dt
    vy = (float(pb[1]) - float(pa[1])) / dt
    ahead = float(frame - b)
    return (float(pb[0]) + vx * ahead, float(pb[1]) + vy * ahead)


def _post_background_ratio(
    path: Dict[int, Point],
    frame: int,
    candidate_sets: Dict[int, Sequence[Candidate]],
    expected_by_frame: Dict[int, Sequence[IdentifiedCandidate]],
    *,
    post_window: int,
    pos_tol: float,
    shape_weight: float,
) -> float:
    values = []
    for offset in range(1, int(post_window) + 1):
        next_frame = int(frame) + offset
        point = path.get(next_frame)
        candidates = candidate_sets.get(next_frame, [])
        if point is None or not candidates:
            continue
        selected = _nearest_candidate(point, candidates)
        if selected is None:
            continue
        values.append(float(_is_background(
            selected,
            expected_by_frame.get(next_frame, []),
            pos_tol=pos_tol,
            shape_weight=shape_weight,
        )))
    return float(np.mean(values)) if values else 0.0


def _history_continuity(
    path: Dict[int, Point],
    frames: Sequence[int],
    frame: int,
    *,
    lookback: int,
    continuity_scale: float,
) -> float:
    point = path.get(int(frame))
    if point is None:
        return 0.0
    predicted = _predict_from_history(
        path,
        frames,
        int(frame),
        lookback=lookback,
    )
    if predicted is None:
        return 0.0
    return max(0.0, 1.0 - _dist(predicted, point) / max(float(continuity_scale), 1e-6))


def _post_motion_continuity(
    path: Dict[int, Point],
    frame: int,
    *,
    post_window: int,
    continuity_scale: float,
) -> float:
    current = path.get(int(frame))
    previous = path.get(int(frame) - 1)
    if current is None or previous is None:
        return 0.0
    vx = float(current[0]) - float(previous[0])
    vy = float(current[1]) - float(previous[1])
    values = []
    for offset in range(1, int(post_window) + 1):
        next_frame = int(frame) + offset
        point = path.get(next_frame)
        if point is None:
            continue
        predicted = (
            float(current[0]) + vx * float(offset),
            float(current[1]) + vy * float(offset),
        )
        values.append(max(0.0, 1.0 - _dist(predicted, point) / max(float(continuity_scale), 1e-6)))
    return float(np.mean(values)) if values else 0.0


def _occlusion_source_family(family: str) -> str:
    name = str(family)
    if name.endswith("_occlusion_state"):
        return name[: -len("_occlusion_state")]
    return name


def _box_switch_source_families(family: str) -> list[str]:
    name = str(family)
    marker = "_box_switch_"
    if marker not in name:
        return []
    root, suffix = name.split(marker, 1)
    if "_to_" not in suffix or "_at" not in suffix:
        return []
    left_rel, right_suffix = suffix.split("_to_", 1)
    right_rel, after_at = right_suffix.split("_at", 1)
    tail = ""
    if "_" in after_at:
        tail = "_" + after_at.split("_", 1)[1]
    return [
        f"{root}_box_rel_{left_rel}{tail}",
        f"{root}_box_rel_{right_rel}{tail}",
    ]


def _source_family_names(family: str) -> list[str]:
    name = str(family)
    sources = []
    if name.endswith("_occlusion_state"):
        sources.append(_occlusion_source_family(name))
    if "_box_switch_" in name:
        sources.extend(_box_switch_source_families(name))
    return [source for source in sources if source != name]


def _source_continuity_to_point(
    source_path: Dict[int, Point],
    frame: int,
    point: Point,
    *,
    lookback: int,
    continuity_scale: float,
) -> float:
    history_frames = sorted(int(item) for item in source_path if int(item) < int(frame))
    if not history_frames:
        return 0.0
    predicted = _predict_from_history(
        source_path,
        history_frames,
        int(frame),
        lookback=lookback,
    )
    if predicted is None:
        return 0.0
    return max(0.0, 1.0 - _dist(predicted, point) / max(float(continuity_scale), 1e-6))


def score_paths_by_merge_lifecycle(
    paths: Dict[str, Dict[int, Point]],
    candidate_sets: Dict[int, Sequence[Candidate]],
    expected_by_frame: Dict[int, Sequence[IdentifiedCandidate]],
    frames: Sequence[int],
    *,
    sibling_radius: float = 70.0,
    pos_tol: float = 26.0,
    shape_weight: float = 0.25,
    lookback: int = 2,
    continuity_scale: float = 36.0,
    post_window: int = 3,
) -> Dict[str, dict]:
    ordered_frames = [int(frame) for frame in frames]
    events = release_event_frames(
        candidate_sets,
        expected_by_frame,
        frames=ordered_frames,
        sibling_radius=sibling_radius,
        pos_tol=pos_tol,
        shape_weight=shape_weight,
    )

    out: Dict[str, dict] = {}
    for family, path in paths.items():
        scores = []
        release_non_bg = []
        continuity_values = []
        post_bg_values = []

        for frame in events:
            point = path.get(frame)
            candidates = candidate_sets.get(frame, [])
            if point is None or not candidates:
                continue

            selected = _nearest_candidate(point, candidates)
            if selected is None:
                continue

            is_bg = _is_background(
                selected,
                expected_by_frame.get(frame, []),
                pos_tol=pos_tol,
                shape_weight=shape_weight,
            )
            non_bg_value = 0.0 if is_bg else 1.0

            predicted = _predict_from_history(
                path,
                ordered_frames,
                frame,
                lookback=lookback,
            )
            if predicted is None:
                continuity = 0.0
            else:
                continuity = max(0.0, 1.0 - _dist(predicted, selected) / max(float(continuity_scale), 1e-6))

            post_bg = _post_background_ratio(
                path,
                frame,
                candidate_sets,
                expected_by_frame,
                post_window=post_window,
                pos_tol=pos_tol,
                shape_weight=shape_weight,
            )

            score = non_bg_value + 0.5 * continuity - 0.75 * post_bg
            scores.append(score)
            release_non_bg.append(non_bg_value)
            continuity_values.append(continuity)
            post_bg_values.append(post_bg)

        out[family] = {
            "merge_lifecycle_score": float(np.sum(scores)) if scores else 0.0,
            "merge_lifecycle_score_mean": float(np.mean(scores)) if scores else 0.0,
            "merge_lifecycle_events": len(scores),
            "merge_release_non_bg_ratio": float(np.mean(release_non_bg)) if release_non_bg else 0.0,
            "merge_release_continuity": float(np.mean(continuity_values)) if continuity_values else 0.0,
            "merge_post_bg_ratio": float(np.mean(post_bg_values)) if post_bg_values else 0.0,
        }
    return out


def score_paths_by_source_identity_escape(
    paths: Dict[str, Dict[int, Point]],
    candidate_sets: Dict[int, Sequence[Candidate]],
    expected_by_frame: Dict[int, Sequence[IdentifiedCandidate]],
    frames: Sequence[int],
    *,
    sibling_radius: float = 70.0,
    pos_tol: float = 26.0,
    shape_weight: float = 0.25,
    lookback: int = 2,
    continuity_scale: float = 36.0,
    post_window: int = 3,
    escape_scale: float = 36.0,
) -> Dict[str, dict]:
    ordered_frames = [int(frame) for frame in frames]
    events = release_event_frames(
        candidate_sets,
        expected_by_frame,
        frames=ordered_frames,
        sibling_radius=sibling_radius,
        pos_tol=pos_tol,
        shape_weight=shape_weight,
    )

    out: Dict[str, dict] = {}
    for family, path in paths.items():
        scores = []
        escape_values = []
        source_values = []
        post_values = []
        source_names = _source_family_names(str(family))
        source_paths = [paths[source] for source in source_names if source in paths]
        if not source_paths:
            source_paths = [path]

        for event_frame in events:
            point = path.get(int(event_frame))
            candidates = candidate_sets.get(int(event_frame), [])
            if point is None or not candidates:
                continue
            escape = background_flow_escape_point_score(
                point,
                candidates,
                expected_by_frame.get(int(event_frame), []),
                sibling_radius=sibling_radius,
                pos_tol=pos_tol,
                shape_weight=shape_weight,
                escape_scale=escape_scale,
            )
            source_continuity = max(
                _source_continuity_to_point(
                    source_path,
                    int(event_frame),
                    point,
                    lookback=lookback,
                    continuity_scale=continuity_scale,
                )
                for source_path in source_paths
            )
            post = _post_motion_continuity(
                path,
                int(event_frame),
                post_window=post_window,
                continuity_scale=continuity_scale,
            )
            score = escape + source_continuity + 0.5 * post
            scores.append(score)
            escape_values.append(escape)
            source_values.append(source_continuity)
            post_values.append(post)

        out[family] = {
            "source_identity_escape_score": float(np.sum(scores)) if scores else 0.0,
            "source_identity_escape_score_mean": float(np.mean(scores)) if scores else 0.0,
            "source_identity_escape_events": len(scores),
            "source_identity_escape_raw_escape": float(np.mean(escape_values)) if escape_values else 0.0,
            "source_identity_escape_source_continuity": float(np.mean(source_values)) if source_values else 0.0,
            "source_identity_escape_post_continuity": float(np.mean(post_values)) if post_values else 0.0,
        }
    return out


def score_paths_by_identity_escape(
    paths: Dict[str, Dict[int, Point]],
    candidate_sets: Dict[int, Sequence[Candidate]],
    expected_by_frame: Dict[int, Sequence[IdentifiedCandidate]],
    frames: Sequence[int],
    *,
    sibling_radius: float = 70.0,
    pos_tol: float = 26.0,
    shape_weight: float = 0.25,
    lookback: int = 2,
    continuity_scale: float = 36.0,
    post_window: int = 3,
    escape_scale: float = 36.0,
) -> Dict[str, dict]:
    ordered_frames = [int(frame) for frame in frames]
    events = release_event_frames(
        candidate_sets,
        expected_by_frame,
        frames=ordered_frames,
        sibling_radius=sibling_radius,
        pos_tol=pos_tol,
        shape_weight=shape_weight,
    )

    out: Dict[str, dict] = {}
    for family, path in paths.items():
        scores = []
        escape_values = []
        continuity_values = []
        post_values = []
        for event_frame in events:
            point = path.get(int(event_frame))
            candidates = candidate_sets.get(int(event_frame), [])
            if point is None or not candidates:
                continue
            escape = background_flow_escape_point_score(
                point,
                candidates,
                expected_by_frame.get(int(event_frame), []),
                sibling_radius=sibling_radius,
                pos_tol=pos_tol,
                shape_weight=shape_weight,
                escape_scale=escape_scale,
            )
            continuity = _history_continuity(
                path,
                ordered_frames,
                int(event_frame),
                lookback=lookback,
                continuity_scale=continuity_scale,
            )
            post = _post_motion_continuity(
                path,
                int(event_frame),
                post_window=post_window,
                continuity_scale=continuity_scale,
            )
            score = escape + continuity + 0.5 * post
            scores.append(score)
            escape_values.append(escape)
            continuity_values.append(continuity)
            post_values.append(post)

        out[family] = {
            "identity_escape_score": float(np.sum(scores)) if scores else 0.0,
            "identity_escape_score_mean": float(np.mean(scores)) if scores else 0.0,
            "identity_escape_events": len(scores),
            "identity_escape_raw_escape": float(np.mean(escape_values)) if escape_values else 0.0,
            "identity_escape_continuity": float(np.mean(continuity_values)) if continuity_values else 0.0,
            "identity_escape_post_continuity": float(np.mean(post_values)) if post_values else 0.0,
        }
    return out


def score_paths_by_background_flow_escape(
    paths: Dict[str, Dict[int, Point]],
    candidate_sets: Dict[int, Sequence[Candidate]],
    expected_by_frame: Dict[int, Sequence[IdentifiedCandidate]],
    frames: Sequence[int],
    *,
    sibling_radius: float = 70.0,
    pos_tol: float = 26.0,
    shape_weight: float = 0.25,
    post_window: int = 3,
    escape_scale: float = 36.0,
) -> Dict[str, dict]:
    ordered_frames = [int(frame) for frame in frames]
    events = release_event_frames(
        candidate_sets,
        expected_by_frame,
        frames=ordered_frames,
        sibling_radius=sibling_radius,
        pos_tol=pos_tol,
        shape_weight=shape_weight,
    )

    out: Dict[str, dict] = {}
    for family, path in paths.items():
        scores = []
        escape_hits = []
        for event_frame in events:
            for offset in range(0, int(post_window) + 1):
                frame = int(event_frame) + offset
                point = path.get(frame)
                candidates = candidate_sets.get(frame, [])
                if point is None or not candidates:
                    continue
                score = background_flow_escape_point_score(
                    point,
                    candidates,
                    expected_by_frame.get(frame, []),
                    sibling_radius=sibling_radius,
                    pos_tol=pos_tol,
                    shape_weight=shape_weight,
                    escape_scale=escape_scale,
                )
                scores.append(score)
                escape_hits.append(float(score > 0.0))

        out[family] = {
            "background_flow_escape_score": float(np.sum(scores)) if scores else 0.0,
            "background_flow_escape_score_mean": float(np.mean(scores)) if scores else 0.0,
            "background_flow_escape_events": len(scores),
            "background_flow_escape_ratio": float(np.mean(escape_hits)) if escape_hits else 0.0,
        }
    return out
