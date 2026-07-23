# 지속되는 예측 경로에서 독립 심판의 순증거 합의를 관리합니다.
from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import hypot, log
from statistics import median

from core.puzzle.models import Candidate, CandidateEvidence


Point = tuple[float, float]
SUPPORT_GROUPS = (
    "background_motion",
    "local_rigid",
    "texture_background",
    "anchor_shape_identity",
)


class PersistentEvidenceQuorum:
    def __init__(
        self,
        *,
        required_groups: int = 3,
        required_observations: int = 3,
        max_prediction_error_scales: float = 1.5,
        required_positive_groups: Sequence[str] = (),
    ) -> None:
        self.required_groups = max(1, int(required_groups))
        self.required_observations = max(1, int(required_observations))
        self.max_prediction_error_scales = max(0.1, float(max_prediction_error_scales))
        self.required_positive_groups = tuple(
            str(group) for group in required_positive_groups if str(group) in SUPPORT_GROUPS
        )
        self.reset()

    def reset(self) -> None:
        self._path_points: list[Point] = []
        self._latest_margins: dict[str, float] = {}
        self._observations = 0

    def update(
        self,
        *,
        incumbent_point: Sequence[float] | None,
        challenger_point: Sequence[float] | None,
        stable_scale_px: float,
        group_margins: Mapping[str, float | None],
        protect_incumbent: bool = False,
    ) -> tuple[Point | None, dict[str, object]]:
        incumbent = _point(incumbent_point)
        challenger = _point(challenger_point)
        if protect_incumbent and incumbent is not None:
            self.reset()
            return incumbent, self._debug("protected_incumbent", incumbent, challenger, 0.0, None)
        if challenger is None:
            self.reset()
            return incumbent, self._debug("challenger_missing", incumbent, challenger, 0.0, None)
        if incumbent is None:
            self.reset()
            return challenger, self._debug("incumbent_missing", incumbent, challenger, 0.0, None)
        if not any(group_margins.get(group) is not None for group in SUPPORT_GROUPS):
            self.reset()
            return incumbent, self._debug("support_missing", incumbent, challenger, 0.0, None)

        scale = max(1.0, float(stable_scale_px))
        prediction_error = self._prediction_error(challenger, scale)
        path_reset = prediction_error is not None and prediction_error > self.max_prediction_error_scales
        if path_reset:
            self.reset()

        observed = {
            str(group): float(value)
            for group, value in group_margins.items()
            if value is not None and (group in SUPPORT_GROUPS or group == "yolo_penalty")
        }
        for group, value in observed.items():
            self._latest_margins[group] = value
        current_net_margin = sum(observed.values())
        self._observations += 1
        self._path_points.append(challenger)
        if len(self._path_points) > 2:
            del self._path_points[0]

        positive_groups = self._positive_groups()
        if path_reset:
            reason = "path_reset"
        elif not all(
            group_margins.get(group) is not None
            and float(group_margins[group]) > 0.0
            for group in self.required_positive_groups
        ):
            reason = "required_support_rejected"
        elif len(positive_groups) < self.required_groups:
            reason = "quorum_pending"
        elif self._observations < self.required_observations:
            reason = "persistence_pending"
        elif current_net_margin <= 0.0:
            reason = "current_evidence_rejected"
        else:
            reason = "persistent_quorum_confirmed"
        selected = reason == "persistent_quorum_confirmed"
        return (challenger if selected else incumbent), self._debug(
            reason,
            incumbent,
            challenger,
            current_net_margin,
            prediction_error,
        )

    def _prediction_error(self, challenger: Point, scale: float) -> float | None:
        if not self._path_points:
            return None
        predicted = self._path_points[-1]
        if len(self._path_points) == 2:
            previous, latest = self._path_points
            predicted = (latest[0] * 2.0 - previous[0], latest[1] * 2.0 - previous[1])
        return hypot(predicted[0] - challenger[0], predicted[1] - challenger[1]) / scale

    def _positive_groups(self) -> tuple[str, ...]:
        return tuple(group for group in SUPPORT_GROUPS if self._latest_margins.get(group, 0.0) > 0.0)

    def _debug(
        self,
        reason: str,
        incumbent: Point | None,
        challenger: Point | None,
        current_net_margin: float,
        prediction_error: float | None,
    ) -> dict[str, object]:
        return {
            "reason": reason,
            "selected": reason == "persistent_quorum_confirmed",
            "incumbent_point": incumbent,
            "challenger_point": challenger,
            "observation_count": self._observations,
            "current_net_margin": current_net_margin,
            "prediction_error_scales": prediction_error,
            "positive_groups": self._positive_groups(),
            "latest_group_margins": dict(self._latest_margins),
        }


