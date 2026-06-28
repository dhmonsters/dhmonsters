# 라이브 투명 퍼즐 family selector 그림자 기록기를 제공합니다.
from __future__ import annotations

from collections import deque
from typing import Mapping, Sequence, Tuple

import _local_box_family_score as local_box


Point = Tuple[float, float]
Candidate = Tuple[float, float, float, float, float]

KNOWN_SOURCES = (
    "balanced_viterbi",
    "bg_split_viterbi",
    "strict_transition_viterbi",
    "panel_default",
    "merge_context",
    "phase_catalog",
    "guarded_decal_identity",
)


def _point(value: Sequence[float] | None) -> Point | None:
    if value is None or len(value) < 2:
        return None
    return (float(value[0]), float(value[1]))


def _candidate(value: Sequence[float]) -> Candidate | None:
    if len(value) < 2:
        return None
    score = float(value[2]) if len(value) >= 3 else 0.0
    width = float(value[3]) if len(value) >= 4 else 1.0
    height = float(value[4]) if len(value) >= 5 else 1.0
    return (float(value[0]), float(value[1]), score, width, height)


def _local_box_candidate(candidate: Candidate) -> tuple[float, float, float, float, float]:
    return (
        float(candidate[0]),
        float(candidate[1]),
        float(candidate[3]),
        float(candidate[4]),
        float(candidate[2]),
    )


def _source_for_family(family: str) -> str:
    name = family.lower()
    for source in KNOWN_SOURCES:
        if name.startswith(source):
            return source
    return family


def _serial_point(point: Point | None) -> list[int] | None:
    if point is None:
        return None
    return [int(round(point[0])), int(round(point[1]))]


def _serial_float_point(point: Point | None) -> list[float] | None:
    if point is None:
        return None
    return [float(point[0]), float(point[1])]


def _rescue_allowed_for_family(family: str, merge_context: Mapping[str, object]) -> bool:
    name = str(family).lower()
    if name.startswith("guarded_decal_identity"):
        return True
    return (
        (
            name.startswith("bg_split_viterbi")
            or name.startswith("merge_context")
        )
        and int(merge_context.get("frames", 0) or 0) > 0
    )


