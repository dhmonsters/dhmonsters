# 투명도형 후보 박스 내부점을 다중가설로 추적하는 solver입니다.
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Sequence, Tuple


Point = Tuple[float, float]


@dataclass(frozen=True)
class MhtCandidate:
    cx: float
    cy: float
    score: float
    w: float = float("nan")
    h: float = float("nan")
    bg_center: Optional[Point] = None
    motion_score: float = 0.0
    viol_score: float = 0.0
    bg_score: float = 0.0


@dataclass(frozen=True)
class MhtFrame:
    frame_index: int
    candidates: Sequence[MhtCandidate]
    anchor: Optional[Point] = None


@dataclass(frozen=True)
class SolverConfig:
    keep: int = 64
    branch: int = 8
    gate: float = 140.0
    grid_size: int = 5
    shrink: float = 0.76
    velocity_alpha: float = 0.55
    continuity_weight: float = 1.0
    accel_weight: float = 0.3
    center_weight: float = 2.0
    merge_bg_far_bonus: float = 0.18
    bg_penalty: float = 28.0
    motion_weight: float = 0.9
    viol_weight: float = 0.7
    bg_weight: float = 0.8
    score_weight: float = 0.15


@dataclass(frozen=True)
class _State:
    point: Point
    cand_idx: int
    offset_x: float
    offset_y: float
    local_cost: float
    score: float


@dataclass(frozen=True)
class _Hypothesis:
    cost: float
    last: Point
    vx: float
    vy: float
    path: Dict[int, Point]


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _finite_box(candidate: MhtCandidate) -> bool:
    return (
        math.isfinite(float(candidate.w))
        and math.isfinite(float(candidate.h))
        and float(candidate.w) > 0.0
        and float(candidate.h) > 0.0
    )


def _inside_box(point: Point, candidate: MhtCandidate, scale: float = 1.0) -> bool:
    if not _finite_box(candidate):
        return False
    return (
        abs(float(point[0]) - float(candidate.cx)) <= float(candidate.w) * scale / 2.0
        and abs(float(point[1]) - float(candidate.cy)) <= float(candidate.h) * scale / 2.0
    )


def _candidate_points(
    candidate: MhtCandidate,
    grid_size: int,
    shrink: float,
) -> List[Tuple[Point, float, float]]:
    cx, cy = float(candidate.cx), float(candidate.cy)
    if not _finite_box(candidate) or grid_size <= 1:
        return [((cx, cy), 0.0, 0.0)]

    half_w = float(candidate.w) * float(shrink) / 2.0
    half_h = float(candidate.h) * float(shrink) / 2.0
    if grid_size == 1:
        xs = [cx]
        ys = [cy]
    else:
        xs = [cx - half_w + (2.0 * half_w * i / float(grid_size - 1)) for i in range(grid_size)]
        ys = [cy - half_h + (2.0 * half_h * i / float(grid_size - 1)) for i in range(grid_size)]

    points = []
    for x in xs:
        for y in ys:
            ox = 0.0 if half_w <= 0.0 else (float(x) - cx) / half_w
            oy = 0.0 if half_h <= 0.0 else (float(y) - cy) / half_h
            points.append(((float(x), float(y)), float(ox), float(oy)))
    return points


def _states_for_hypothesis(
    candidates: Sequence[MhtCandidate],
    pred: Point,
    config: SolverConfig,
) -> List[_State]:
    states: List[_State] = []
    direct_near = any(
        cand.bg_center is None and _dist((float(cand.cx), float(cand.cy)), pred) <= 35.0
        for cand in candidates
    )
    for cand_idx, candidate in enumerate(candidates):
        pred_inside = _inside_box(pred, candidate, scale=1.08)
        bg_like = candidate.bg_center is not None
        allow_merge_grid = bg_like and pred_inside and not direct_near
        signal_cost = (
            -float(config.motion_weight) * float(candidate.motion_score)
            - float(config.viol_weight) * float(candidate.viol_score)
            - float(config.bg_weight) * float(candidate.bg_score)
            - float(config.score_weight) * float(candidate.score)
        )
        if allow_merge_grid:
            local = signal_cost
            local -= min(_dist(pred, candidate.bg_center), 90.0) * float(config.merge_bg_far_bonus)
            states.append(
                _State(
                    point=pred,
                    cand_idx=cand_idx,
                    offset_x=0.0,
                    offset_y=0.0,
                    local_cost=local,
                    score=float(candidate.score),
                )
            )
        grid_size = config.grid_size if allow_merge_grid else 1
        for point, offset_x, offset_y in _candidate_points(
            candidate,
            grid_size,
            config.shrink,
        ):
            local = (abs(offset_x) + abs(offset_y)) * float(config.center_weight)
            if allow_merge_grid:
                local -= min(_dist(point, candidate.bg_center), 90.0) * float(config.merge_bg_far_bonus)
            elif bg_like and not pred_inside:
                local += float(config.bg_penalty)
            local += signal_cost
            states.append(
                _State(
                    point=point,
                    cand_idx=cand_idx,
                    offset_x=offset_x,
                    offset_y=offset_y,
                    local_cost=local,
                    score=float(candidate.score),
                )
            )
    return states