def pairwise_persistent_margins(
    *,
    incumbent_candidate: Candidate,
    challenger_candidate: Candidate,
    incumbent_evidence: CandidateEvidence,
    challenger_evidence: CandidateEvidence,
    candidate_pool: Sequence[Candidate],
    anchor_shape: tuple[float, float] | None = None,
    frame_shape: tuple[int, int] | None = None,
) -> dict[str, float | None]:
    if (
        _touches_frame_boundary(incumbent_candidate, frame_shape)
        or _touches_frame_boundary(challenger_candidate, frame_shape)
    ):
        return {
            "background_motion": None,
            "local_rigid": None,
            "texture_background": None,
            "anchor_shape_identity": None,
            "yolo_penalty": 0.0,
        }
    motion_pairs = (
        (float(incumbent_evidence.motion_divergence), float(challenger_evidence.motion_divergence)),
        (float(incumbent_evidence.rigid_violation), float(challenger_evidence.rigid_violation)),
    )
    available_motion = [pair for pair in motion_pairs if pair != (0.0, 0.0)]
    background_motion = (
        sum(challenger - incumbent for incumbent, challenger in available_motion) / len(available_motion)
        if available_motion else None
    )
    local_pair = (
        float(incumbent_evidence.local_rigid_residual),
        float(challenger_evidence.local_rigid_residual),
    )
    local_rigid = local_pair[1] - local_pair[0] if local_pair != (0.0, 0.0) else None
    texture_pair = (
        float(incumbent_evidence.texture_bg_score),
        float(challenger_evidence.texture_bg_score),
    )
    texture_background = texture_pair[0] - texture_pair[1] if texture_pair != (0.0, 0.0) else None

    scores = [float(candidate.score) for candidate in candidate_pool]
    yolo_penalty = 0.0
    if scores:
        relative_floor = min(float(incumbent_candidate.score), float(median(scores)))
        score_span = max(scores) - min(scores)
        if float(challenger_candidate.score) < relative_floor:
            yolo_penalty = -min(
                1.0,
                (relative_floor - float(challenger_candidate.score)) / max(0.1, score_span),
            )
    anchor_shape_identity = None
    if (
        anchor_shape is not None
        and not _touches_frame_boundary(incumbent_candidate, frame_shape)
        and not _touches_frame_boundary(challenger_candidate, frame_shape)
    ):
        incumbent_distance = _shape_distance(incumbent_candidate, anchor_shape)
        challenger_distance = _shape_distance(challenger_candidate, anchor_shape)
        anchor_shape_identity = incumbent_distance - challenger_distance
    return {
        "background_motion": background_motion,
        "local_rigid": local_rigid,
        "texture_background": texture_background,
        "anchor_shape_identity": anchor_shape_identity,
        "yolo_penalty": yolo_penalty,
    }


def _shape_distance(candidate: Candidate, anchor_shape: tuple[float, float]) -> float:
    x1, y1, x2, y2 = candidate.bbox
    width = max(1.0, float(x2) - float(x1))
    height = max(1.0, float(y2) - float(y1))
    area = width * height
    aspect = width / height
    anchor_area = max(1.0, float(anchor_shape[0]))
    anchor_aspect = max(1e-6, float(anchor_shape[1]))
    return abs(log(area / anchor_area)) + abs(log(aspect / anchor_aspect))


def _touches_frame_boundary(
    candidate: Candidate,
    frame_shape: tuple[int, int] | None,
) -> bool:
    if frame_shape is None:
        return False
    frame_height, frame_width = frame_shape
    x1, y1, x2, y2 = candidate.bbox
    return x1 <= 0.0 or y1 <= 0.0 or x2 >= frame_width or y2 >= frame_height


def _point(value: Sequence[float] | None) -> Point | None:
    if value is None or len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None
