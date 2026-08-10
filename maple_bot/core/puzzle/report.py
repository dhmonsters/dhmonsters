# 투명도형 퍼즐 trace를 사람이 읽을 수 있는 세션 리포트로 요약한다.
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from core.puzzle.models import PuzzleSession


class ReportBuilder:
    def build(self, session: PuzzleSession, trace_path: Path) -> Path:
        events = _read_events(trace_path)
        summary = _summarize(events)
        report_path = session.output_dir / "report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(_render_report(session, trace_path, summary), encoding="utf-8")
        return report_path


def _read_events(trace_path: Path) -> list[dict[str, Any]]:
    if not trace_path.exists():
        return []

    events: list[dict[str, Any]] = []
    with trace_path.open("r", encoding="utf-8") as fp:
        for line in fp:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
    return events


def _summarize(events: list[dict[str, Any]]) -> dict[str, object]:
    state_counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    max_frame_index = -1
    frames_from_end = 0
    merge_count = 0
    hold_count = 0
    reacquire_count = 0

    for event in events:
        event_type = str(event.get("type") or "")
        if event_type:
            event_counts[event_type] += 1

        frame_index = event.get("frame_index")
        if isinstance(frame_index, int):
            max_frame_index = max(max_frame_index, frame_index)

        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        if event_type == "SESSION_END":
            frames = payload.get("frames")
            if isinstance(frames, int):
                frames_from_end = max(frames_from_end, frames)

        state = _state_from(event_type, payload)
        if state:
            state_counts[state] += 1

        if _is_merge_event(event_type, state, payload):
            merge_count += 1
        if _is_hold_event(event_type, state, payload):
            hold_count += 1
        if state == "REACQUIRE" or event_type == "REACQUIRE":
            reacquire_count += 1

    return {
        "event_count": len(events),
        "frames": max(frames_from_end, max_frame_index + 1),
        "event_counts": dict(sorted(event_counts.items())),
        "state_counts": dict(sorted(state_counts.items())),
        "merge_count": merge_count,
        "hold_count": hold_count,
        "reacquire_count": reacquire_count,
    }


def _state_from(event_type: str, payload: dict[str, Any]) -> str:
    for key in ("state", "identity_state"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    if event_type in {
        "INIT_VISIBLE",
        "TRACK_CONFIDENT",
        "OCCLUSION_SUSPECTED",
        "IDENTITY_HOLD",
        "REACQUIRE",
        "LOST",
    }:
        return event_type
    return ""


def _is_merge_event(event_type: str, state: str, payload: dict[str, Any]) -> bool:
    if event_type in {"MERGE", "MERGED_BLOB"} or state == "OCCLUSION_SUSPECTED":
        return True
    likelihood = payload.get("merge_likelihood")
    return isinstance(likelihood, (int, float)) and likelihood > 0


def _is_hold_event(event_type: str, state: str, payload: dict[str, Any]) -> bool:
    if event_type == "IDENTITY_HOLD" or state == "IDENTITY_HOLD":
        return True
    hold_frames = payload.get("hold_frames")
    return isinstance(hold_frames, int) and hold_frames > 0


def _render_report(session: PuzzleSession, trace_path: Path, summary: dict[str, object]) -> str:
    lines = [
        "# 투명도형 퍼즐 세션 리포트",
        "",
        "## Session",
        f"session_id: {session.session_id}",
        f"started_at: {session.started_at}",
        f"source_kind: {session.source_kind}",
        "",
        "## Summary",
        f"event_count: {summary['event_count']}",
        f"frames: {summary['frames']}",
        f"merge_count: {summary['merge_count']}",
        f"hold_count: {summary['hold_count']}",
        f"reacquire_count: {summary['reacquire_count']}",
        "",
        "## State Counts",
    ]

    state_counts = summary["state_counts"]
    if isinstance(state_counts, dict) and state_counts:
        lines.extend(f"{name}: {count}" for name, count in state_counts.items())
    else:
        lines.append("none")

    lines.extend(
        [
            "",
            "## Event Counts",
        ]
    )
    event_counts = summary["event_counts"]
    if isinstance(event_counts, dict) and event_counts:
        lines.extend(f"{name}: {count}" for name, count in event_counts.items())
    else:
        lines.append("none")

    lines.extend(
        [
            "",
            "## Artifacts",
            f"raw_video: {session.raw_video_path}",
            f"board_video: {session.board_video_path}",
            f"overlay_video: {session.overlay_video_path}",
            f"trace: {trace_path}",
        ]
    )
    return "\n".join(lines) + "\n"
