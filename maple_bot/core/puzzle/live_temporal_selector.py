# 라이브 투명도형 시간축 selector를 퍼즐 런타임에서 쓰기 쉽게 묶습니다.
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from core.vision.transparent_family_selector_runtime import TransparentFamilySelectorRuntime
from core.vision.transparent_kinematic_shape import (
    TransparentKinematicBeamTracker,
    TransparentKinematicShapeTracker,
)
from core.vision.transparent_live_family_pool import LiveFamilyDecision, TransparentLiveFamilyPool
from core.vision.transparent_selector_shadow import TransparentSelectorShadow
from core.vision.transparent_track_health import TrackHealthDecision, TransparentTrackHealthSelector


Point = tuple[float, float]
CandidateRow = tuple[float, float, float, float, float]
FAST_LIVE_BOX_REL_PAIRS = frozenset({
    ("n05", "p05"),
    ("n05", "z0"),
    ("n1", "p05"),
    ("n1", "z0"),
    ("p05", "n05"),
    ("p05", "p05"),
    ("p05", "p1"),
    ("p05", "z0"),
    ("p1", "n05"),
    ("p1", "p05"),
    ("p1", "z0"),
    ("z0", "n05"),
    ("z0", "p05"),
    ("z0", "p1"),
})
LEGACY_RESCUE_MIN_BOARD_WIDTH = 600
KINEMATIC_SHAPE_FAMILY = "kinematic_shape_center_mild_state_mild"


@dataclass(frozen=True)
class LiveTemporalDecision:
    point: Point | None
    source: str
    reason: str
    family: str | None = None
    selector_record: Mapping[str, object] | None = None
    live_family_points: Mapping[str, Point] = field(default_factory=dict)
    health: TrackHealthDecision | None = None
    debug: Mapping[str, object] = field(default_factory=dict)


