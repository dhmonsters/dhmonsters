# 투명도형 퍼즐 후보열에서 타겟 신분을 시간축으로 보류하고 복원한다.
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence


Point = tuple[float, float]
Candidate = tuple[float, float, float, float, float]
IdentityState = str


@dataclass(frozen=True)
class TemporalFrame:
    frame_index: int
    candidates: tuple[Candidate, ...]
    track_hint: Point | None = None
    background_penalties: tuple[float, ...] = ()
    target_supports: tuple[float, ...] = ()
    background_ids: tuple[int | None, ...] = ()


@dataclass(frozen=True)
class TemporalIdentityConfig:
    keep: int = 48
    branch: int = 8
    gate: float = 120.0
    max_candidates: int = 24
    default_size: float = 24.0
    merge_min_size: float = 48.0
    merge_size_ratio: float = 1.35
    velocity_alpha: float = 0.55
    continuity_weight: float = 1.0
    accel_weight: float = 0.35
    score_weight: float = 4.0
    track_hint_weight: float = 0.05
    track_hint_cap: float = 90.0
    background_penalty_weight: float = 35.0
    target_support_weight: float = 45.0
    track_signal_radius: float = 90.0
    background_run_weight: float = 18.0
    background_run_grace: int = 2
    merge_center_penalty: float = 35.0
    hold_cost: float = 4.0
    prediction_hold_cost: float = 80.0
    prediction_hold_box_scale: float = 1.20
    prediction_hold_distance_gate: float = 28.0
    prediction_hold_distance_weight: float = 0.35
    prediction_hold_score_weight: float = 0.10
    prediction_hold_track_gate: float = 40.0
    missing_cost: float = 12.0


@dataclass(frozen=True)
class TemporalIdentityResult:
    path: dict[int, Point]
    states: dict[int, IdentityState]
    candidate_indices: dict[int, int | None]
    cost: float
    background_id: int | None = None
    background_run: int = 0


@dataclass(frozen=True)
class _State:
    point: Point
    candidate_index: int | None
    local_cost: float
    state: IdentityState
    background_id: int | None = None


@dataclass(frozen=True)
class _Hypothesis:
    cost: float
    last: Point
    vx: float
    vy: float
    path: dict[int, Point]
    states: dict[int, IdentityState]
    candidate_indices: dict[int, int | None]
    background_id: int | None = None
    background_run: int = 0


def frames_from_jsonl_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    default_size: float = 24.0,
    anchor_source: str = "track",
    expected_background_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
) -> tuple[list[TemporalFrame], Point | None]:
    frames: list[TemporalFrame] = []
    anchor: Point | None = None
    previous_candidates: tuple[Candidate, ...] = ()
    expected_background_by_frame = expected_background_by_frame or {}
    for frame_index, row in enumerate(rows):
        track_hint = _point(row.get(anchor_source))
        if anchor is None:
            anchor = track_hint
        candidates = tuple(
            candidate
            for value in row.get("cands", [])
            for candidate in [_candidate(value, default_size=default_size)]
            if candidate is not None
        )
        frames.append(
            TemporalFrame(
                int(frame_index),
                candidates,
                track_hint,
                _background_penalties(candidates, track_hint),
                _combine_supports(
                    _target_supports(candidates, track_hint, radius=float(default_size) * 4.0),
                    _motion_outlier_supports(candidates, previous_candidates),
                ),
                _background_ids(candidates, expected_background_by_frame.get(int(frame_index), ())),
            )
        )
        previous_candidates = candidates
    return frames, anchor


def temporal_identity_path_from_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    config: TemporalIdentityConfig | None = None,
    default_size: float = 24.0,
    expected_background_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
) -> dict[int, Point]:
    frames, anchor = frames_from_jsonl_rows(
        rows,
        default_size=default_size,
        expected_background_by_frame=expected_background_by_frame,
    )
    result = select_temporal_identity(frames, anchor=anchor, config=config)
    return dict(result.path)


