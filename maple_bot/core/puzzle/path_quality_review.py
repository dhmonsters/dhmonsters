# trace 이벤트를 모아 표적 경로 품질과 위험 프레임을 진단한다.
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from math import hypot
from pathlib import Path
from typing import Any


UNSTABLE_IDENTITY_STATES = frozenset({"IDENTITY_HOLD", "IDENTITY_LOST", "OCCLUSION_SUSPECTED"})


@dataclass(frozen=True)
class PathQualityFrame:
    frame_index: int
    status: str
    target_point: tuple[float, float] | None = None
    jump_px: float | None = None
    candidate_count: int | None = None
    identity_state: str = "-"
    identity_reason: str = "-"
    identity_confidence: float | None = None
    target_source: str = "-"
    target_reason: str = "-"
    identity_temporal_distance: float | None = None
    temporal_family: str = "-"
    mouse_reason: str = "-"
    risk_flags: list[str] = field(default_factory=list)
    problem: str = "-"
    suggested_fix: str = "-"


@dataclass(frozen=True)
class PathQualitySummary:
    total_frames: int = 0
    stable_frames: int = 0
    risky_frames: int = 0
    max_jump_px: float = 0.0
    has_ground_truth: bool = False
    verdict: str = "정답 없음: 내부 신호 기준 진단"


@dataclass(frozen=True)
class PathQualityReview:
    summary: PathQualitySummary
    frames: list[PathQualityFrame]
    problem_counts: dict[str, int]
    suggestions: list[dict[str, object]]


class PathQualityReviewBuilder:
    def __init__(
        self,
        *,
        target_jump_px: float = 120.0,
        low_confidence: float = 0.35,
        divergence_px: float = 80.0,
    ) -> None:
        self.target_jump_px = float(target_jump_px)
        self.low_confidence = float(low_confidence)
        self.divergence_px = float(divergence_px)

    def build(self, trace_path: str | Path) -> PathQualityReview:
        frame_states = _collect_frame_states(Path(trace_path))
        frames = self._build_frames(frame_states)
        problem_counts = Counter(flag for frame in frames for flag in frame.risk_flags)
        max_jump = max((frame.jump_px or 0.0 for frame in frames), default=0.0)
        risky_frames = sum(1 for frame in frames if frame.risk_flags)
        summary = PathQualitySummary(
            total_frames=len(frames),
            stable_frames=max(0, len(frames) - risky_frames),
            risky_frames=risky_frames,
            max_jump_px=max_jump,
        )
        return PathQualityReview(
            summary=summary,
            frames=frames,
            problem_counts=dict(problem_counts),
            suggestions=_suggestions_from_counts(problem_counts),
        )

    def _build_frames(self, frame_states: dict[int, dict[str, Any]]) -> list[PathQualityFrame]:
        frames: list[PathQualityFrame] = []
        previous_point: tuple[float, float] | None = None
        for frame_index in sorted(frame_states):
            state = frame_states[frame_index]
            target_point = _point_tuple(state.get("target_point"))
            jump_px = _point_distance(previous_point, target_point)
            if target_point is not None:
                previous_point = target_point
            risk_flags = _risk_flags(
                state,
                target_point=target_point,
                jump_px=jump_px,
                target_jump_px=self.target_jump_px,
                low_confidence=self.low_confidence,
                divergence_px=self.divergence_px,
            )
            problem = _problem_text(risk_flags)
            suggested_fix = _suggested_fix_text(risk_flags)
            frames.append(
                PathQualityFrame(
                    frame_index=frame_index,
                    status="확인 필요" if risk_flags else "안정 추정",
                    target_point=target_point,
                    jump_px=jump_px,
                    candidate_count=_optional_int(state.get("candidate_count")),
                    identity_state=str(state.get("identity_state") or "-"),
                    identity_reason=str(state.get("identity_reason") or "-"),
                    identity_confidence=_optional_float(state.get("identity_confidence")),
                    target_source=str(state.get("target_source") or "-"),
                    target_reason=str(state.get("target_reason") or "-"),
                    identity_temporal_distance=_optional_float(state.get("identity_temporal_distance")),
                    temporal_family=str(state.get("temporal_family") or "-"),
                    mouse_reason=str(state.get("mouse_reason") or "-"),
                    risk_flags=risk_flags,
                    problem=problem,
                    suggested_fix=suggested_fix,
                )
            )
        return frames


