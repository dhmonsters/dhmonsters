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
    ):
        self.window = max(2, int(window))
        self.min_frames = max(2, int(min_frames))
        self.merge_min_size = float(merge_min_size)
        self.merge_size_ratio = float(merge_size_ratio)
        self._mht_family_name = "bg_split_viterbi_center_mild_state_mild"
        self._mht_config = SolverConfig(
            keep=64,
            branch=8,
            gate=140.0,
            grid_size=5,
            shrink=0.76,
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
        self._start_point: Point | None = None

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

        if frame not in self._candidate_sets:
            self._frames.append(frame)
        self._candidate_sets[frame] = self._normalize_candidates(candidates)
        self._prune()

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
        for config in self._configs:
            path = self._viterbi_path(usable_frames, config)
            if path:
                points[config.name] = path[-1]
        mht_path = self._hidden_mht_path(usable_frames)
        latest_frame = usable_frames[-1]
        if latest_frame in mht_path:
            points[self._mht_family_name] = mht_path[latest_frame]
        return LiveFamilyDecision(points, {
            "frames": len(usable_frames),
            "ready": bool(points),
            "families": sorted(points),
        })

    def _prune(self) -> None:
        while len(self._frames) > self.window:
            old = self._frames.popleft()
            self._candidate_sets.pop(old, None)

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