def select_temporal_identity(
    frames: Sequence[TemporalFrame],
    *,
    anchor: Point | None = None,
    config: TemporalIdentityConfig | None = None,
) -> TemporalIdentityResult:
    cfg = config or TemporalIdentityConfig()
    ordered = sorted(frames, key=lambda frame: int(frame.frame_index))
    if not ordered:
        return TemporalIdentityResult({}, {}, {}, 0.0)

    start = _initial_point(ordered, anchor)
    hypotheses = [_Hypothesis(0.0, start, 0.0, 0.0, {}, {}, {}, None, 0)]

    for frame in ordered:
        candidates = _ranked_candidates(frame.candidates, cfg)
        expanded: list[_Hypothesis] = []
        for hypothesis in hypotheses:
            predicted = (
                float(hypothesis.last[0]) + float(hypothesis.vx),
                float(hypothesis.last[1]) + float(hypothesis.vy),
            )
            states = _states_for_frame(
                candidates,
                predicted,
                frame.track_hint,
                frame.background_penalties,
                frame.target_supports,
                frame.background_ids,
                cfg,
            )
            for state in _best_states_for_hypothesis(states, predicted, cfg):
                expanded.append(_advance(hypothesis, frame.frame_index, state, cfg))
        hypotheses = sorted(expanded, key=lambda item: item.cost)[: max(1, int(cfg.keep))]

    best = min(hypotheses, key=lambda item: item.cost)
    return TemporalIdentityResult(
        path=dict(best.path),
        states=dict(best.states),
        candidate_indices=dict(best.candidate_indices),
        cost=float(best.cost),
        background_id=best.background_id,
        background_run=best.background_run,
    )


def _point(value: object) -> Point | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _candidate(value: object, *, default_size: float) -> Candidate | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        return None
    try:
        cx = float(value[0])
        cy = float(value[1])
        score = float(value[2]) if len(value) >= 3 else 0.0
        width = float(value[3]) if len(value) >= 4 else float(default_size)
        height = float(value[4]) if len(value) >= 5 else float(default_size)
    except (TypeError, ValueError):
        return None
    return (cx, cy, score, width, height)


def _initial_point(frames: Sequence[TemporalFrame], anchor: Point | None) -> Point:
    if anchor is not None:
        return (float(anchor[0]), float(anchor[1]))
    for frame in frames:
        if frame.candidates:
            best = max(frame.candidates, key=lambda candidate: float(candidate[2]))
            return (float(best[0]), float(best[1]))
    return (0.0, 0.0)


def _ranked_candidates(candidates: Sequence[Candidate], cfg: TemporalIdentityConfig) -> list[Candidate]:
    return list(candidates)[: max(1, int(cfg.max_candidates))]


