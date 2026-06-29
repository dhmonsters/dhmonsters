# 투명도형 라이브 세션 trace를 첫 테스트용 요약 리포트로 정리한다.
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LiveSessionReviewSummary:
    frames: int = 0
    mouse_enabled: bool | None = None
    puzzle_activated: bool = False
    activation_reason: str = "-"
    temporal_selector_events: int = 0
    mouse_events: int = 0
    mouse_moved: int = 0
    mouse_disabled: int = 0
    mouse_reasons: dict[str, int] = field(default_factory=dict)
    selector_sources: dict[str, int] = field(default_factory=dict)
    selector_families: dict[str, int] = field(default_factory=dict)


class LiveSessionReviewBuilder:
    def build(self, trace_path: str | Path, output_path: str | Path) -> LiveSessionReviewSummary:
        trace = Path(trace_path)
        output = Path(output_path)
        events = list(_read_events(trace))
        summary = _summarize(events)
        output.write_text(_format_markdown(summary, trace_path=trace), encoding="utf-8")
        return summary


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    return events


def _summarize(events: list[dict[str, Any]]) -> LiveSessionReviewSummary:
    mouse_enabled: bool | None = None
    puzzle_activated = False
    activation_reason = "-"
    frames = 0
    temporal_selector_events = 0
    mouse_events = 0
    mouse_moved = 0
    mouse_disabled = 0
    mouse_reasons: Counter[str] = Counter()
    selector_sources: Counter[str] = Counter()
    selector_families: Counter[str] = Counter()

    for event in events:
        event_type = str(event.get("type") or "")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        if event_type == "SESSION_START" and "mouse_enabled" in payload:
            mouse_enabled = bool(payload.get("mouse_enabled"))
        elif event_type == "PUZZLE_ACTIVATED":
            puzzle_activated = True
            activation_reason = str(payload.get("reason") or "-")
        elif event_type == "FRAME_RECORDED":
            frames += 1
        elif event_type == "TEMPORAL_SELECTOR":
            temporal_selector_events += 1
            source = str(payload.get("source") or "-")
            family = str(payload.get("family") or "-")
            selector_sources[source] += 1
            selector_families[family] += 1
        elif event_type == "MOUSE_MOVE":
            mouse_events += 1
            reason = str(payload.get("reason") or "-")
            mouse_reasons[reason] += 1
            if bool(payload.get("moved", False)):
                mouse_moved += 1
            if reason == "disabled":
                mouse_disabled += 1

    return LiveSessionReviewSummary(
        frames=frames,
        mouse_enabled=mouse_enabled,
        puzzle_activated=puzzle_activated,
        activation_reason=activation_reason,
        temporal_selector_events=temporal_selector_events,
        mouse_events=mouse_events,
        mouse_moved=mouse_moved,
        mouse_disabled=mouse_disabled,
        mouse_reasons=dict(mouse_reasons),
        selector_sources=dict(selector_sources),
        selector_families=dict(selector_families),
    )


def _format_markdown(summary: LiveSessionReviewSummary, *, trace_path: Path) -> str:
    return "\n".join(
        [
            "# Live Session Review",
            "",
            f"- trace: {trace_path.name}",
            f"- frames: {summary.frames}",
            f"- mouse_enabled: {_bool_text(summary.mouse_enabled)}",
            f"- puzzle_activated: {_bool_text(summary.puzzle_activated)}",
            f"- activation_reason: {summary.activation_reason}",
            f"- temporal_selector_events: {summary.temporal_selector_events}",
            f"- mouse_events: {summary.mouse_events}",
            f"- mouse_moved: {summary.mouse_moved}",
            f"- mouse_disabled: {summary.mouse_disabled}",
            "",
            "## Mouse Reasons",
            "",
            *_counter_lines(summary.mouse_reasons),
            "",
            "## Selector Sources",
            "",
            *_counter_lines(summary.selector_sources),
            "",
            "## Selector Families",
            "",
            *_counter_lines(summary.selector_families),
            "",
        ]
    )


def _counter_lines(values: dict[str, int]) -> list[str]:
    if not values:
        return ["- -: 0"]
    return [f"- {name}: {count}" for name, count in sorted(values.items())]


def _bool_text(value: bool | None) -> str:
    if value is None:
        return "unknown"
    return "true" if value else "false"
