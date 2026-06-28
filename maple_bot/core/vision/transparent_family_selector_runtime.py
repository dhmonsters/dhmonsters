# 저장된 GT-free family selector 모델을 라이브 런타임에서 사용합니다.
from __future__ import annotations

from pathlib import Path
from typing import Dict, Mapping, Sequence

from _gt_free_family_selector import (
    load_gt_free_selector_model,
    select_gt_free_family_rows,
)
from core.vision.transparent_feature_rows import build_transparent_feature_rows

box_switch_variant_paths = None
event_gate_shortlist_paths = None
gap_fill_variant_paths = None
occlusion_variant_paths = None
select_identity_family = None


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_PATH = ROOT / "models" / "transparent" / "gt_free_family_selector_v1.json"
GT_SCORE_LABELS = frozenset({"success", "mean", "max", "coverage"})


def strip_gt_score_labels(row: Mapping[str, object]) -> dict:
    return {
        str(key): value
        for key, value in row.items()
        if str(key) not in GT_SCORE_LABELS
    }


class TransparentFamilySelectorRuntime:
    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
        *,
        use_judge_scoreboard: bool = True,
    ):
        self.model_path = Path(model_path)
        self.use_judge_scoreboard = bool(use_judge_scoreboard)
        self._model = None
        self._load_error = ""
        self._load()

    @property
    def available(self) -> bool:
        return self._model is not None

    @property
    def load_error(self) -> str:
        return self._load_error

    def select(self, rows: Sequence[Mapping[str, object]]) -> Dict[object, dict]:
        if self._model is None:
            return {}
        runtime_rows = [strip_gt_score_labels(row) for row in rows]
        return select_gt_free_family_rows(runtime_rows, self._model)

    def select_from_path_pool(
        self,
        clip: str,
        paths,
        frames,
        **kwargs,
    ) -> tuple[Dict[object, dict], list[dict]]:
        anchor_points = kwargs.pop("anchor_points", None)
        expected_by_frame = kwargs.pop("expected_by_frame", None)
        candidate_sets = kwargs.get("candidate_sets")
        scoreboard = self._select_scoreboard_family(
            clip,
            paths,
            frames,
            candidate_sets=candidate_sets,
            expected_by_frame=expected_by_frame,
            anchor_points=anchor_points,
        )
        if scoreboard:
            return {clip: scoreboard}, [scoreboard]
        rows = build_transparent_feature_rows(
            clip,
            paths,
            frames,
            **kwargs,
        )
        selected = self.select(rows)
        if scoreboard:
            selected = dict(selected)
            selected[clip] = scoreboard
        return selected, rows

    def _select_scoreboard_family(
        self,
        clip: str,
        paths,
        frames,
        *,
        candidate_sets=None,
        expected_by_frame=None,
        anchor_points=None,
    ) -> dict | None:
        if not self.use_judge_scoreboard or not candidate_sets:
            return None
        helpers = _load_scoreboard_helpers()
        if helpers is None:
            return None
        path_pool = _scoreboard_path_pool(
            paths,
            frames,
            candidate_sets=candidate_sets,
            expected_by_frame=expected_by_frame,
        )
        anchors = anchor_points or _default_anchor_points(path_pool)
        selection = helpers["select_identity_family"](
            path_pool,
            frames=frames,
            anchor_points=anchors,
            expected_by_frame=expected_by_frame,
            candidate_sets=candidate_sets,
            judge_scoreboard_mode="rescue",
        )
        family = str(selection.get("family", ""))
        if not family:
            return None
        scores = selection.get("scores", {})
        row = {
            "clip": clip,
            "family": family,
            "selector": str(selection.get("judge", "judge_scoreboard")),
            "rank_center": 0.0,
            "rank_rough": 0.0,
            "judge_total_score": float(selection.get("score", 0.0) or 0.0),
            "judge_scores": dict(scores) if isinstance(scores, Mapping) else {},
        }
        point = _latest_point(path_pool.get(family, {}), frames)
        if point is not None:
            serial_point = [float(point[0]), float(point[1])]
            row["point"] = serial_point
            row["rescue_point"] = serial_point
        return row

    def _load(self) -> None:
        try:
            if not self.model_path.exists():
                self._load_error = f"missing model: {self.model_path}"
                return
            self._model = load_gt_free_selector_model(self.model_path)
            self._load_error = ""
        except Exception as exc:
            self._model = None
            self._load_error = str(exc)


def _load_scoreboard_helpers() -> dict[str, object] | None:
    global box_switch_variant_paths
    global event_gate_shortlist_paths
    global gap_fill_variant_paths
    global occlusion_variant_paths
    global select_identity_family

    if select_identity_family is not None:
        return {
            "box_switch_variant_paths": box_switch_variant_paths,
            "event_gate_shortlist_paths": event_gate_shortlist_paths,
            "gap_fill_variant_paths": gap_fill_variant_paths,
            "occlusion_variant_paths": occlusion_variant_paths,
            "select_identity_family": select_identity_family,
        }
    try:
        from _live_family_pool_gt_score import (
            box_switch_variant_paths as loaded_box_switch_variant_paths,
            event_gate_shortlist_paths as loaded_event_gate_shortlist_paths,
            gap_fill_variant_paths as loaded_gap_fill_variant_paths,
            occlusion_variant_paths as loaded_occlusion_variant_paths,
            select_identity_family as loaded_select_identity_family,
        )
    except Exception:
        return None

    box_switch_variant_paths = loaded_box_switch_variant_paths
    event_gate_shortlist_paths = loaded_event_gate_shortlist_paths
    gap_fill_variant_paths = loaded_gap_fill_variant_paths
    occlusion_variant_paths = loaded_occlusion_variant_paths
    select_identity_family = loaded_select_identity_family
    return {
        "box_switch_variant_paths": box_switch_variant_paths,
        "event_gate_shortlist_paths": event_gate_shortlist_paths,
        "gap_fill_variant_paths": gap_fill_variant_paths,
        "occlusion_variant_paths": occlusion_variant_paths,
        "select_identity_family": select_identity_family,
    }


def _scoreboard_path_pool(
    paths,
    frames,
    *,
    candidate_sets=None,
    expected_by_frame=None,
) -> dict:
    path_pool = {str(family): dict(path) for family, path in dict(paths).items()}
    if gap_fill_variant_paths is not None:
        path_pool.update(gap_fill_variant_paths(path_pool, frames=frames))
    if (
        occlusion_variant_paths is not None
        and expected_by_frame
        and candidate_sets
    ):
        path_pool.update(occlusion_variant_paths(
            path_pool,
            frames=frames,
            expected_by_frame=expected_by_frame,
            candidate_sets=candidate_sets,
        ))
    if box_switch_variant_paths is not None:
        path_pool.update(box_switch_variant_paths(path_pool, frames=frames))
    if event_gate_shortlist_paths is not None:
        path_pool = event_gate_shortlist_paths(path_pool)
    return path_pool


def _default_anchor_points(paths: Mapping[str, Mapping[int, Sequence[float]]]) -> Mapping[int, tuple[float, float]] | None:
    for family in (
        "panel_default_center_mild_state_mild",
        "balanced_viterbi_center_mild_state_mild",
    ):
        path = paths.get(family)
        if path:
            return {
                int(frame): (float(point[0]), float(point[1]))
                for frame, point in path.items()
            }
    return None


def _latest_point(path: Mapping[int, Sequence[float]], frames: Sequence[int]) -> tuple[float, float] | None:
    for frame in reversed(frames):
        point = path.get(int(frame))
        if point is not None and len(point) >= 2:
            return (float(point[0]), float(point[1]))
    return None