def _states_for_frame(
    candidates: Sequence[Candidate],
    predicted: Point,
    track_hint: Point | None,
    background_penalties: Sequence[float],
    target_supports: Sequence[float],
    background_ids: Sequence[int | None],
    cfg: TemporalIdentityConfig,
) -> list[_State]:
    if not candidates:
        return [
            _State(
                predicted,
                None,
                float(cfg.missing_cost) + _track_hint_cost(predicted, track_hint, cfg),
                "MERGED_HOLD",
                None,
            )
        ]

    median_size = _median([max(candidate[3], candidate[4]) for candidate in candidates])
    states: list[_State] = []
    for index, candidate in enumerate(candidates):
        center = (float(candidate[0]), float(candidate[1]))
        merge_like = _is_merge_like(candidate, median_size, cfg)
        center_cost = -float(candidate[2]) * float(cfg.score_weight)
        center_cost += _track_hint_cost(center, track_hint, cfg)
        center_cost += _candidate_signal_cost(index, background_penalties, target_supports, cfg)
        if merge_like:
            center_cost += float(cfg.merge_center_penalty)
        bg_id = background_ids[index] if index < len(background_ids) else None
        states.append(_State(center, index, center_cost, "TRACK_CONFIDENT", bg_id))

        if merge_like and _inside_box(predicted, candidate, scale=1.05):
            states.append(
                _State(
                    _clamp_point_to_candidate_box(predicted, candidate),
                    index,
                    float(cfg.hold_cost)
                    - float(candidate[2]) * float(cfg.score_weight) * 0.25
                    + _candidate_signal_cost(index, background_penalties, target_supports, cfg)
                    + _track_hint_cost(predicted, track_hint, cfg),
                    "MERGED_HOLD",
                    bg_id,
                )
            )
        if (
            _prediction_hold_track_allowed(predicted, track_hint, cfg)
            and _inside_box(predicted, candidate, scale=float(cfg.prediction_hold_box_scale))
        ):
            states.append(
                _State(
                    _clamp_point_to_candidate_box(predicted, candidate),
                    index,
                    _prediction_hold_cost(
                        index,
                        candidate,
                        predicted,
                        track_hint,
                        background_penalties,
                        target_supports,
                        cfg,
                    ),
                    "RELEASE_PENDING",
                    bg_id,
                )
            )
    nearest = _nearest_candidate(predicted, candidates)
    if nearest is not None:
        nearest_index, nearest_candidate, nearest_distance = nearest
        if (
            _prediction_hold_track_allowed(predicted, track_hint, cfg)
            and nearest_distance <= float(cfg.prediction_hold_distance_gate)
        ):
            bg_id = background_ids[nearest_index] if nearest_index < len(background_ids) else None
            states.append(
                _State(
                    predicted,
                    nearest_index,
                    _prediction_hold_cost(
                        nearest_index,
                        nearest_candidate,
                        predicted,
                        track_hint,
                        background_penalties,
                        target_supports,
                        cfg,
                    )
                    + nearest_distance * float(cfg.prediction_hold_distance_weight),
                    "RELEASE_PENDING",
                    bg_id,
                )
            )
    return states


def _best_states_for_hypothesis(
    states: Sequence[_State],
    predicted: Point,
    cfg: TemporalIdentityConfig,
) -> list[_State]:
    gated = [state for state in states if _dist(state.point, predicted) <= float(cfg.gate)]
    pool = gated if gated else list(states)
    return sorted(
        pool,
        key=lambda state: state.local_cost + _dist(state.point, predicted) * float(cfg.continuity_weight),
    )[: max(1, int(cfg.branch))]


def _advance(
    hypothesis: _Hypothesis,
    frame_index: int,
    state: _State,
    cfg: TemporalIdentityConfig,
) -> _Hypothesis:
    dx = float(state.point[0]) - float(hypothesis.last[0])
    dy = float(state.point[1]) - float(hypothesis.last[1])
    predicted = (
        float(hypothesis.last[0]) + float(hypothesis.vx),
        float(hypothesis.last[1]) + float(hypothesis.vy),
    )
    accel = math.hypot(dx - float(hypothesis.vx), dy - float(hypothesis.vy))
    step_cost = (
        float(state.local_cost)
        + _dist(state.point, predicted) * float(cfg.continuity_weight)
        + accel * float(cfg.accel_weight)
    )
    background_id = state.background_id
    background_run = _next_background_run(hypothesis, background_id)
    step_cost += _background_run_cost(background_id, background_run, cfg)
    if state.state == "TRACK_CONFIDENT" and _was_holding(hypothesis.states):
        state_name = "REACQUIRE_CANDIDATE"
    else:
        state_name = state.state

    if not hypothesis.path:
        vx, vy = dx, dy
    else:
        vx = float(cfg.velocity_alpha) * float(hypothesis.vx) + (1.0 - float(cfg.velocity_alpha)) * dx
        vy = float(cfg.velocity_alpha) * float(hypothesis.vy) + (1.0 - float(cfg.velocity_alpha)) * dy

    path = dict(hypothesis.path)
    states = dict(hypothesis.states)
    candidate_indices = dict(hypothesis.candidate_indices)
    path[int(frame_index)] = (float(state.point[0]), float(state.point[1]))
    states[int(frame_index)] = state_name
    candidate_indices[int(frame_index)] = state.candidate_index
    return _Hypothesis(
        cost=float(hypothesis.cost) + step_cost,
        last=state.point,
        vx=vx,
        vy=vy,
        path=path,
        states=states,
        candidate_indices=candidate_indices,
        background_id=background_id,
        background_run=background_run,
    )


