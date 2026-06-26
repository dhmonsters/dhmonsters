# selector_shadow JSONL 로그에서 rescue 후보와 추적 차이를 요약하는 분석기입니다.
from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence


Point = tuple[float, float]


def _point(value: object) -> Point | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _dist(a: Point, b: Point) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _load_jsonl(path: Path) -> list[dict]:
    frames = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                frames.append(item)
    return frames


def _shadow_record(frame: Mapping[str, object]) -> Mapping[str, object] | None:
    record = frame.get("selector_shadow")
    if not isinstance(record, Mapping):
        return None
    return record


def _event(
    *,
    kind: str,
    frame: Mapping[str, object],
    track: Point | None,
    shadow: Point | None,
    distance: float | None,
    family: str,
) -> dict:
    return {
        "kind": kind,
        "frame": int(frame.get("i", -1) or -1),
        "family": family,
        "track": None if track is None else [round(track[0], 1), round(track[1], 1)],
        "shadow": None if shadow is None else [round(shadow[0], 1), round(shadow[1], 1)],
        "distance": None if distance is None else round(float(distance), 1),
    }


def analyze_record_file(
    path: str | Path,
    *,
    divergence_px: float = 30.0,
    jump_px: float = 40.0,
    max_events: int = 20,
) -> dict:
    source = Path(path)
    frames = _load_jsonl(source)
    families: Counter[str] = Counter()
    events = []
    shadow_frames = 0
    divergence_count = 0
    recovery_candidates = 0
    shadow_less_jumpy = 0
    rescue_allowed_frames = 0
    rescue_blocked_frames = 0
    bg_split_frames = 0
    selector_rescue_used = 0
    health_rescue_frames = 0
    max_divergence = 0.0
    prev_track: Point | None = None
    prev_shadow: Point | None = None

    for frame in frames:
        record = _shadow_record(frame)
        track = _point(frame.get("track"))
        shadow = None if record is None else _point(record.get("point"))
        if record is None:
            prev_track = track if track is not None else prev_track
            continue

        shadow_frames += 1
        family = str(record.get("family", ""))
        if family:
            families[family] += 1

        rescue_point = _point(record.get("rescue_point"))
        rescue_allowed = bool(record.get("rescue_allowed", False))
        is_bg_split = family.lower().startswith("bg_split_viterbi")
        if is_bg_split:
            bg_split_frames += 1
        if rescue_point is not None:
            if rescue_allowed:
                rescue_allowed_frames += 1
            else:
                rescue_blocked_frames += 1

        health = frame.get("health")
        if isinstance(health, Mapping) and health.get("source") == "rescue":
            health_rescue_frames += 1
        if frame.get("rescue_source") == "selector_shadow":
            selector_rescue_used += 1
            events.append({
                "kind": "selector_rescue_used",
                "frame": int(frame.get("i", -1) or -1),
                "family": family,
                "shadow": None if shadow is None else [round(shadow[0], 1), round(shadow[1], 1)],
                "rescue_point": (
                    None
                    if rescue_point is None
                    else [round(rescue_point[0], 1), round(rescue_point[1], 1)]
                ),
                "health_reason": (
                    str(health.get("reason", ""))
                    if isinstance(health, Mapping)
                    else ""
                ),
            })

        if shadow is not None and track is not None:
            distance = _dist(track, shadow)
            max_divergence = max(max_divergence, distance)
            if distance >= float(divergence_px):
                divergence_count += 1
                events.append(_event(
                    kind="divergence",
                    frame=frame,
                    track=track,
                    shadow=shadow,
                    distance=distance,
                    family=family,
                ))
        elif shadow is not None and track is None:
            recovery_candidates += 1
            events.append(_event(
                kind="recovery",
                frame=frame,
                track=None,
                shadow=shadow,
                distance=None,
                family=family,
            ))

        if (
            prev_track is not None
            and prev_shadow is not None
            and track is not None
            and shadow is not None
        ):
            track_jump = _dist(prev_track, track)
            shadow_jump = _dist(prev_shadow, shadow)
            if track_jump >= float(jump_px) and shadow_jump + 10.0 < track_jump:
                shadow_less_jumpy += 1
                events.append({
                    "kind": "shadow_less_jumpy",
                    "frame": int(frame.get("i", -1) or -1),
                    "family": family,
                    "track_jump": round(track_jump, 1),
                    "shadow_jump": round(shadow_jump, 1),
                    "track": [round(track[0], 1), round(track[1], 1)],
                    "shadow": [round(shadow[0], 1), round(shadow[1], 1)],
                })

        prev_track = track if track is not None else prev_track
        prev_shadow = shadow if shadow is not None else prev_shadow

    events = sorted(
        events,
        key=lambda item: (
            item.get("kind") != "divergence",
            item.get("kind") != "selector_rescue_used",
            -float(item.get("distance") or item.get("track_jump") or 0.0),
            int(item.get("frame", -1)),
        ),
    )[: max(0, int(max_events))]

    return {
        "name": source.name,
        "path": str(source),
        "frames": len(frames),
        "shadow_frames": shadow_frames,
        "divergence_count": divergence_count,
        "recovery_candidates": recovery_candidates,
        "shadow_less_jumpy": shadow_less_jumpy,
        "rescue_allowed_frames": rescue_allowed_frames,
        "rescue_blocked_frames": rescue_blocked_frames,
        "bg_split_frames": bg_split_frames,
        "selector_rescue_used": selector_rescue_used,
        "health_rescue_frames": health_rescue_frames,
        "max_divergence": round(max_divergence, 1),
        "families": dict(families),
        "events": events,
    }


