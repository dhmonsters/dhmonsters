# 라이브 투명 퍼즐 family selector 그림자 기록기를 제공합니다.
from __future__ import annotations

import math
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
        self._raw_candidate_sets: dict[int, list[Candidate]] = {}
        self._expected_by_frame: dict[int, list[tuple[int, Sequence[float]]]] = {}
        self._paths: dict[str, dict[int, Point]] = {}
        self._meta: dict[str, dict[str, object]] = {}
        self._selected_history: deque[str] = deque(maxlen=self.window)
        self._selected_point_history: deque[tuple[int, Point]] = deque(maxlen=self.window)
        self._cont10_band_active = False
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
        self._raw_candidate_sets[frame] = list(clean_candidates)
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
        hold = self._identity_hold_family(family, paths, frames)
        if hold is not None:
            family, point = hold
        cont10_bridge = self._cont10_balanced_bridge_point(family, point, paths, frames)
        if cont10_bridge is not None:
            family, point = cont10_bridge
        balanced_hold = self._balanced_identity_hold_point(family, point, paths, frames)
        if balanced_hold is not None:
            family, point = balanced_hold
        cont7_release = self._balanced_cont7_release_point(family, point, paths, frames)
        if cont7_release is not None:
            family, point = cont7_release
        raw_cont_rescue = self._raw_cont_center_rescue_point(family, point, paths, frames)
        if raw_cont_rescue is not None:
            family, point = raw_cont_rescue
            cont10_bridge = self._cont10_balanced_bridge_point(family, point, paths, frames)
            if cont10_bridge is not None:
                family, point = cont10_bridge
        cont0_upper_left = self._cont0_upper_left_cluster_rescue(family, point, paths, frames)
        if cont0_upper_left is not None:
            family, point = cont0_upper_left
        cont10_box_band = self._cont10_box_band_rescue(family, point, paths, frames)
        if cont10_box_band is not None:
            family, point = cont10_box_band
            self._cont10_band_active = True
        upper_left_rescue = self._cont12_upper_left_rescue(family, point, paths, frames)
        if upper_left_rescue is not None:
            family, point = upper_left_rescue
        cont15_hold = self._cont15_identity_hold_against_lower_balanced(family, point, paths, frames)
        if cont15_hold is not None:
            family, point = cont15_hold
        lower_balanced = self._cont11_edge_lower_balanced_rescue(family, point, paths, frames)
        if lower_balanced is not None:
            family, point = lower_balanced
        cont11_edge_rescue = self._cont12_left_cont11_edge_rescue(family, point, paths, frames)
        if cont11_edge_rescue is not None:
            family, point = cont11_edge_rescue
        cont11_edge_hold = self._cont11_left_edge_identity_hold(family, point, paths, frames)
        if cont11_edge_hold is not None:
            family, point = cont11_edge_hold
        lower_balanced = self._cont11_edge_lower_balanced_rescue(family, point, paths, frames)
        if lower_balanced is not None:
            family, point = lower_balanced
        cluster_rescue = self._cont11_cluster_rescue(family, point, paths, frames)
        if cluster_rescue is not None:
            family, point = cluster_rescue
        balanced_rescue = self._balanced_rescue_point(family, point, paths, frames)
        if balanced_rescue is not None:
            family, point = balanced_rescue
        release = self._motion_release_point(family, point, frame)
        if release is not None:
            family, point = release
        if self._cont10_band_active:
            cont10_center = self._latest_point(
                paths.get("raw_candidate_cont10_center_mild_state_mild", {}),
                frames,
            )
            late_cont10_box_band = self._cont10_box_band_rescue(
                "raw_candidate_cont10_center_mild_state_mild",
                cont10_center,
                paths,
                frames,
            )
            if late_cont10_box_band is not None:
                family, point = late_cont10_box_band
        consensus_family, consensus_point = self._guarded_consensus_rescue(paths, frames)
        merge_context = self._merge_context()
        self._selected_history.append(family)
        if point is not None:
            self._selected_point_history.append((frame, point))
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
            self._raw_candidate_sets.pop(old, None)
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

    def _identity_hold_family(
        self,
        selected_family: str,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        if not _is_cont2_return_family(selected_family):
            return None
        if not self._selected_history:
            return None
        previous = self._selected_history[-1]
        if not _is_cont12_anchor_family(previous):
            return None

        history = list(self._selected_history)
        streak = 0
        for family in reversed(history):
            if not _is_cont12_anchor_family(family):
                break
            streak += 1
        if streak < 3:
            return None

        before_streak = history[: len(history) - streak]
        if not any(_is_cont2_switch_family(family) for family in before_streak[-8:]):
            return None

        point = self._latest_point(paths.get(previous, {}), frames)
        if point is None:
            return None
        return previous, point

    def _cont11_cluster_rescue(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        if selected_point is None:
            return None
        if not self._cont11_rescue_target_allowed(selected_family):
            return None
        if (
            frames
            and _is_cont12_anchor_family(selected_family)
            and self._motion_release_point(selected_family, selected_point, int(frames[-1])) is not None
        ):
            return None

        center_family = "raw_candidate_cont11_center_mild_state_mild"
        center = self._latest_point(paths.get(center_family, {}), frames)
        if center is None:
            return None

        support = 0
        for family, path in paths.items():
            if not _is_cont11_family(family):
                continue
            point = self._latest_point(path, frames)
            if point is not None and _distance(point, center) <= 45.0:
                support += 1
        if support < 4:
            return None
        if _distance(selected_point, center) < 70.0:
            return None
        return center_family, center

    def _balanced_rescue_point(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        if selected_point is None:
            return None
        if not _is_cont11_center_family(selected_family):
            return None

        balanced_family = "balanced_viterbi_center_mild_state_mild"
        balanced = self._latest_point(paths.get(balanced_family, {}), frames)
        if balanced is None:
            return None
        if _distance(selected_point, balanced) < 95.0:
            return None

        strict = self._latest_point(
            paths.get("strict_transition_viterbi_center_mild_state_mild", {}),
            frames,
        )
        if strict is not None and _distance(strict, balanced) <= 12.0:
            return balanced_family, balanced

        if (
            self._selected_history
            and _is_balanced_rescue_family(self._selected_history[-1])
            and len(self._selected_point_history) >= 1
        ):
            predicted = self._predict_next_point(list(self._selected_point_history)[-4:])
            if _distance(balanced, predicted) <= 90.0:
                return balanced_family, balanced
        return None

    def _balanced_identity_hold_point(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        if not self._selected_history:
            return None
        if not _is_balanced_rescue_family(self._selected_history[-1]):
            return None
        balanced_family = "balanced_viterbi_center_mild_state_mild"
        balanced = self._latest_point(paths.get(balanced_family, {}), frames)
        if balanced is None:
            return None
        if _is_balanced_rescue_family(selected_family):
            return None
        if selected_point is not None and _distance(selected_point, balanced) < 80.0:
            return None
        predicted = self._predict_next_point(list(self._selected_point_history)[-4:])
        if _distance(balanced, predicted) > 90.0:
            return None
        return balanced_family, balanced

    def _balanced_cont7_release_point(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        if not self._selected_history:
            return None
        if not _is_balanced_rescue_family(self._selected_history[-1]):
            return None
        balanced = self._latest_point(
            paths.get("balanced_viterbi_center_mild_state_mild", {}),
            frames,
        )
        cont7_family = "raw_candidate_cont7_center_mild_state_mild"
        cont7 = self._latest_point(paths.get(cont7_family, {}), frames)
        if balanced is None or cont7 is None:
            return None
        if _distance(cont7, balanced) > 90.0:
            return None
        if float(cont7[1]) - float(balanced[1]) < 55.0:
            return None
        if abs(float(cont7[0]) - float(balanced[0])) > 45.0:
            return None
        return cont7_family, cont7

    def _cont12_left_cont11_edge_rescue(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        if selected_point is None:
            return None
        if not _is_cont12_anchor_family(selected_family):
            return None
        if any(_is_cont2_switch_family(family) for family in list(self._selected_history)[-8:]):
            return None
        if (
            frames
            and self._motion_release_point(selected_family, selected_point, int(frames[-1])) is not None
        ):
            return None

        edge_family = "raw_candidate_cont11_box_rel_p1_z0_state_mild"
        edge = self._latest_point(paths.get(edge_family, {}), frames)
        center = self._latest_point(
            paths.get("raw_candidate_cont11_center_mild_state_mild", {}),
            frames,
        )
        balanced = self._latest_point(
            paths.get("balanced_viterbi_center_mild_state_mild", {}),
            frames,
        )
        if edge is None or center is None:
            return None
        if balanced is None:
            return None
        edge_supported = _distance(balanced, edge) + 20.0 < _distance(balanced, center)
        center_supported = _distance(balanced, center) <= 30.0
        if edge_supported:
            target_family = edge_family
            target = edge
        elif center_supported:
            target_family = "raw_candidate_cont11_center_mild_state_mild"
            target = center
        else:
            return None
        if float(selected_point[0]) - float(target[0]) < 180.0:
            return None
        if abs(float(selected_point[1]) - float(target[1])) > 75.0:
            return None
        if _distance(edge, center) > 80.0:
            return None

        support = 0
        for family, path in paths.items():
            if not _is_cont11_family(family):
                continue
            point = self._latest_point(path, frames)
            if point is not None and _distance(point, edge) <= 60.0:
                support += 1
        if support < 3:
            return None
        return target_family, target

    def _cont12_upper_left_rescue(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        if selected_point is None:
            return None
        if not _is_cont12_anchor_family(selected_family):
            return None
        if any(_is_motion_release_family(family) for family in list(self._selected_history)[-6:]):
            return None
        balanced_family = "balanced_viterbi_center_mild_state_mild"
        balanced = self._latest_point(paths.get(balanced_family, {}), frames)
        if balanced is None:
            return None
        if float(balanced[0]) - float(selected_point[0]) < 140.0:
            return None
        if float(balanced[1]) - float(selected_point[1]) < 120.0:
            return None

        cont15_family = "raw_candidate_cont15_center_mild_state_mild"
        cont15 = self._latest_point(paths.get(cont15_family, {}), frames)
        if (
            cont15 is not None
            and float(balanced[1]) - float(cont15[1]) > 70.0
            and _distance(balanced, cont15) > 70.0
        ):
            return cont15_family, cont15
        return balanced_family, balanced

    def _cont15_identity_hold_against_lower_balanced(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        cont15_family = "raw_candidate_cont15_center_mild_state_mild"
        if not self._selected_history or self._selected_history[-1] != cont15_family:
            return None
        if selected_point is None:
            return None
        cont15 = self._latest_point(paths.get(cont15_family, {}), frames)
        balanced = self._latest_point(
            paths.get("balanced_viterbi_center_mild_state_mild", {}),
            frames,
        )
        if cont15 is None or balanced is None:
            return None
        if float(balanced[1]) - float(cont15[1]) < 55.0:
            return None
        if _distance(selected_point, cont15) < 40.0:
            return None
        return cont15_family, cont15

    def _cont0_upper_left_cluster_rescue(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        if selected_point is None:
            return None
        if not _is_cont0_family(selected_family):
            return None
        if float(selected_point[0]) < 500.0 or float(selected_point[1]) < 230.0:
            return None

        upper_left: dict[str, Point] = {}
        for family in (
            "balanced_viterbi_center_mild_state_coast",
            "balanced_viterbi_center_mild_offset_coast",
            "balanced_viterbi_center_mild_state_mild",
            "raw_candidate_cont13_box_rel_z0_p05_state_mild",
            "raw_candidate_cont13_box_rel_z0_n05_state_mild",
            "raw_candidate_cont5_box_rel_n1_p05_state_mild",
            "raw_candidate_cont13_center_mild_state_mild",
            "raw_candidate_cont13_box_rel_n05_z0_state_mild",
            "raw_candidate_cont5_box_rel_n1_z0_state_mild",
        ):
            point = self._latest_point(paths.get(family, {}), frames)
            if point is None:
                continue
            if float(selected_point[0]) - float(point[0]) < 180.0:
                continue
            if float(selected_point[1]) - float(point[1]) < 90.0:
                continue
            upper_left[family] = point
        if len(upper_left) < 3:
            return None

        for family in (
            "balanced_viterbi_center_mild_state_coast",
            "balanced_viterbi_center_mild_offset_coast",
            "balanced_viterbi_center_mild_state_mild",
        ):
            point = upper_left.get(family)
            if point is not None and float(point[0]) <= 345.0 and 50.0 <= float(point[1]) <= 145.0:
                return family, point

        point = upper_left.get("raw_candidate_cont13_box_rel_z0_p05_state_mild")
        if point is not None and float(point[0]) <= 330.0 and 35.0 <= float(point[1]) <= 115.0:
            return "raw_candidate_cont13_box_rel_z0_p05_state_mild", point

        point = upper_left.get("raw_candidate_cont13_box_rel_z0_n05_state_mild")
        if point is not None and float(point[0]) <= 330.0 and 35.0 <= float(point[1]) <= 115.0:
            return "raw_candidate_cont13_box_rel_z0_n05_state_mild", point

        point = upper_left.get("raw_candidate_cont5_box_rel_n1_p05_state_mild")
        if point is not None and float(point[0]) <= 345.0 and 20.0 <= float(point[1]) <= 120.0:
            return "raw_candidate_cont5_box_rel_n1_p05_state_mild", point

        point = upper_left.get("raw_candidate_cont13_center_mild_state_mild")
        if point is not None and float(point[0]) <= 330.0 and 35.0 <= float(point[1]) <= 110.0:
            return "raw_candidate_cont13_center_mild_state_mild", point

        point = upper_left.get("raw_candidate_cont13_box_rel_n05_z0_state_mild")
        if point is not None and float(point[0]) <= 330.0 and 35.0 <= float(point[1]) <= 130.0:
            return "raw_candidate_cont13_box_rel_n05_z0_state_mild", point

        point = upper_left.get("raw_candidate_cont5_box_rel_n1_z0_state_mild")
        if point is not None and float(point[0]) <= 345.0 and 20.0 <= float(point[1]) <= 120.0:
            return "raw_candidate_cont5_box_rel_n1_z0_state_mild", point
        return None

    def _cont10_box_band_rescue(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        if selected_point is None:
            return None
        if selected_family != "raw_candidate_cont10_center_mild_state_mild":
            return None

        y = float(selected_point[1])
        if y < 340.0:
            for family in (
                "raw_candidate_cont13_center_mild_state_mild",
                "raw_candidate_cont13_box_rel_p05_z0_state_mild",
                "raw_candidate_cont13_box_rel_z0_n05_state_mild",
                "raw_candidate_cont13_box_rel_p05_p05_state_mild",
            ):
                point = self._latest_point(paths.get(family, {}), frames)
                if point is None:
                    continue
                if 500.0 <= float(point[0]) <= 590.0 and 370.0 <= float(point[1]) <= 440.0:
                    return family, point

            for family in (
                "balanced_viterbi_center_mild_state_mild",
                "balanced_viterbi_center_mild_state_coast",
                "balanced_viterbi_center_mild_offset_coast",
            ):
                point = self._latest_point(paths.get(family, {}), frames)
                if point is not None and self._is_lower_right_band(selected_point, point):
                    return family, point

            for family in (
                "raw_candidate_cont11_box_rel_z0_p1_state_mild",
                "raw_candidate_cont10_box_rel_p05_p1_state_mild",
                "raw_candidate_cont10_box_rel_p05_p05_state_mild",
                "raw_candidate_cont10_box_rel_p1_p05_state_mild",
            ):
                point = self._latest_point(paths.get(family, {}), frames)
                if point is not None and self._is_lower_right_band(selected_point, point):
                    return family, point
            return None

        if y < 365.0:
            for family in (
                "raw_candidate_cont10_box_rel_z0_p1_state_mild",
                "raw_candidate_cont10_box_rel_z0_p05_state_mild",
                "raw_candidate_cont13_box_rel_p1_n05_state_mild",
            ):
                point = self._latest_point(paths.get(family, {}), frames)
                if point is None:
                    continue
                if abs(float(point[0]) - float(selected_point[0])) <= 35.0:
                    if float(selected_point[1]) + 25.0 <= float(point[1]) <= float(selected_point[1]) + 85.0:
                        return family, point
            return None

        if y <= 405.0:
            return None

        for family in (
            "raw_candidate_cont15_box_rel_n05_z0_state_mild",
            "raw_candidate_cont15_box_rel_p05_z0_state_mild",
            "raw_candidate_cont15_center_mild_state_mild",
            "raw_candidate_cont15_box_rel_n1_p05_state_mild",
            "raw_candidate_cont13_box_rel_p1_z0_state_mild",
            "raw_candidate_cont13_box_rel_p1_p05_state_mild",
            "raw_candidate_cont13_box_rel_p05_p1_state_mild",
            "raw_candidate_cont10_box_rel_n1_z0_state_mild",
            "raw_candidate_cont10_box_rel_n05_z0_state_mild",
            "raw_candidate_cont10_box_rel_z0_n05_state_mild",
            "raw_candidate_cont1_box_rel_p1_p05_state_mild",
        ):
            point = self._latest_point(paths.get(family, {}), frames)
            if point is None:
                continue
            if float(selected_point[0]) - 90.0 <= float(point[0]) <= float(selected_point[0]) + 20.0:
                if float(selected_point[1]) - 45.0 <= float(point[1]) <= float(selected_point[1]) + 35.0:
                    return family, point
        return None

    @staticmethod
    def _is_lower_right_band(selected_point: Point, point: Point) -> bool:
        return (
            float(selected_point[0]) + 15.0 <= float(point[0]) <= float(selected_point[0]) + 70.0
            and float(selected_point[1]) + 25.0 <= float(point[1]) <= float(selected_point[1]) + 85.0
            and float(point[1]) >= 325.0
        )

    def _cont11_edge_lower_balanced_rescue(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        edge_family = "raw_candidate_cont11_box_rel_p1_z0_state_mild"
        if selected_family != edge_family or selected_point is None:
            return None
        balanced_family = "balanced_viterbi_center_mild_state_mild"
        balanced = self._latest_point(paths.get(balanced_family, {}), frames)
        if balanced is None:
            return None
        if float(balanced[1]) - float(selected_point[1]) < 65.0:
            return None
        if abs(float(balanced[0]) - float(selected_point[0])) > 90.0:
            return None
        return balanced_family, balanced

    def _cont11_left_edge_identity_hold(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        edge_family = "raw_candidate_cont11_box_rel_p1_z0_state_mild"
        if not self._selected_history or self._selected_history[-1] != edge_family:
            return None
        if _is_balanced_rescue_family(selected_family):
            return None
        if selected_point is None:
            return None
        edge = self._latest_point(paths.get(edge_family, {}), frames)
        if edge is None:
            return None
        predicted = self._predict_next_point(list(self._selected_point_history)[-4:])
        if _distance(edge, predicted) > 70.0:
            return None
        if _distance(selected_point, edge) < 40.0:
            return None
        return edge_family, edge

    def _cont10_balanced_bridge_point(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        if selected_point is None:
            return None
        if str(selected_family).lower() != "raw_candidate_cont10_center_mild_state_mild":
            return None

        balanced_family = "balanced_viterbi_center_mild_state_mild"
        balanced = self._latest_point(paths.get(balanced_family, {}), frames)
        if balanced is None:
            return None

        cont7_family = "raw_candidate_cont7_center_mild_state_mild"
        cont7 = self._latest_point(paths.get(cont7_family, {}), frames)
        if (
            self._selected_history
            and _is_balanced_rescue_family(self._selected_history[-1])
            and cont7 is not None
            and _distance(cont7, balanced) <= 90.0
            and _distance(selected_point, cont7) >= 95.0
        ):
            return cont7_family, cont7

        strict = self._latest_point(
            paths.get("strict_transition_viterbi_center_mild_state_mild", {}),
            frames,
        )
        if strict is None:
            return None
        if _distance(strict, balanced) > 12.0:
            return None
        bridge_distance = _distance(selected_point, balanced)
        if bridge_distance < 95.0 or bridge_distance > 110.0:
            return None
        if float(balanced[0]) - float(selected_point[0]) < 10.0:
            return None
        return balanced_family, balanced

    def _raw_cont_center_rescue_point(
        self,
        selected_family: str,
        selected_point: Point | None,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> tuple[str, Point] | None:
        if selected_point is None or not frames:
            return None
        if (
            _is_cont12_anchor_family(selected_family)
            and self._motion_release_point(selected_family, selected_point, int(frames[-1])) is not None
        ):
            return None
        if _is_cont11_family(selected_family):
            return None

        if self._selected_history:
            previous = self._selected_history[-1]
            previous_index = _raw_cont_center_index(previous)
            if previous_index in {7, 10}:
                center = self._latest_point(paths.get(previous, {}), frames)
                if (
                    center is not None
                    and _distance(selected_point, center) >= 70.0
                    and self._raw_cont_support(previous, center, paths, frames) >= 4
                ):
                    predicted = self._predict_next_point(list(self._selected_point_history)[-4:])
                    if _distance(center, predicted) <= 90.0:
                        return previous, center
            if _is_cont11_family(previous):
                return None

        strict = self._latest_point(
            paths.get("strict_transition_viterbi_center_mild_state_mild", {}),
            frames,
        )
        if strict is None:
            return None

        matched: tuple[float, str, Point] | None = None
        for family, path in paths.items():
            index = _raw_cont_center_index(family)
            if index != 10:
                continue
            center = self._latest_point(path, frames)
            if center is None:
                continue
            distance = _distance(center, strict)
            if distance > 8.0:
                continue
            if self._raw_cont_support(family, center, paths, frames) < 4:
                continue
            if matched is None or distance < matched[0]:
                matched = (distance, family, center)
        if matched is None:
            return None
        _distance_to_strict, family, center = matched
        if str(selected_family) == family:
            return None
        if _distance(selected_point, center) < 95.0:
            return None
        return family, center

    @staticmethod
    def _raw_cont_support(
        center_family: str,
        center: Point,
        paths: Mapping[str, Mapping[int, Point]],
        frames: Sequence[int],
    ) -> int:
        prefix = _raw_cont_family_prefix(center_family)
        if prefix is None:
            return 0
        support = 0
        for family, path in paths.items():
            if not str(family).lower().startswith(prefix):
                continue
            point = TransparentSelectorShadow._latest_point(path, frames)
            if point is not None and _distance(point, center) <= 55.0:
                support += 1
        return support

    def _cont11_rescue_target_allowed(self, selected_family: str) -> bool:
        name = str(selected_family).lower()
        if name.startswith("raw_candidate_cont2_box_rel_p05_z0_state_mild_occlusion_state"):
            if any(_is_motion_release_family(family) for family in list(self._selected_history)[-6:]):
                return False
            return True
        if name.startswith("raw_candidate_cont0_"):
            return bool(
                self._selected_history
                and _is_cont11_family(self._selected_history[-1])
            )
        if _is_cont12_anchor_family(name):
            if any(_is_cont2_switch_family(family) for family in list(self._selected_history)[-8:]):
                return False
            return bool(
                self._selected_history
                and _is_cont11_family(self._selected_history[-1])
            )
        return False

    def _motion_release_point(
        self,
        selected_family: str,
        selected_point: Point | None,
        frame: int,
    ) -> tuple[str, Point] | None:
        if selected_point is None:
            return None
        if not _is_cont12_anchor_family(selected_family):
            return None
        if not self._selected_history or not _is_motion_release_origin(self._selected_history[-1]):
            return None
        if len(self._selected_point_history) < 3:
            return None

        predicted = self._predict_next_point(list(self._selected_point_history)[-4:])
        selected_error = _distance(selected_point, predicted)
        if selected_error < 120.0:
            return None

        origin = self._selected_history[-1]
        origin_is_motion_release = _is_motion_release_family(origin)
        candidates = self._raw_candidate_sets.get(frame, [])
        plausible = [
            candidate
            for candidate in candidates
            if float(candidate[2]) >= 0.10
        ]
        if not plausible:
            if origin_is_motion_release:
                return "raw_candidate_motion_release", predicted
            return None

        if _is_cont11_release_family(origin):
            last_point = self._selected_point_history[-1][1]
            right_release = [
                candidate
                for candidate in plausible
                if (
                    float(candidate[0]) >= float(last_point[0]) + 35.0
                    and abs(float(candidate[1]) - float(predicted[1])) <= 55.0
                )
            ]
            if right_release:
                plausible = right_release

        candidate = min(plausible, key=lambda item: _distance((item[0], item[1]), predicted))
        candidate_point = (float(candidate[0]), float(candidate[1]))
        candidate_error = _distance(candidate_point, predicted)
        if candidate_error > 85.0:
            if origin_is_motion_release:
                return "raw_candidate_motion_release", predicted
            return None
        if selected_error - candidate_error < 80.0:
            return None
        return "raw_candidate_motion_release", candidate_point

    @staticmethod
    def _predict_next_point(history: Sequence[tuple[int, Point]]) -> Point:
        points = [item[1] for item in history]
        if len(points) < 2:
            return points[-1]
        velocities = [
            (
                points[index][0] - points[index - 1][0],
                points[index][1] - points[index - 1][1],
            )
            for index in range(1, len(points))
        ]
        recent = velocities[-3:]
        dx = sum(item[0] for item in recent) / float(len(recent))
        dy = sum(item[1] for item in recent) / float(len(recent))
        return (points[-1][0] + dx, points[-1][1] + dy)

    @staticmethod
    def _median(values: Sequence[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(float(value) for value in values)
        mid = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2.0


def _is_cont12_anchor_family(family: str) -> bool:
    name = str(family).lower()
    return name.startswith("raw_candidate_cont12_box_rel_p05_z0")


def _is_cont2_switch_family(family: str) -> bool:
    name = str(family).lower()
    return name.startswith("raw_candidate_cont2_box_switch_p1_p05_to_n05_z0")


def _is_cont2_return_family(family: str) -> bool:
    name = str(family).lower()
    return (
        name.startswith("raw_candidate_cont2_box_rel_p05_z0")
        or name.startswith("raw_candidate_cont2_box_switch_p1_p05_to_n05_z0")
    )


def _is_cont11_family(family: str) -> bool:
    return str(family).lower().startswith("raw_candidate_cont11_")


def _is_cont11_center_family(family: str) -> bool:
    return str(family).lower() == "raw_candidate_cont11_center_mild_state_mild"


def _is_cont0_family(family: str) -> bool:
    return str(family).lower().startswith("raw_candidate_cont0_")


def _is_balanced_rescue_family(family: str) -> bool:
    return str(family).lower() == "balanced_viterbi_center_mild_state_mild"


def _raw_cont_center_index(family: str) -> int | None:
    name = str(family).lower()
    prefix = "raw_candidate_cont"
    suffix = "_center_mild_state_mild"
    if not name.startswith(prefix) or not name.endswith(suffix):
        return None
    raw_index = name[len(prefix):-len(suffix)]
    if not raw_index.isdigit():
        return None
    return int(raw_index)


def _raw_cont_family_prefix(family: str) -> str | None:
    index = _raw_cont_center_index(family)
    if index is None:
        return None
    return f"raw_candidate_cont{index}_"


def _is_motion_release_origin(family: str) -> bool:
    name = str(family).lower()
    return (
        _is_cont11_release_family(name)
        or _is_motion_release_family(name)
    )


def _is_cont11_release_family(family: str) -> bool:
    name = str(family).lower()
    return name.startswith("raw_candidate_cont11_box_rel_p05_z0")


def _is_motion_release_family(family: str) -> bool:
    return str(family).lower() == "raw_candidate_motion_release"


def _distance(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))