class LiveTemporalSelector:
    def __init__(
        self,
        *,
        runtime: Any | None = None,
        family_pool: Any | None = None,
        selector_shadow: Any | None = None,
        health_selector: TransparentTrackHealthSelector | None = None,
        kinematic_shape_tracker: Any | None = None,
        kinematic_beam_tracker: Any | None = None,
        kinematic_wide_beam_tracker: Any | None = None,
        kinematic_explorer_beam_tracker: Any | None = None,
        enable_kinematic_shape: bool = False,
        clip_id: str = "live",
        window: int = 24,
        min_frames: int = 8,
        live_max_candidates: int = 24,
        include_local_box: bool = False,
        use_expected_background: bool = False,
        legacy_rescue_min_board_width: int = LEGACY_RESCUE_MIN_BOARD_WIDTH,
    ) -> None:
        self.runtime = runtime or TransparentFamilySelectorRuntime()
        self.family_pool = family_pool or TransparentLiveFamilyPool(
            window=window,
            min_frames=min_frames,
            enable_phase_catalog=False,
            enable_bg_mht=False,
            enable_raw_mht=False,
            enable_phase_mht=False,
            enable_guarded_decal_identity=False,
            raw_rank_families=0,
            raw_continuity_families=20,
            raw_beam_families=0,
            raw_beam_spawn=0,
            raw_max_candidates_per_frame=24,
            raw_box_rel_pairs=FAST_LIVE_BOX_REL_PAIRS,
        )
        self.selector_shadow = selector_shadow or TransparentSelectorShadow(
            self.runtime,
            clip_id=clip_id,
            window=window,
            min_frames=min_frames,
            emit_every=1,
            max_candidates=8,
            include_local_box=include_local_box,
            merge_context_frames=6,
            merge_min_size=175.0,
            merge_size_ratio=1.30,
        )
        self.health_selector = health_selector or TransparentTrackHealthSelector()
        self.kinematic_shape_tracker = kinematic_shape_tracker or TransparentKinematicShapeTracker()
        self.kinematic_beam_tracker = kinematic_beam_tracker or TransparentKinematicBeamTracker()
        self.kinematic_wide_beam_tracker = kinematic_wide_beam_tracker or TransparentKinematicBeamTracker(
            width=16,
            branch=5,
            cost_decay=1.0,
            acceleration_weight=0.5,
            yolo_penalty_weight=0.0,
        )
        self.kinematic_explorer_beam_tracker = (
            kinematic_explorer_beam_tracker or TransparentKinematicBeamTracker(
                width=24,
                branch=5,
                cost_decay=1.0,
                acceleration_weight=0.5,
                yolo_penalty_weight=0.0,
                diverse_first=True,
            )
        )
        self.enable_kinematic_shape = bool(enable_kinematic_shape)
        self.live_max_candidates = max(1, int(live_max_candidates))
        self.use_expected_background = bool(use_expected_background)
        self.legacy_rescue_min_board_width = max(1, int(legacy_rescue_min_board_width))
        self._seeded = False

    def reset(self, *, point: Point | None = None) -> None:
        if hasattr(self.family_pool, "reset"):
            self.family_pool.reset()
        if hasattr(self.selector_shadow, "reset"):
            self.selector_shadow.reset(clip_id="live")
        self.health_selector.reset(point)
        self.kinematic_shape_tracker.reset()
        self.kinematic_beam_tracker.reset()
        self.kinematic_wide_beam_tracker.reset()
        self.kinematic_explorer_beam_tracker.reset()
        self._seeded = point is not None

    def update(
        self,
        *,
        frame_index: int,
        candidates: Sequence[Sequence[float]],
        primary_point: Sequence[float] | None,
        white_anchor: Sequence[float] | None = None,
        wide_white_anchor: Sequence[float] | None = None,
        engine_point: Sequence[float] | None = None,
        frame_shape: Sequence[int] | None = None,
    ) -> LiveTemporalDecision:
        clean_candidates = _normalize_candidates(candidates)
        anchor = _point(white_anchor)
        live_candidates = _limit_candidates(clean_candidates, self.live_max_candidates)
        if anchor is not None:
            live_candidates = []
            self._seeded = True
        elif not self._seeded and primary_point is not None:
            anchor = _point(primary_point)
            live_candidates = []
            self._seeded = anchor is not None

        live_decision = self.family_pool.update(
            int(frame_index),
            candidates=live_candidates,
            white_anchor=anchor,
        )
        anchors = _anchors_from_live_family(live_decision)
        shape_point = self.kinematic_shape_tracker.update(
            clean_candidates,
            white_anchor=anchor,
        )
        beam_point = self.kinematic_beam_tracker.update(
            clean_candidates,
            white_anchor=anchor,
        )
        self.kinematic_wide_beam_tracker.update(
            clean_candidates,
            white_anchor=_point(wide_white_anchor) or anchor,
        )
        self.kinematic_explorer_beam_tracker.update(
            clean_candidates,
            white_anchor=_point(wide_white_anchor) or anchor,
        )
        wide_beam_points = tuple(
            self.kinematic_wide_beam_tracker.hypothesis_points
        )
        explorer_beam_points = tuple(
            self.kinematic_explorer_beam_tracker.hypothesis_points
        )
        if self.enable_kinematic_shape and shape_point is not None:
            anchors[KINEMATIC_SHAPE_FAMILY] = shape_point
        primary = _point(primary_point)
        if primary is not None:
            anchors["panel_default_center_mild_state_mild"] = primary
        engine = _point(engine_point)
        if engine is not None:
            anchors["phase_catalog_center_mild_state_mild"] = engine

        selector_record = None
        if anchors:
            selector_record = self.selector_shadow.update(
                int(frame_index),
                candidates=clean_candidates,
                anchors=anchors,
                expected_by_frame=(
                    _expected_background_by_frame(
                        self.family_pool,
                        [int(frame_index)],
                    )
                    if self.use_expected_background
                    else {}
                ),
                allow_legacy_rescues=_legacy_rescues_allowed(
                    frame_shape,
                    min_board_width=self.legacy_rescue_min_board_width,
                ),
            )

        selected = _selector_point(selector_record)
        rescue = _allowed_rescue_point(selector_record)
        health = self.health_selector.update(
            primary=primary,
            rescue=rescue,
            frame_shape=frame_shape,
            force_primary=anchor is not None,
        )

        if selected is not None:
            return LiveTemporalDecision(
                point=selected,
                source="selector_shadow",
                reason="selected_family",
                family=str(selector_record.get("family", "")) if isinstance(selector_record, Mapping) else None,
                selector_record=selector_record,
                live_family_points=anchors,
                health=health,
                debug=_debug_payload(
                    live_decision,
                    selector_record,
                    shape_point=shape_point,
                    beam_point=beam_point,
                    beam_debug=getattr(self.kinematic_beam_tracker, "last_debug", {}),
                    wide_beam_points=wide_beam_points,
                    wide_beam_debug=getattr(self.kinematic_wide_beam_tracker, "last_debug", {}),
                    explorer_beam_points=explorer_beam_points,
                    explorer_beam_debug=getattr(self.kinematic_explorer_beam_tracker, "last_debug", {}),
                ),
            )
        return LiveTemporalDecision(
            point=health.point,
            source=health.source,
            reason=health.reason,
            selector_record=selector_record,
            live_family_points=anchors,
            health=health,
            debug=_debug_payload(
                live_decision,
                selector_record,
                shape_point=shape_point,
                beam_point=beam_point,
                beam_debug=getattr(self.kinematic_beam_tracker, "last_debug", {}),
                wide_beam_points=wide_beam_points,
                wide_beam_debug=getattr(self.kinematic_wide_beam_tracker, "last_debug", {}),
                explorer_beam_points=explorer_beam_points,
                explorer_beam_debug=getattr(self.kinematic_explorer_beam_tracker, "last_debug", {}),
            ),
        )


