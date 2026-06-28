# 라이브 투명도형 시간축 selector를 퍼즐 런타임에서 쓰기 쉽게 묶습니다.
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from core.vision.transparent_family_selector_runtime import TransparentFamilySelectorRuntime
from core.vision.transparent_live_family_pool import LiveFamilyDecision, TransparentLiveFamilyPool
from core.vision.transparent_selector_shadow import TransparentSelectorShadow
from core.vision.transparent_track_health import TrackHealthDecision, TransparentTrackHealthSelector


Point = tuple[float, float]
CandidateRow = tuple[float, float, float, float, float]


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
        clip_id: str = "live",
        window: int = 24,
        min_frames: int = 8,
        live_max_candidates: int = 24,
        include_local_box: bool = False,
        use_expected_background: bool = False,
    ) -> None:
        self.runtime = runtime or TransparentFamilySelectorRuntime()
        self.family_pool = family_pool or TransparentLiveFamilyPool(
            window=window,
            min_frames=min_frames,
            enable_bg_mht=False,
            enable_raw_mht=False,
            enable_phase_mht=False,
            enable_guarded_decal_identity=True,
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
        self.live_max_candidates = max(1, int(live_max_candidates))
        self.use_expected_background = bool(use_expected_background)
        self._seeded = False

    def reset(self, *, point: Point | None = None) -> None:
        if hasattr(self.family_pool, "reset"):
            self.family_pool.reset()
        if hasattr(self.selector_shadow, "reset"):
            self.selector_shadow.reset(clip_id="live")
        self.health_selector.reset(point)
        self._seeded = point is not None

    def update(
        self,
        *,
        frame_index: int,
        candidates: Sequence[Sequence[float]],
        primary_point: Sequence[float] | None,
        white_anchor: Sequence[float] | None = None,
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
                debug=_debug_payload(live_decision, selector_record),
            )
        return LiveTemporalDecision(
            point=health.point,
            source=health.source,
            reason=health.reason,
            selector_record=selector_record,
            live_family_points=anchors,
            health=health,
            debug=_debug_payload(live_decision, selector_record),
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


def _debug_payload(live_decision: LiveFamilyDecision, selector_record: object) -> dict[str, object]:
    return {
        "live_family": dict(live_decision.debug),
        "selector_available": bool(
            isinstance(selector_record, Mapping) and selector_record.get("available", False)
        ),
    }
