# 투명 퍼즐 live 루프에서 selector용 family 경로 후보를 생성합니다.
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from typing import Mapping, Sequence, Tuple

import numpy as np

from core.vision.transparent_mht_solver import (
    MhtCandidate,
    MhtFrame,
    SolverConfig,
    solve_mht,
)


Point = Tuple[float, float]
Candidate = Tuple[float, float, float, float, float]


@dataclass(frozen=True)
class LiveFamilyDecision:
    points: Mapping[str, Point]
    debug: Mapping[str, object]


@dataclass(frozen=True)
class _Node:
    x: float
    y: float
    score: float


@dataclass(frozen=True)
class _FamilyConfig:
    name: str
    transition_scale: float
    max_jump: float
    det_weight: float
    motion_weight: float
    start_scale: float


class TransparentLiveFamilyPool:
    def __init__(
        self,
        *,
        window: int = 24,
        min_frames: int = 8,
        merge_min_size: float = 48.0,
        merge_size_ratio: float = 1.18,
        catalog_min_lag: int = 20,
        catalog_max_lag: int = 80,
        catalog_history: int = 160,
        phase_mht_window: int = 28,
        enable_phase_mht: bool = False,
        raw_rank_families: int = 4,
        raw_continuity_families: int = 8,
        raw_max_candidates_per_frame: int = 24,
        raw_max_step_px: float = 85.0,
    ):
        self.window = max(2, int(window))
        self.min_frames = max(2, int(min_frames))
        self.merge_min_size = float(merge_min_size)
        self.merge_size_ratio = float(merge_size_ratio)
        self.catalog_min_lag = max(2, int(catalog_min_lag))
        self.catalog_max_lag = max(self.catalog_min_lag, int(catalog_max_lag))
        self.catalog_history = max(self.catalog_max_lag + 2, int(catalog_history))
        self.phase_mht_window = max(3, int(phase_mht_window))
        self.enable_phase_mht = bool(enable_phase_mht)
        self.raw_rank_families = max(0, int(raw_rank_families))
        self.raw_continuity_families = max(0, int(raw_continuity_families))
        self.raw_max_candidates_per_frame = max(1, int(raw_max_candidates_per_frame))
        self.raw_max_step_px = float(raw_max_step_px)
        self._phase_family_name = "phase_catalog_live_center_mild_state_mild"
        self._phase_mht_family_name = "phase_catalog_mht_center_mild_state_mild"
        self._mht_family_name = "bg_split_viterbi_center_mild_state_mild"
        self._mht_config = SolverConfig(
            keep=64,
            branch=8,
            gate=140.0,
            grid_size=5,
            shrink=0.76,
        )
        self._phase_mht_config = SolverConfig(
            keep=48,
            branch=6,
            gate=140.0,
            grid_size=3,
            shrink=0.76,
            score_weight=0.05,
            bg_penalty=36.0,
        )
        self._configs = (
            _FamilyConfig(
                "balanced_viterbi_center_mild_state_mild",
                transition_scale=28.0,
                max_jump=170.0,
                det_weight=0.2,
                motion_weight=1.4,
                start_scale=35.0,
            ),
            _FamilyConfig(
                "strict_transition_viterbi_center_mild_state_mild",
                transition_scale=18.0,
                max_jump=120.0,
                det_weight=0.0,
                motion_weight=0.0,
                start_scale=35.0,
            ),
        )
        self.reset()

    def reset(self) -> None:
        self._frames: deque[int] = deque()
        self._candidate_sets: dict[int, list[Candidate]] = {}
        self._catalog_frames: deque[int] = deque()
        self._catalog_candidate_sets: dict[int, list[Candidate]] = {}
        self._catalog_period: int | None = None
        self._phase_last: Point | None = None
        self._phase_velocity: Point = (0.0, 0.0)
        self._start_point: Point | None = None
        self._raw_last_points: dict[str, Point] = {}
        self._raw_offset_histories: dict[str, list[Point]] = {}

    def update(
        self,
        frame_index: int,
        *,
        candidates: Sequence[Sequence[float]],
        gray_frame: object | None = None,
        white_anchor: Point | None = None,
    ) -> LiveFamilyDecision:
        del gray_frame
        frame = int(frame_index)
        if white_anchor is not None:
            self._start_point = (float(white_anchor[0]), float(white_anchor[1]))
            self._phase_last = self._start_point
            self._phase_velocity = (0.0, 0.0)

        normalized = self._normalize_candidates(candidates)
        if frame not in self._candidate_sets:
            self._frames.append(frame)
        self._candidate_sets[frame] = normalized
        if frame not in self._catalog_candidate_sets:
            self._catalog_frames.append(frame)
        self._catalog_candidate_sets[frame] = self._catalog_candidates(
            normalized,
            white_anchor,
        )
        self._prune()
        self._prune_catalog()
        raw_points = self._raw_candidate_family_points(frame, normalized)

        usable_frames = [
            idx for idx in self._frames
            if self._candidate_sets.get(idx)
        ]
        if self._start_point is None or len(usable_frames) < self.min_frames:
            return LiveFamilyDecision({}, {
                "frames": len(usable_frames),
                "ready": False,
            })

        points = {}
        points.update(raw_points)
        for config in self._configs:
            path = self._viterbi_path(usable_frames, config)
            if path:
                points[config.name] = path[-1]
                points.update(self._coast_variants(config.name, usable_frames, path))
        mht_path = self._hidden_mht_path(usable_frames)
        latest_frame = usable_frames[-1]
        if latest_frame in mht_path:
            point = mht_path[latest_frame]
            points[self._mht_family_name] = point
            points["merge_context_center_mild_state_mild"] = point
            ordered_mht = [
                mht_path[frame]
                for frame in usable_frames
                if frame in mht_path
            ]
            ordered_frames = [
                frame
                for frame in usable_frames
                if frame in mht_path
            ]
            if len(ordered_mht) >= 3:
                points.update(self._coast_variants(
                    self._mht_family_name,
                    ordered_frames,
                    ordered_mht,
                ))
                points.update(self._coast_variants(
                    "merge_context_center_mild_state_mild",
                    ordered_frames,
                    ordered_mht,
                ))
        phase_point = self._phase_catalog_live_point(frame)
        if phase_point is not None:
            points[self._phase_family_name] = phase_point
        if self.enable_phase_mht:
            phase_mht_path = self._phase_catalog_mht_path(frame)
            if frame in phase_mht_path:
                points[self._phase_mht_family_name] = phase_mht_path[frame]
        return LiveFamilyDecision(points, {
            "frames": len(usable_frames),
            "ready": bool(points),
            "families": sorted(points),
        })

    def _raw_candidate_family_points(
        self,
        frame: int,
        candidates: Sequence[Candidate],
    ) -> dict[str, Point]:
        ranked = sorted(
            list(candidates),
            key=lambda candidate: float(candidate[2]),
            reverse=True,
        )[: self.raw_max_candidates_per_frame]
        if not ranked:
            return {}

        points = [
            (float(candidate[0]), float(candidate[1]))
            for candidate in ranked
        ]
        out: dict[str, Point] = {}
        for rank, point in enumerate(points[: self.raw_rank_families]):
            out[f"raw_candidate_rank{rank}_center_mild_state_mild"] = point

        if not self._raw_last_points:
            for index, candidate in enumerate(ranked[: self.raw_continuity_families]):
                point = (float(candidate[0]), float(candidate[1]))
                family = f"raw_candidate_cont{index}_center_mild_state_mild"
                self._raw_last_points[family] = point
                out[family] = point
                offset_family = self._raw_box_offset_family_name(family)
                self._raw_offset_histories[offset_family] = [point]
                out[offset_family] = point
            return out

        used: set[int] = set()
        next_last = dict(self._raw_last_points)
        next_histories = {
            family: list(history[-2:])
            for family, history in self._raw_offset_histories.items()
        }
        for family in sorted(self._raw_last_points):
            previous = self._raw_last_points[family]
            best_index = None
            best_error = float("inf")
            for index, point in enumerate(points):
                if index in used:
                    continue
                error = math.hypot(point[0] - previous[0], point[1] - previous[1])
                if error < best_error:
                    best_index = index
                    best_error = error
            if best_index is None or best_error > self.raw_max_step_px:
                continue
            used.add(best_index)
            point = points[best_index]
            candidate = ranked[best_index]
            next_last[family] = point
            out[family] = point
            offset_family = self._raw_box_offset_family_name(family)
            offset_point = self._raw_box_offset_point(
                int(frame),
                candidate,
                point,
                next_histories.get(offset_family, []),
            )
            history = (next_histories.get(offset_family, []) + [offset_point])[-2:]
            next_histories[offset_family] = history
            out[offset_family] = offset_point

        if len(next_last) < self.raw_continuity_families:
            for candidate in ranked:
                point = (float(candidate[0]), float(candidate[1]))
                if any(math.hypot(point[0] - existing[0], point[1] - existing[1]) <= 1e-6 for existing in next_last.values()):
                    continue
                family = f"raw_candidate_cont{len(next_last)}_center_mild_state_mild"
                next_last[family] = point
                out[family] = point
                offset_family = self._raw_box_offset_family_name(family)
                next_histories[offset_family] = [point]
                out[offset_family] = point
                if len(next_last) >= self.raw_continuity_families:
                    break

        self._raw_last_points = next_last
        self._raw_offset_histories = next_histories
        return out

    @staticmethod
    def _raw_box_offset_family_name(family: str) -> str:
        return str(family).replace(
            "_center_mild_state_mild",
            "_box_offset_state_mild",
        )

    def _raw_box_offset_point(
        self,
        frame: int,
        candidate: Candidate,
        point: Point,
        history: Sequence[Point],
    ) -> Point:
        if not self._is_merge_like_candidate(int(frame), candidate):
            return (float(point[0]), float(point[1]))
        prediction = self._raw_offset_prediction(history, point)
        return self._clamp_point_to_candidate_box(candidate, prediction)

    @staticmethod
    def _raw_offset_prediction(history: Sequence[Point], fallback: Point) -> Point:
        if len(history) < 2:
            return (float(fallback[0]), float(fallback[1]))
        prev = history[-1]
        before = history[-2]
        return (
            float(prev[0]) + (float(prev[0]) - float(before[0])),
            float(prev[1]) + (float(prev[1]) - float(before[1])),
        )

    @staticmethod
    def _clamp_point_to_candidate_box(candidate: Candidate, point: Point) -> Point:
        cx, cy, _score, width, height = candidate
        half_w = float(width) / 2.0
        half_h = float(height) / 2.0
        return (
            min(max(float(point[0]), float(cx) - half_w), float(cx) + half_w),
            min(max(float(point[1]), float(cy) - half_h), float(cy) + half_h),
        )

    def _prune(self) -> None:
        while len(self._frames) > self.window:
            old = self._frames.popleft()
            self._candidate_sets.pop(old, None)

    def _prune_catalog(self) -> None:
        while len(self._catalog_frames) > self.catalog_history:
            old = self._catalog_frames.popleft()
            self._catalog_candidate_sets.pop(old, None)

    def _viterbi_path(
        self,
        frames: Sequence[int],
        config: _FamilyConfig,
    ) -> list[Point]:
        node_frames = [
            self._nodes_for_frame(frame, config)
            for frame in frames
        ]
        if not node_frames or any(not nodes for nodes in node_frames):
            return []

        prev_scores = {}
        back = []
        start = _Node(self._start_point[0], self._start_point[1], 0.0)
        for node in node_frames[0]:
            prev_scores[node] = node.score - self._transition_penalty(
                start,
                node,
                config.start_scale,
                config.max_jump,
            )
        back.append({node: None for node in node_frames[0]})

        for nodes in node_frames[1:]:
            cur_scores = {}
            cur_back = {}
            for node in nodes:
                best_score = None
                best_prev = None
                for prev, prev_score in prev_scores.items():
                    score = prev_score + node.score - self._transition_penalty(
                        prev,
                        node,
                        config.transition_scale,
                        config.max_jump,
                    )
                    if best_score is None or score > best_score:
                        best_score = score
                        best_prev = prev
                if best_score is not None and best_prev is not None:
                    cur_scores[node] = best_score
                    cur_back[node] = best_prev
            if not cur_scores:
                return []
            prev_scores = cur_scores
            back.append(cur_back)

        node = max(prev_scores, key=prev_scores.get)
        selected = [node]
        for idx in range(len(back) - 1, 0, -1):
            node = back[idx][node]
            selected.append(node)
        selected.reverse()
        return [(node.x, node.y) for node in selected]

    def _hidden_mht_path(self, frames: Sequence[int]) -> dict[int, Point]:
        if self._start_point is None or not frames:
            return {}

        anchor_frame = int(frames[0]) - 1
        mht_frames = [MhtFrame(anchor_frame, [], anchor=self._start_point)]
        for frame in frames:
            mht_frames.append(MhtFrame(
                int(frame),
                self._mht_candidates_for_frame(int(frame)),
            ))
        return solve_mht(mht_frames, config=self._mht_config)

    def _mht_candidates_for_frame(self, frame: int) -> list[MhtCandidate]:
        candidates = self._candidate_sets.get(int(frame), [])
        if not candidates:
            return []
        sizes = [max(float(candidate[3]), float(candidate[4])) for candidate in candidates]
        median_size = float(np.median(sizes)) if sizes else 0.0
        out = []
        for candidate in candidates:
            cx, cy, score, width, height = candidate
            size = max(float(width), float(height))
            merge_like = (
                size >= self.merge_min_size
                or (
                    median_size > 0.0
                    and size >= median_size * self.merge_size_ratio
                )
            )
            out.append(MhtCandidate(
                cx=float(cx),
                cy=float(cy),
                score=float(score),
                w=float(width),
                h=float(height),
                bg_center=(float(cx), float(cy)) if merge_like else None,
            ))
        return out

    def _phase_catalog_live_point(self, frame: int) -> Point | None:
        candidates = self._catalog_candidate_sets.get(int(frame), [])
        if not candidates or self._phase_last is None:
            return None
        if self._catalog_period is None:
            self._catalog_period = self._estimate_catalog_period(frame)
        if self._catalog_period is None:
            return None

        lag = self._choose_catalog_lag(frame, self._catalog_period)
        expected = self._catalog_candidate_sets.get(int(frame) - int(lag), [])
        pred = (
            float(self._phase_last[0]) + float(self._phase_velocity[0]),
            float(self._phase_last[1]) + float(self._phase_velocity[1]),
        )
        active = self._active_phase_candidates(candidates, expected, pred)
        picked = self._pick_phase_candidate(active, pred)
        if picked is None:
            cur = pred
            self._phase_velocity = (
                float(self._phase_velocity[0]) * 0.9,
                float(self._phase_velocity[1]) * 0.9,
            )
        else:
            cur = (float(picked[0]), float(picked[1]))
            self._phase_velocity = (
                float(self._phase_velocity[0]) * 0.6 + (cur[0] - self._phase_last[0]) * 0.4,
                float(self._phase_velocity[1]) * 0.6 + (cur[1] - self._phase_last[1]) * 0.4,
            )
        self._phase_last = cur
        return cur

    def _phase_catalog_mht_path(self, frame: int) -> dict[int, Point]:
        if self._start_point is None:
            return {}
        if self._catalog_period is None:
            self._catalog_period = self._estimate_catalog_period(frame)
        if self._catalog_period is None:
            return {}

        frames = [
            int(idx)
            for idx in self._catalog_frames
            if idx <= int(frame) and self._catalog_candidate_sets.get(int(idx))
        ]
        frames = frames[-self.phase_mht_window:]
        if len(frames) < 2:
            return {}
        anchor_frame = int(frames[0]) - 1
        mht_frames = [MhtFrame(anchor_frame, [], anchor=self._start_point)]
        for idx in frames:
            mht_frames.append(MhtFrame(
                int(idx),
                self._phase_mht_candidates_for_frame(int(idx)),
            ))
        return solve_mht(mht_frames, config=self._phase_mht_config)

    def _phase_mht_candidates_for_frame(self, frame: int) -> list[MhtCandidate]:
        candidates = self._catalog_candidate_sets.get(int(frame), [])
        if not candidates:
            return []
        if self._catalog_period is None:
            return [
                MhtCandidate(c[0], c[1], c[2], c[3], c[4])
                for c in candidates
            ]

        lag = self._choose_catalog_lag(frame, self._catalog_period)
        expected = self._catalog_candidate_sets.get(int(frame) - int(lag), [])
        active = []
        confirmed = []
        for candidate in candidates:
            if self._candidate_matches_background(candidate, expected):
                confirmed.append(candidate)
            else:
                active.append(candidate)
        source = active if active else confirmed
        out = []
        for candidate in source:
            bg_center = None
            if candidate in confirmed:
                bg_center = (float(candidate[0]), float(candidate[1]))
            out.append(MhtCandidate(
                cx=float(candidate[0]),
                cy=float(candidate[1]),
                score=float(candidate[2]),
                w=float(candidate[3]),
                h=float(candidate[4]),
                bg_center=bg_center,
            ))
        return out

    def _estimate_catalog_period(self, frame: int) -> int | None:
        hi = min(int(frame), int(self.catalog_max_lag))
        lo = min(int(self.catalog_min_lag), hi)
        best: tuple[float, int] | None = None
        for lag in range(lo, hi + 1):
            scores = []
            for cur_frame in self._catalog_frames:
                if cur_frame < lag:
                    continue
                if cur_frame > frame:
                    continue
                ref = self._catalog_candidate_sets.get(int(cur_frame) - lag, [])
                cur = self._catalog_candidate_sets.get(int(cur_frame), [])
                score = self._catalog_match_score(ref, cur)
                if score is not None:
                    scores.append(score)
            if not scores:
                continue
            scores.sort()
            item = (float(scores[len(scores) // 2]), int(lag))
            if best is None or item < best:
                best = item
        return None if best is None else int(best[1])

    def _choose_catalog_lag(self, frame: int, period: int, search: int = 8) -> int:
        lo = max(2, int(period) - int(search))
        hi = min(int(frame), int(period) + int(search))
        best: tuple[float, int] | None = None
        for lag in range(lo, hi + 1):
            ref = self._catalog_candidate_sets.get(int(frame) - int(lag), [])
            cur = self._catalog_candidate_sets.get(int(frame), [])
            score = self._catalog_match_score(ref, cur)
            if score is None:
                continue
            item = (score, int(lag))
            if best is None or item < best:
                best = item
        return int(period) if best is None else int(best[1])

    @staticmethod
    def _catalog_match_score(
        reference: Sequence[Candidate],
        current: Sequence[Candidate],
    ) -> float | None:
        if not reference or not current:
            return None
        pairs = []
        for ri, ref in enumerate(reference):
            for ci, cur in enumerate(current):
                pairs.append((math.hypot(ref[0] - cur[0], ref[1] - cur[1]), ri, ci))
        pairs.sort(key=lambda item: item[0])
        used_ref = set()
        used_cur = set()
        distances = []
        for distance, ri, ci in pairs:
            if ri in used_ref or ci in used_cur:
                continue
            used_ref.add(ri)
            used_cur.add(ci)
            distances.append(float(distance))
        if not distances:
            return None
        distances.sort()
        keep = distances[: max(1, int(math.ceil(len(distances) * 0.75)))]
        return float(keep[len(keep) // 2])

    def _active_phase_candidates(
        self,
        candidates: Sequence[Candidate],
        expected: Sequence[Candidate],
        pred: Point,
    ) -> list[Candidate]:
        if not expected:
            return list(candidates)
        active = []
        for candidate in candidates:
            if self._candidate_matches_background(candidate, expected):
                if math.hypot(candidate[0] - pred[0], candidate[1] - pred[1]) > 34.0:
                    continue
            active.append(candidate)
        return active if active else list(candidates)

    def _candidate_matches_background(
        self,
        candidate: Candidate,
        expected: Sequence[Candidate],
    ) -> bool:
        for background in expected:
            if math.hypot(candidate[0] - background[0], candidate[1] - background[1]) > 10.0:
                continue
            if not self._candidate_shape_close(candidate, background):
                continue
            return True
        return False

    @staticmethod
    def _candidate_shape_close(candidate: Candidate, expected: Candidate) -> bool:
        if not (
            math.isfinite(candidate[3])
            and math.isfinite(candidate[4])
            and math.isfinite(expected[3])
            and math.isfinite(expected[4])
            and candidate[3] > 0.0
            and candidate[4] > 0.0
            and expected[3] > 0.0
            and expected[4] > 0.0
        ):
            return True
        area_a = float(candidate[3]) * float(candidate[4])
        area_b = float(expected[3]) * float(expected[4])
        aspect_a = float(candidate[3]) / max(float(candidate[4]), 1e-6)
        aspect_b = float(expected[3]) / max(float(expected[4]), 1e-6)
        return (
            TransparentLiveFamilyPool._pct_delta(area_a, area_b) <= 6.0
            and TransparentLiveFamilyPool._pct_delta(aspect_a, aspect_b) <= 6.0
        )

    @staticmethod
    def _pct_delta(a: float, b: float) -> float:
        return abs(float(a) - float(b)) / max((abs(float(a)) + abs(float(b))) / 2.0, 1e-6) * 100.0

    @staticmethod
    def _pick_phase_candidate(candidates: Sequence[Candidate], pred: Point) -> Candidate | None:
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda candidate: (
                math.hypot(candidate[0] - pred[0], candidate[1] - pred[1])
                - 0.02 * float(candidate[2])
            ),
        )

    def _catalog_candidates(
        self,
        candidates: Sequence[Candidate],
        white_anchor: Point | None,
    ) -> list[Candidate]:
        if white_anchor is None:
            return list(candidates)
        return [
            candidate
            for candidate in candidates
            if math.hypot(candidate[0] - white_anchor[0], candidate[1] - white_anchor[1]) > 45.0
        ]

    def _coast_variants(
        self,
        family_name: str,
        frames: Sequence[int],
        path: Sequence[Point],
    ) -> dict[str, Point]:
        if len(frames) < 3 or len(path) < 3:
            return {}
        latest_frame = int(frames[-1])
        latest_point = path[-1]
        state_point = latest_point
        if self._is_state_suspect(frames, path):
            state_point = self._coast_prediction(frames, path)
        offset_point = self._clamp_to_nearest_candidate_box(
            latest_frame,
            state_point,
            max_dist=105.0,
        )
        state_name, offset_name = self._coast_family_names(family_name)
        return {
            state_name: (float(state_point[0]), float(state_point[1])),
            offset_name: (float(offset_point[0]), float(offset_point[1])),
        }

    @staticmethod
    def _coast_family_names(family_name: str) -> tuple[str, str]:
        base = str(family_name)
        for suffix in ("_state_mild", "_state_medium", "_state_aggressive"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        return (f"{base}_state_coast", f"{base}_offset_coast")

    def _is_state_suspect(
        self,
        frames: Sequence[int],
        path: Sequence[Point],
    ) -> bool:
        latest_frame = int(frames[-1])
        latest_point = path[-1]
        selected = self._nearest_candidate(latest_frame, latest_point, max_dist=120.0)
        if selected is not None and self._is_merge_like_candidate(latest_frame, selected):
            return True
        if len(path) < 3:
            return False

        a_frame, b_frame, c_frame = int(frames[-3]), int(frames[-2]), int(frames[-1])
        a_point, b_point, c_point = path[-3], path[-2], path[-1]
        dt_ab = max(1.0, float(b_frame - a_frame))
        vx = (float(b_point[0]) - float(a_point[0])) / dt_ab
        vy = (float(b_point[1]) - float(a_point[1])) / dt_ab
        dt_bc = max(1.0, float(c_frame - b_frame))
        pred = (
            float(b_point[0]) + vx * dt_bc,
            float(b_point[1]) + vy * dt_bc,
        )
        return math.hypot(float(c_point[0]) - pred[0], float(c_point[1]) - pred[1]) > 36.0

    def _coast_prediction(
        self,
        frames: Sequence[int],
        path: Sequence[Point],
    ) -> Point:
        stable = []
        for frame, point in zip(frames[:-1], path[:-1]):
            selected = self._nearest_candidate(int(frame), point, max_dist=120.0)
            if selected is not None and self._is_merge_like_candidate(int(frame), selected):
                continue
            stable.append((int(frame), point))
        if len(stable) < 2:
            return (float(path[-1][0]), float(path[-1][1]))

        a_frame, a_point = stable[-2]
        b_frame, b_point = stable[-1]
        latest_frame = int(frames[-1])
        dt = max(1.0, float(b_frame - a_frame))
        vx = (float(b_point[0]) - float(a_point[0])) / dt
        vy = (float(b_point[1]) - float(a_point[1])) / dt
        ahead = max(1.0, float(latest_frame - b_frame))
        return (
            float(b_point[0]) + vx * ahead,
            float(b_point[1]) + vy * ahead,
        )

    def _is_merge_like_candidate(self, frame: int, candidate: Candidate) -> bool:
        candidates = self._candidate_sets.get(int(frame), [])
        if not candidates:
            return False
        sizes = [max(float(item[3]), float(item[4])) for item in candidates]
        areas = [float(item[3]) * float(item[4]) for item in candidates]
        size = max(float(candidate[3]), float(candidate[4]))
        area = float(candidate[3]) * float(candidate[4])
        median_size = float(np.median(sizes)) if sizes else 0.0
        median_area = float(np.median(areas)) if areas else 0.0
        return (
            size >= self.merge_min_size
            or (
                median_size > 0.0
                and size >= median_size * self.merge_size_ratio
            )
            or (
                median_area > 0.0
                and area >= median_area * 1.18
            )
        )

    def _clamp_to_nearest_candidate_box(
        self,
        frame: int,
        point: Point,
        *,
        max_dist: float,
    ) -> Point:
        candidate = self._nearest_candidate(frame, point, max_dist=max_dist)
        if candidate is None:
            return (float(point[0]), float(point[1]))
        cx, cy, _score, width, height = candidate
        half_w = float(width) / 2.0
        half_h = float(height) / 2.0
        return (
            min(max(float(point[0]), float(cx) - half_w), float(cx) + half_w),
            min(max(float(point[1]), float(cy) - half_h), float(cy) + half_h),
        )

    def _nearest_candidate(
        self,
        frame: int,
        point: Point,
        *,
        max_dist: float,
    ) -> Candidate | None:
        candidates = self._candidate_sets.get(int(frame), [])
        if not candidates:
            return None
        best = min(
            candidates,
            key=lambda candidate: math.hypot(
                float(candidate[0]) - float(point[0]),
                float(candidate[1]) - float(point[1]),
            ),
        )
        dist = math.hypot(float(best[0]) - float(point[0]), float(best[1]) - float(point[1]))
        if dist > float(max_dist):
            return None
        return best

    def _nodes_for_frame(
        self,
        frame: int,
        config: _FamilyConfig,
    ) -> list[_Node]:
        candidates = self._candidate_sets.get(int(frame), [])
        if not candidates:
            return []
        det_scores = self._rank_to_ten([candidate[2] for candidate in candidates])
        motion_scores = self._motion_scores_for_frame(frame, candidates)
        nodes = []
        for candidate, det_score, motion_score in zip(candidates, det_scores, motion_scores):
            nodes.append(_Node(
                x=float(candidate[0]),
                y=float(candidate[1]),
                score=(
                    float(config.det_weight) * float(det_score)
                    + float(config.motion_weight) * float(motion_score)
                ),
            ))
        return nodes

    def _motion_scores_for_frame(
        self,
        frame: int,
        candidates: Sequence[Candidate],
    ) -> list[float]:
        prev_frame = self._previous_frame(frame)
        if prev_frame is None:
            return [0.0 for _candidate in candidates]
        previous = self._candidate_sets.get(prev_frame, [])
        if not previous:
            return [0.0 for _candidate in candidates]

        motions = []
        for candidate in candidates:
            prev = min(
                previous,
                key=lambda item: self._distance_xy(candidate, item),
            )
            motions.append((
                float(candidate[0]) - float(prev[0]),
                float(candidate[1]) - float(prev[1]),
            ))
        if not motions:
            return [0.0 for _candidate in candidates]
        bgx = float(np.median([motion[0] for motion in motions]))
        bgy = float(np.median([motion[1] for motion in motions]))
        anomaly = [
            math.hypot(motion[0] - bgx, motion[1] - bgy)
            for motion in motions
        ]
        return self._rank_to_ten(anomaly)

    def _previous_frame(self, frame: int) -> int | None:
        prior = [idx for idx in self._frames if int(idx) < int(frame)]
        if not prior:
            return None
        return int(prior[-1])

    @staticmethod
    def _transition_penalty(
        prev: _Node,
        cur: _Node,
        scale: float,
        max_jump: float,
    ) -> float:
        distance = math.hypot(prev.x - cur.x, prev.y - cur.y)
        penalty = distance / max(float(scale), 1e-6)
        if distance > float(max_jump):
            penalty += (distance - float(max_jump)) / max(float(scale) * 0.35, 1e-6)
        return penalty

    @staticmethod
    def _rank_to_ten(values: Sequence[float]) -> list[float]:
        if not values:
            return []
        numeric = [float(value) for value in values]
        if len(numeric) == 1:
            return [10.0]
        if max(numeric) - min(numeric) <= 1e-6:
            return [0.0 for _value in numeric]
        order = sorted(range(len(numeric)), key=lambda idx: numeric[idx], reverse=True)
        scores = [0.0 for _value in numeric]
        denom = max(1, len(numeric) - 1)
        for rank, idx in enumerate(order):
            scores[idx] = 10.0 * (denom - rank) / denom
        return scores

    @staticmethod
    def _distance_xy(a: Candidate, b: Candidate) -> float:
        return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))

    @staticmethod
    def _normalize_candidates(candidates: Sequence[Sequence[float]]) -> list[Candidate]:
        normalized = []
        for candidate in candidates:
            if len(candidate) < 2:
                continue
            score = float(candidate[2]) if len(candidate) >= 3 else 0.0
            width = float(candidate[3]) if len(candidate) >= 4 else 24.0
            height = float(candidate[4]) if len(candidate) >= 5 else 24.0
            normalized.append((
                float(candidate[0]),
                float(candidate[1]),
                score,
                width,
                height,
            ))
        return normalized