def _was_holding(states: Mapping[int, IdentityState]) -> bool:
    if not states:
        return False
    latest_frame = max(states)
    return states[latest_frame] in {"MERGED_HOLD", "RELEASE_PENDING"}


def _prediction_hold_cost(
    index: int,
    candidate: Candidate,
    predicted: Point,
    track_hint: Point | None,
    background_penalties: Sequence[float],
    target_supports: Sequence[float],
    cfg: TemporalIdentityConfig,
) -> float:
    center = (float(candidate[0]), float(candidate[1]))
    score_relief = (
        float(candidate[2])
        * float(cfg.score_weight)
        * float(cfg.prediction_hold_score_weight)
    )
    return (
        float(cfg.prediction_hold_cost)
        + _dist(center, predicted) * float(cfg.prediction_hold_distance_weight)
        - score_relief
        + _candidate_signal_cost(index, background_penalties, target_supports, cfg) * 0.5
        + _track_hint_cost(predicted, track_hint, cfg)
    )


def _prediction_hold_track_allowed(
    predicted: Point,
    track_hint: Point | None,
    cfg: TemporalIdentityConfig,
) -> bool:
    if track_hint is None:
        return True
    gate = float(cfg.prediction_hold_track_gate)
    if gate <= 0.0:
        return True
    return _dist(predicted, track_hint) <= gate


def _next_background_run(hypothesis: _Hypothesis, background_id: int | None) -> int:
    if background_id is None:
        return 0
    if hypothesis.background_id == background_id:
        return int(hypothesis.background_run) + 1
    return 1


def _nearest_candidate(
    point: Point,
    candidates: Sequence[Candidate],
) -> tuple[int, Candidate, float] | None:
    if not candidates:
        return None
    index, candidate = min(
        enumerate(candidates),
        key=lambda item: _dist(point, (item[1][0], item[1][1])),
    )
    return (
        int(index),
        candidate,
        _dist(point, (candidate[0], candidate[1])),
    )


def _background_run_cost(
    background_id: int | None,
    background_run: int,
    cfg: TemporalIdentityConfig,
) -> float:
    if background_id is None:
        return 0.0
    over = max(0, int(background_run) - int(cfg.background_run_grace))
    return float(over) * float(cfg.background_run_weight)


def _is_merge_like(
    candidate: Candidate,
    median_size: float,
    cfg: TemporalIdentityConfig,
) -> bool:
    size = max(float(candidate[3]), float(candidate[4]))
    return (
        size >= float(cfg.merge_min_size)
        or (
            median_size > 0.0
            and size >= median_size * float(cfg.merge_size_ratio)
            and size > float(cfg.default_size)
        )
    )


def _track_hint_cost(
    point: Point,
    track_hint: Point | None,
    cfg: TemporalIdentityConfig,
) -> float:
    if track_hint is None or float(cfg.track_hint_weight) <= 0.0:
        return 0.0
    return min(_dist(point, track_hint), float(cfg.track_hint_cap)) * float(cfg.track_hint_weight)


def _candidate_signal_cost(
    index: int,
    background_penalties: Sequence[float],
    target_supports: Sequence[float],
    cfg: TemporalIdentityConfig,
) -> float:
    background = float(background_penalties[index]) if index < len(background_penalties) else 0.0
    support = float(target_supports[index]) if index < len(target_supports) else 0.0
    return (
        background * float(cfg.background_penalty_weight)
        - support * float(cfg.target_support_weight)
    )


def _background_penalties(
    candidates: Sequence[Candidate],
    track_hint: Point | None,
) -> tuple[float, ...]:
    if track_hint is None or not candidates:
        return tuple(0.0 for _candidate in candidates)
    distances = [_dist((candidate[0], candidate[1]), track_hint) for candidate in candidates]
    best_distance = min(distances)
    return tuple(
        1.0 if distance <= 1.0 and best_distance <= 1.0 and float(candidate[2]) < 0.6 else 0.0
        for candidate, distance in zip(candidates, distances)
    )