def analyze_record_path(path: str | Path, **kwargs) -> list[dict]:
    source = Path(path)
    if source.is_file():
        summary = analyze_record_file(source, **kwargs)
        return [summary] if summary["shadow_frames"] else []

    summaries = []
    for jsonl_path in sorted(source.glob("*.jsonl")):
        summary = analyze_record_file(jsonl_path, **kwargs)
        if summary["shadow_frames"]:
            summaries.append(summary)
    return summaries


def write_markdown_report(summaries: Iterable[Mapping[str, object]], out_path: str | Path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    items = list(summaries)
    lines = [
        "# selector_shadow 분석 리포트",
        "",
    ]
    if not items:
        lines.extend([
            "selector_shadow 로그가 있는 파일이 없습니다.",
            "",
            "`planet_solver_noauth.py`로 녹화한 뒤 다시 실행하면 분석 지표가 생성됩니다.",
        ])
        try:
            out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        except PermissionError:
            return None
        return out

    total_shadow = sum(int(item.get("shadow_frames", 0) or 0) for item in items)
    total_divergence = sum(int(item.get("divergence_count", 0) or 0) for item in items)
    total_recovery = sum(int(item.get("recovery_candidates", 0) or 0) for item in items)
    total_allowed = sum(int(item.get("rescue_allowed_frames", 0) or 0) for item in items)
    total_used = sum(int(item.get("selector_rescue_used", 0) or 0) for item in items)
    lines.extend([
        f"- 분석 파일: {len(items)}개",
        f"- shadow 프레임: {total_shadow}개",
        f"- divergence 프레임: {total_divergence}개",
        f"- recovery 후보: {total_recovery}개",
        f"- selector rescue 허용: {total_allowed}개",
        f"- selector rescue 채택: {total_used}개",
        "",
        "| 파일 | 프레임 | shadow | bg-split | allowed | blocked | used | health-rescue | divergence | max-div | 주요 family |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ])
    for item in items:
        families = item.get("families", {}) or {}
        if isinstance(families, Mapping) and families:
            top_family = max(families.items(), key=lambda pair: int(pair[1]))[0]
        else:
            top_family = "-"
        lines.append(
            "| {name} | {frames} | {shadow_frames} | {bg_split_frames} | "
            "{rescue_allowed_frames} | {rescue_blocked_frames} | "
            "{selector_rescue_used} | {health_rescue_frames} | "
            "{divergence_count} | {max_divergence} | {family} |".format(
                name=item.get("name", ""),
                frames=item.get("frames", 0),
                shadow_frames=item.get("shadow_frames", 0),
                bg_split_frames=item.get("bg_split_frames", 0),
                rescue_allowed_frames=item.get("rescue_allowed_frames", 0),
                rescue_blocked_frames=item.get("rescue_blocked_frames", 0),
                selector_rescue_used=item.get("selector_rescue_used", 0),
                health_rescue_frames=item.get("health_rescue_frames", 0),
                divergence_count=item.get("divergence_count", 0),
                max_divergence=item.get("max_divergence", 0.0),
                family=top_family,
            )
        )

    lines.append("")
    lines.append("## 주요 이벤트")
    for item in items:
        events = item.get("events", []) or []
        if not events:
            continue
        lines.append("")
        lines.append(f"### {item.get('name', '')}")
        for event in events[:10]:
            lines.append(f"- f{event.get('frame')}: {event.get('kind')} {event}")

    try:
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except PermissionError:
        return None
    return out


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="selector_shadow JSONL 분석 리포트를 생성합니다.")
    parser.add_argument("path", nargs="?", default="_record_debug")
    parser.add_argument("--out", default="03_output/2026-06-26_selector_shadow_rescue_analysis_v1.md")
    parser.add_argument("--divergence-px", type=float, default=30.0)
    parser.add_argument("--jump-px", type=float, default=40.0)
    args = parser.parse_args(argv)

    summaries = analyze_record_path(
        args.path,
        divergence_px=args.divergence_px,
        jump_px=args.jump_px,
    )
    report = write_markdown_report(summaries, args.out)
    print(f"selector_shadow files={len(summaries)} report={report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