class TransparentSelectorShadow:
    def __init__(
        self,
        runtime,
        *,
        clip_id: str = "live",
        window: int = 36,
        min_frames: int = 8,
        emit_every: int = 5,
        max_candidates: int = 12,
        include_local_box: bool = True,
        merge_context_frames: int = 6,
        merge_min_size: float = 175.0,
        merge_size_ratio: float = 1.30,
    ):
        self.runtime = runtime
        self.window = max(1, int(window))
        self.min_frames = max(1, int(min_frames))
        self.emit_every = max(1, int(emit_every))
        self.max_candidates = max(1, int(max_candidates))
        self.include_local_box = bool(include_local_box)
        self.merge_context_frames = max(1, int(merge_context_frames))
        self.merge_min_size = float(merge_min_size)
        self.merge_size_ratio = float(merge_size_ratio)
        self.reset(clip_id=clip_id)

    def reset(self, *, clip_id: str | None = None) -> None:
        if clip_id is not None:
            self.clip_id = str(clip_id)
        self._frames: deque[int] = deque()
        self._candidate_sets: dict[int, list[Candidate]] = {}
        self._expected_by_frame: dict[int, list[tuple[int, Sequence[float]]]] = {}
        self._paths: dict[str, dict[int, Point]] = {}
        self._meta: dict[str, dict[str, object]] = {}
        self._updates = 0

    def update(
        self,
        frame_index: int,
        *,
        candidates: Sequence[Sequence[float]],
        anchors: Mapping[str, Sequence[float] | None],
        expected_by_frame: Mapping[int, Sequence[tuple[int, Sequence[float]]]] | None = None,
    ) -> dict | None:
        frame = int(frame_index)
        if frame not in self._candidate_sets:
            self._frames.append(frame)

        normalized = [_candidate(candidate) for candidate in candidates]
        clean_candidates = [candidate for candidate in normalized if candidate is not None]
        clean_candidates.sort(key=lambda candidate: candidate[2], reverse=True)
        self._candidate_sets[frame] = clean_candidates[: self.max_candidates]
        if expected_by_frame:
            for key, expected in expected_by_frame.items():
                self._expected_by_frame[int(key)] = [
                    (int(item[0]), item[1])
                    for item in expected
                ]

        for family, value in anchors.items():
            point = _point(value)
            if point is None:
                continue
            name = str(family)
            self._paths.setdefault(name, {})[frame] = point
            self._meta.setdefault(name, {
                "source": _source_for_family(name),
                "mode": "base",
            })

        self._prune_old_frames()
        self._updates += 1
        if self._updates % self.emit_every != 0:
            return None
        if len(self._frames) < self.min_frames:
            return None
        if not getattr(self.runtime, "available", False):
            return {
                "clip": self.clip_id,
                "frame": frame,
                "available": False,
                "error": str(getattr(self.runtime, "load_error", "")),
            }

        paths, meta = self._build_path_pool()
        if not paths:
            return None
        frames = list(self._frames)
        selected, rows = self.runtime.select_from_path_pool(
            self.clip_id,
            paths,
            frames,
            meta=meta,
            candidate_sets={
                idx: self._candidate_sets.get(idx, [])
                for idx in frames
            },
            expected_by_frame={
                idx: self._expected_by_frame.get(idx, [])
                for idx in frames
            },
        )
        selected_row = selected.get(self.clip_id)
        if not selected_row:
            return None

        family = str(selected_row.get("family", ""))
        point = _point(selected_row.get("point"))
        if point is None:
            point = _point(selected_row.get("rescue_point"))
        if point is None:
            point = self._latest_point(paths.get(family, {}), frames)
        consensus_family, consensus_point = self._guarded_consensus_rescue(paths, frames)
        merge_context = self._merge_context()
        return {
            "clip": self.clip_id,
            "frame": frame,
            "available": True,
            "family": family,
            "point": _serial_point(point),
            "rescue_point": _serial_float_point(point),
            "rescue_allowed": _rescue_allowed_for_family(family, merge_context),
            "consensus_rescue_family": consensus_family,
            "consensus_rescue_point": _serial_float_point(consensus_point),
            "consensus_rescue_allowed": consensus_point is not None,
            "merge_context": merge_context,
            "rows": len(rows),
            "paths": len(paths),
            "frames": len(frames),
            "rank_center": float(selected_row.get("rank_center", 0.0) or 0.0),
            "rank_rough": float(selected_row.get("rank_rough", 0.0) or 0.0),
        }

    def _prune_old_frames(self) -> None:
        while len(self._frames) > self.window:
            old = self._frames.popleft()
            self._candidate_sets.pop(old, None)
            self._expected_by_frame.pop(old, None)
            for path in self._paths.values():
                path.pop(old, None)

    def _build_path_pool(self) -> tuple[dict[str, dict[int, Point]], dict[str, dict[str, object]]]:
        frames = list(self._frames)
        paths = {
            family: {
                frame: point
                for frame, point in path.items()
                if frame in self._candidate_sets
            }
            for family, path in self._paths.items()
        }
        paths = {
            family: path
            for family, path in paths.items()
            if len(path) >= self.min_frames
        }
        meta = {
            family: dict(self._meta.get(family, {}))
            for family in paths
        }
        if not self.include_local_box or not paths:
            return paths, meta

        local_box_candidate_sets = {
            frame: [_local_box_candidate(candidate) for candidate in self._candidate_sets.get(frame, [])]
            for frame in frames
        }
        augmented = local_box.augment_local_box_paths(
            paths,
            local_box_candidate_sets,
            frames,
            local_box_families=list(paths),
        )
        for family in list(paths):
            base_meta = meta.get(family, {})
            for variant in local_box.DEFAULT_VARIANTS:
                variant_name = f"{family}_lb_{variant.name}"
                if variant_name in augmented:
                    meta[variant_name] = {
                        "source": family,
                        "mode": "local_box",
                        "variant": variant.name,
                        "suspect_count": base_meta.get("suspect_count", 0),
                    }
        return augmented, meta

    def _merge_context(self) -> dict:
        frames = list(self._frames)[-self.merge_context_frames:]
        context_frames = 0
        latest = False
        max_size = 0.0
        max_ratio = 0.0

        for frame in frames:
            candidates = self._candidate_sets.get(frame, [])
            sizes = [
                max(float(candidate[3]), float(candidate[4]))
                for candidate in candidates
            ]
            if not sizes:
                continue
            median_size = self._median(sizes)
            frame_max_size = max(sizes)
            frame_max_ratio = (
                frame_max_size / median_size
                if median_size > 1e-6
                else 0.0
            )
            merge_like = (
                frame_max_size >= self.merge_min_size
                or frame_max_ratio >= self.merge_size_ratio
            )
            max_size = max(max_size, frame_max_size)
            max_ratio = max(max_ratio, frame_max_ratio)
            if merge_like:
                context_frames += 1
                latest = frame == frames[-1]

        return {
            "frames": int(context_frames),
            "latest": bool(latest),
            "max_size": round(max_size, 1),
            "max_ratio": round(max_ratio, 3),
        }

    @staticmethod
    def _latest_point(path: Mapping[int, Point], frames: Sequence[int]) -> Point | None:
        for frame in reversed(frames):
            if frame in path:
                return path[frame]
        return None

    @staticmethod
    def _guarded_consensus_rescue(
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str | None, Point | None]:
        for family in sorted(paths):
            if not family.lower().startswith("guarded_decal_identity_consensus"):
                continue
            point = TransparentSelectorShadow._latest_point(paths.get(family, {}), frames)
            if point is not None:
                return family, point
        return None, None

    @staticmethod
    def _median(values: Sequence[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(float(value) for value in values)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2.0
