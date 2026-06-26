# 기존 record_debug JSONL에 selector_shadow 결과를 재생해 덧붙이는 유틸리티입니다.
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Sequence

from core.vision.transparent_family_selector_runtime import TransparentFamilySelectorRuntime
from core.vision.transparent_live_family_pool import TransparentLiveFamilyPool
from core.vision.transparent_selector_shadow import TransparentSelectorShadow


Point = tuple[float, float]
Candidate = tuple[float, float, float, float, float]


def _point(value: object) -> Point | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return None
    if len(value) < 2:
        return None
    try:
        return (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None


def _normalize_candidates(candidates: object) -> list[Candidate]:
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        return []
    out = []
    for candidate in candidates:
        if not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes)):
            continue
        if len(candidate) < 2:
            continue
        try:
            score = float(candidate[2]) if len(candidate) >= 3 else 0.0
            width = float(candidate[3]) if len(candidate) >= 4 else 24.0
            height = float(candidate[4]) if len(candidate) >= 5 else 24.0
            out.append((
                float(candidate[0]),
                float(candidate[1]),
                score,
                width,
                height,
            ))
        except (TypeError, ValueError):
            continue
    return out


def _load_jsonl(path: str | Path) -> list[dict]:
    rows = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _engine_track(row: Mapping[str, object]) -> Point | None:
    engine = row.get("engine")
    if not isinstance(engine, Mapping):
        return None
    return _point(engine.get("track"))


def backfill_selector_shadow_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    runtime=None,
    clip_id: str = "replay",
    window: int = 24,
    min_frames: int = 8,
    shadow_min_frames: int | None = None,
    max_candidates: int = 8,
    include_local_box: bool = True,
) -> list[dict]:
    runtime = runtime or TransparentFamilySelectorRuntime()
    shadow_frames = int(min_frames if shadow_min_frames is None else shadow_min_frames)
    live_pool = TransparentLiveFamilyPool(window=window, min_frames=min_frames)
    shadow = TransparentSelectorShadow(
        runtime,
        clip_id=clip_id,
        window=window,
        min_frames=shadow_frames,
        emit_every=1,
        max_candidates=max_candidates,
        include_local_box=include_local_box,
    )
    out: list[dict] = []
    seeded = False

    for index, row in enumerate(rows):
        copied = dict(row)
        frame = int(row.get("i", index) or index)
        candidates = _normalize_candidates(row.get("cands", []))
        track = _point(row.get("track"))
        live_candidates = candidates
        white_anchor = None
        if not seeded and track is not None:
            white_anchor = track
            live_candidates = []
            seeded = True

        live_decision = live_pool.update(
            frame,
            candidates=live_candidates,
            white_anchor=white_anchor,
        )

        anchors: dict[str, Point] = {}
        for family, point in live_decision.points.items():
            anchors[str(family)] = (float(point[0]), float(point[1]))
        if track is not None:
            anchors["panel_default_center_mild_state_mild"] = track
        engine_track = _engine_track(row)
        if engine_track is not None:
            anchors["phase_catalog_center_mild_state_mild"] = engine_track

        if anchors:
            record = shadow.update(
                frame,
                candidates=candidates,
                anchors=anchors,
            )
            if record is not None:
                copied["selector_shadow"] = record
        out.append(copied)

    return out


def write_backfilled_jsonl(
    in_path: str | Path,
    out_path: str | Path,
    **kwargs,
) -> Path | None:
    rows = _load_jsonl(in_path)
    backfilled = backfill_selector_shadow_rows(
        rows,
        clip_id=Path(in_path).stem,
        **kwargs,
    )
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in backfilled) + "\n"
    try:
        target.write_text(text, encoding="utf-8")
    except PermissionError:
        return None
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="record_debug JSONL에 selector_shadow를 backfill합니다.")
    parser.add_argument("input")
    parser.add_argument("--out", default="")
    parser.add_argument("--window", type=int, default=24)
    parser.add_argument("--min-frames", type=int, default=8)
    parser.add_argument("--shadow-min-frames", type=int, default=0)
    parser.add_argument("--max-candidates", type=int, default=8)
    args = parser.parse_args(argv)

    source = Path(args.input)
    out_path = Path(args.out) if args.out else source.with_name(f"{source.stem}_selector_shadow.jsonl")
    result = write_backfilled_jsonl(
        source,
        out_path,
        window=args.window,
        min_frames=args.min_frames,
        shadow_min_frames=args.shadow_min_frames or None,
        max_candidates=args.max_candidates,
    )
    print(f"selector_shadow_backfill input={source} output={result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