def _background_ids(
    candidates: Sequence[Candidate],
    expected_background: Sequence[tuple[int, Sequence[float]]],
    *,
    pos_tol: float = 18.0,
) -> tuple[int | None, ...]:
    return tuple(
        _match_background_id((candidate[0], candidate[1]), expected_background, pos_tol=pos_tol)
        for candidate in candidates
    )


def _match_background_id(
    point: Point,
    expected_background: Sequence[tuple[int, Sequence[float]]],
    *,
    pos_tol: float,
) -> int | None:
    best: tuple[float, int] | None = None
    for bg_id, expected in expected_background:
        expected_point = _point(expected)
        if expected_point is None:
            continue
        distance = _dist(point, expected_point)
        if distance > float(pos_tol):
            continue
        item = (distance, int(bg_id))
        if best is None or item < best:
            best = item
    return best[1] if best is not None else None


def _target_supports(
    candidates: Sequence[Candidate],
    track_hint: Point | None,
    *,
    radius: float,
) -> tuple[float, ...]:
    if track_hint is None or not candidates:
        return tuple(0.0 for _candidate in candidates)
    nearby = [
        (float(candidate[2]), index)
        for index, candidate in enumerate(candidates)
        if _dist((candidate[0], candidate[1]), track_hint) <= float(radius)
    ]
    if not nearby:
        return tuple(0.0 for _candidate in candidates)
    scores = [score for score, _index in nearby]
    min_score = min(scores)
    max_score = max(scores)
    scale = max(max_score - min_score, 1e-6)
    support = [0.0 for _candidate in candidates]
    for score, index in nearby:
        support[index] = (score - min_score) / scale
    return tuple(support)


def _motion_outlier_supports(
    candidates: Sequence[Candidate],
    previous_candidates: Sequence[Candidate],
) -> tuple[float, ...]:
    if not candidates or not previous_candidates:
        return tuple(0.0 for _candidate in candidates)

    displacements = []
    for candidate in candidates:
        previous = min(
            previous_candidates,
            key=lambda item: _dist((item[0], item[1]), (candidate[0], candidate[1])),
        )
        displacements.append((
            float(candidate[0]) - float(previous[0]),
            float(candidate[1]) - float(previous[1]),
        ))
    median_dx = _median([dx for dx, _dy in displacements])
    median_dy = _median([dy for _dx, dy in displacements])
    magnitudes = [
        math.hypot(float(dx) - median_dx, float(dy) - median_dy)
        for dx, dy in displacements
    ]
    max_magnitude = max(magnitudes) if magnitudes else 0.0
    if max_magnitude <= 1e-6:
        return tuple(0.0 for _candidate in candidates)
    return tuple(float(value) / max_magnitude for value in magnitudes)


def _combine_supports(*items: Sequence[float]) -> tuple[float, ...]:
    size = max((len(item) for item in items), default=0)
    out = []
    for index in range(size):
        out.append(max(float(item[index]) if index < len(item) else 0.0 for item in items))
    return tuple(out)


def _inside_box(point: Point, candidate: Candidate, *, scale: float = 1.0) -> bool:
    cx, cy, _score, width, height = candidate
    return (
        abs(float(point[0]) - float(cx)) <= float(width) * float(scale) / 2.0
        and abs(float(point[1]) - float(cy)) <= float(height) * float(scale) / 2.0
    )


def _clamp_point_to_candidate_box(point: Point, candidate: Candidate) -> Point:
    cx, cy, _score, width, height = candidate
    half_w = float(width) / 2.0
    half_h = float(height) / 2.0
    return (
        min(max(float(point[0]), float(cx) - half_w), float(cx) + half_w),
        min(max(float(point[1]), float(cy) - half_h), float(cy) + half_h),
    )


def _median(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