def _initial_hypothesis(frame: MhtFrame) -> _Hypothesis:
    if frame.anchor is not None:
        point = (float(frame.anchor[0]), float(frame.anchor[1]))
    elif frame.candidates:
        best = max(frame.candidates, key=lambda cand: float(cand.score))
        point = (float(best.cx), float(best.cy))
    else:
        point = (0.0, 0.0)
    return _Hypothesis(0.0, point, 0.0, 0.0, {int(frame.frame_index): point})


def solve_mht(
    frames: Sequence[MhtFrame],
    *,
    keep: Optional[int] = None,
    branch: Optional[int] = None,
    gate: Optional[float] = None,
    grid_size: Optional[int] = None,
    shrink: Optional[float] = None,
    config: Optional[SolverConfig] = None,
) -> Dict[int, Point]:
    cfg = config or SolverConfig()
    if keep is not None:
        cfg = SolverConfig(**{**cfg.__dict__, "keep": int(keep)})
    if branch is not None:
        cfg = SolverConfig(**{**cfg.__dict__, "branch": int(branch)})
    if gate is not None:
        cfg = SolverConfig(**{**cfg.__dict__, "gate": float(gate)})
    if grid_size is not None:
        cfg = SolverConfig(**{**cfg.__dict__, "grid_size": int(grid_size)})
    if shrink is not None:
        cfg = SolverConfig(**{**cfg.__dict__, "shrink": float(shrink)})

    ordered = sorted(frames, key=lambda item: int(item.frame_index))
    hyps: List[_Hypothesis] = []
    for frame in ordered:
        frame_i = int(frame.frame_index)
        if frame.anchor is not None:
            anchor = (float(frame.anchor[0]), float(frame.anchor[1]))
            hyps = [_Hypothesis(0.0, anchor, 0.0, 0.0, {frame_i: anchor})]
            continue

        if not hyps:
            hyps = [_initial_hypothesis(frame)]
            continue

        if not frame.candidates:
            coasted = []
            for hyp in hyps:
                pred = (hyp.last[0] + hyp.vx, hyp.last[1] + hyp.vy)
                path = dict(hyp.path)
                path[frame_i] = pred
                coasted.append(_Hypothesis(hyp.cost + 10.0, pred, hyp.vx * 0.9, hyp.vy * 0.9, path))
            hyps = sorted(coasted, key=lambda hyp: hyp.cost)[: max(1, cfg.keep)]
            continue

        expanded: List[_Hypothesis] = []
        for hyp in hyps:
            pred = (hyp.last[0] + hyp.vx, hyp.last[1] + hyp.vy)
            states = _states_for_hypothesis(frame.candidates, pred, cfg)
            gated = [state for state in states if _dist(state.point, pred) <= float(cfg.gate)]
            if not gated:
                gated = states
            scored = []
            for state in gated:
                dx = state.point[0] - hyp.last[0]
                dy = state.point[1] - hyp.last[1]
                accel = math.hypot(dx - hyp.vx, dy - hyp.vy)
                cost = (
                    hyp.cost
                    + state.local_cost
                    + _dist(state.point, pred) * float(cfg.continuity_weight)
                    + accel * float(cfg.accel_weight)
                )
                scored.append((cost, state, dx, dy))
            scored.sort(key=lambda item: item[0])
            for cost, state, dx, dy in scored[: max(1, cfg.branch)]:
                if len(hyp.path) <= 1:
                    vx, vy = dx, dy
                else:
                    vx = float(cfg.velocity_alpha) * hyp.vx + (1.0 - float(cfg.velocity_alpha)) * dx
                    vy = float(cfg.velocity_alpha) * hyp.vy + (1.0 - float(cfg.velocity_alpha)) * dy
                path = dict(hyp.path)
                path[frame_i] = state.point
                expanded.append(_Hypothesis(cost, state.point, vx, vy, path))
        hyps = sorted(expanded, key=lambda hyp: hyp.cost)[: max(1, cfg.keep)]

    if not hyps:
        return {}
    return min(hyps, key=lambda hyp: hyp.cost).path