def _collect_frame_states(trace_path: Path) -> dict[int, dict[str, Any]]:
    states: dict[int, dict[str, Any]] = {}
    for event in _read_events(trace_path):
        frame_index = _optional_int(event.get("frame_index"))
        if frame_index is None:
            continue
        state = states.setdefault(frame_index, {"frame_index": frame_index})
        event_type = str(event.get("type") or "")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        if event_type == "CANDIDATES":
            state["candidate_count"] = _optional_int(payload.get("count"))
        elif event_type == "IDENTITY_STATE":
            state["identity_state"] = str(payload.get("state") or "-")
            state["identity_reason"] = str(payload.get("reason") or "-")
            state["identity_confidence"] = _optional_float(payload.get("confidence"))
            state["identity_point"] = _point_tuple(payload.get("point"))
        elif event_type == "TEMPORAL_SELECTOR":
            state["temporal_point"] = _point_tuple(payload.get("point"))
            state["temporal_family"] = str(payload.get("family") or "-")
            state["temporal_reason"] = str(payload.get("reason") or "-")
        elif event_type == "TARGET_SELECTION":
            state["target_point"] = _point_tuple(payload.get("point"))
            state["target_source"] = str(payload.get("source") or "-")
            state["target_reason"] = str(payload.get("reason") or "-")
            state["identity_temporal_distance"] = _optional_float(payload.get("distance"))
            state["temporal_family"] = str(payload.get("temporal_family") or state.get("temporal_family") or "-")
        elif event_type == "MOUSE_MOVE":
            state["mouse_reason"] = str(payload.get("reason") or "-")
    return states


def _read_events(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                yield event


def _risk_flags(
    state: dict[str, Any],
    *,
    target_point: tuple[float, float] | None,
    jump_px: float | None,
    target_jump_px: float,
    low_confidence: float,
    divergence_px: float,
) -> list[str]:
    flags: list[str] = []
    candidate_count = _optional_int(state.get("candidate_count"))
    identity_confidence = _optional_float(state.get("identity_confidence"))
    identity_distance = _optional_float(state.get("identity_temporal_distance"))
    identity_state = str(state.get("identity_state") or "")
    if candidate_count == 0:
        flags.append("no_candidates")
    if target_point is None:
        flags.append("no_target")
    if jump_px is not None and jump_px > target_jump_px:
        flags.append("target_jump")
    if identity_confidence is not None and identity_confidence < low_confidence:
        flags.append("low_identity_confidence")
    if identity_distance is not None and identity_distance > divergence_px:
        flags.append("identity_temporal_diverged")
    if identity_state in UNSTABLE_IDENTITY_STATES:
        flags.append("identity_unstable_state")
    return flags


def _problem_text(flags: list[str]) -> str:
    if not flags:
        return "큰 위험 신호 없음"
    labels = {
        "no_candidates": "검출 후보가 없어 표적 복원이 불안정함",
        "no_target": "선택 표적점이 없음",
        "target_jump": "표적점이 이전 프레임 대비 크게 튐",
        "low_identity_confidence": "identity 신뢰도가 낮음",
        "identity_temporal_diverged": "identity와 temporal 선택이 크게 갈라짐",
        "identity_unstable_state": "identity가 hold/lost/occlusion 상태임",
    }
    return " / ".join(labels.get(flag, flag) for flag in flags)


def _suggested_fix_text(flags: list[str]) -> str:
    if not flags:
        return "현재 기준에서는 추가 조치보다 시각 확인만 필요"
    if "no_candidates" in flags or "no_target" in flags:
        return "ROI와 검출 로그를 먼저 확인하고, 해당 프레임의 원본/3D 미리보기에서 후보가 사라진 이유를 확인"
    if "target_jump" in flags:
        return "점프 직전/직후 프레임을 북마크하고, 선택 경로와 후보 번호가 바뀐 지점을 비교"
    if "identity_temporal_diverged" in flags:
        return "identity 점과 temporal 점을 같은 프레임에서 비교하고, 어떤 후보가 PICK/CHECK/DROP인지 확인"
    if "low_identity_confidence" in flags or "identity_unstable_state" in flags:
        return "겹침/분리 구간으로 보고 후보별 evidence와 선택 이력 패널을 같이 확인"
    return "위험 신호 조합을 기준으로 해당 프레임 주변을 수동 검토"


def _suggestions_from_counts(problem_counts: Counter[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for flag, count in problem_counts.most_common():
        rows.append(
            {
                "problem_code": flag,
                "count": int(count),
                "problem": _problem_text([flag]),
                "suggested_fix": _suggested_fix_text([flag]),
            }
        )
    return rows


def _point_tuple(value: object) -> tuple[float, float] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (float(value[0]), float(value[1]))
    return None


def _point_distance(a: tuple[float, float] | None, b: tuple[float, float] | None) -> float | None:
    if a is None or b is None:
        return None
    return hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