def _normalize_candidates(candidates: Sequence[Sequence[float]]) -> list[CandidateRow]:
    out: list[CandidateRow] = []
    for row in candidates:
        if len(row) < 2:
            continue
        score = float(row[2]) if len(row) >= 3 else 0.0
        width = float(row[3]) if len(row) >= 4 else 24.0
        height = float(row[4]) if len(row) >= 5 else 24.0
        out.append((float(row[0]), float(row[1]), score, width, height))
    return out


def _legacy_rescues_allowed(
    frame_shape: Sequence[int] | None,
    *,
    min_board_width: int,
) -> bool:
    if frame_shape is None or len(frame_shape) < 2:
        return True
    return int(frame_shape[1]) >= int(min_board_width)


def _expected_background_by_frame(
    family_pool: Any,
    frames: Sequence[int],
) -> Mapping[int, Sequence[tuple[int, Sequence[float]]]]:
    getter = getattr(family_pool, "expected_background_by_frame", None)
    if not callable(getter):
        return {}
    expected = getter(frames)
    if not isinstance(expected, Mapping):
        return {}
    return expected


def _limit_candidates(candidates: Sequence[CandidateRow], limit: int) -> list[CandidateRow]:
    return sorted(candidates, key=lambda row: row[2], reverse=True)[:limit]


def _anchors_from_live_family(live_decision: LiveFamilyDecision) -> dict[str, Point]:
    return {
        str(name): (float(point[0]), float(point[1]))
        for name, point in live_decision.points.items()
    }


def _selector_point(record: object) -> Point | None:
    if not isinstance(record, Mapping) or not bool(record.get("available", False)):
        return None
    return _point(record.get("point"))


def _allowed_rescue_point(record: object) -> Point | None:
    if not isinstance(record, Mapping) or not bool(record.get("available", False)):
        return None
    if bool(record.get("rescue_allowed", False)):
        rescue = _point(record.get("rescue_point"))
        if rescue is not None:
            return rescue
    if bool(record.get("consensus_rescue_allowed", False)):
        return _point(record.get("consensus_rescue_point"))
    return None


def _point(value: object) -> Point | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _debug_payload(
    live_decision: LiveFamilyDecision,
    selector_record: object,
    *,
    shape_point: Point | None,
    beam_point: Point | None,
    beam_debug: object,
    wide_beam_points: Sequence[Point],
    wide_beam_debug: object,
    explorer_beam_points: Sequence[Point],
    explorer_beam_debug: object,
) -> dict[str, object]:
    return {
        "live_family": dict(live_decision.debug),
        "selector_available": bool(
            isinstance(selector_record, Mapping) and selector_record.get("available", False)
        ),
        "kinematic_shape_point": shape_point,
        "kinematic_beam_point": beam_point,
        "kinematic_beam_debug": dict(beam_debug) if isinstance(beam_debug, Mapping) else {},
        "kinematic_wide_beam_points": tuple(wide_beam_points),
        "kinematic_wide_beam_debug": (
            dict(wide_beam_debug) if isinstance(wide_beam_debug, Mapping) else {}
        ),
        "kinematic_explorer_beam_points": tuple(explorer_beam_points),
        "kinematic_explorer_beam_debug": (
            dict(explorer_beam_debug) if isinstance(explorer_beam_debug, Mapping) else {}
        ),
    }
