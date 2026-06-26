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


def _limit_candidates(candidates: Sequence[Candidate], limit: int | None) -> list[Candidate]:
    if limit is None or int(limit) <= 0:
        return list(candidates)
    return sorted(candidates, key=lambda candidate: candidate[2], reverse=True)[: int(limit)]


def _load_width_sidecar(path: str | Path, *, limit: int | None = None) -> list[list[list[float]]]:
    source = Path(path)
    sidecar = source.with_suffix(".wjsonl")
    if source.suffix.lower() == ".wjsonl" or not sidecar.exists():
        return []
    rows = []
    max_rows = None if limit is None or int(limit) <= 0 else int(limit)
    with sidecar.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                item = []
            rows.append(item if isinstance(item, list) else [])
            if max_rows is not None and len(rows) >= max_rows:
                break
    return rows


def _merge_width_sidecar(rows: list[dict], width_rows: Sequence[Sequence[Sequence[float]]]) -> list[dict]:
    if not width_rows:
        return rows
    merged = []
    for index, row in enumerate(rows):
        copied = dict(row)
        width_candidates = width_rows[index] if index < len(width_rows) else []
        copied["cands"] = _merge_candidate_widths(copied.get("cands", []), width_candidates)
        merged.append(copied)
    return merged


def _merge_candidate_widths(candidates: object, width_candidates: Sequence[Sequence[float]]) -> object:
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        return candidates
    out = []
    for candidate in candidates:
        if not isinstance(candidate, Sequence) or isinstance(candidate, (str, bytes)) or len(candidate) < 3:
            out.append(candidate)
            continue
        if len(candidate) >= 5:
            out.append(candidate)
            continue
        width_match = _nearest_width_candidate(candidate, width_candidates)
        if width_match is None:
            out.append(candidate)
            continue
        out.append([
            float(candidate[0]),
            float(candidate[1]),
            float(candidate[2]),
            float(width_match[2]),
            float(width_match[3]),
        ])
    return out


def _nearest_width_candidate(
    candidate: Sequence[float],
    width_candidates: Sequence[Sequence[float]],
    *,
    max_distance: float = 16.0,
) -> Sequence[float] | None:
    best = None
    best_dist = None
    for width_candidate in width_candidates:
        if not isinstance(width_candidate, Sequence) or len(width_candidate) < 4:
            continue
        try:
            dx = float(candidate[0]) - float(width_candidate[0])
            dy = float(candidate[1]) - float(width_candidate[1])
        except (TypeError, ValueError):
            continue
        dist = (dx * dx + dy * dy) ** 0.5
        if best_dist is None or dist < best_dist:
            best = width_candidate
            best_dist = dist
    if best_dist is None or best_dist > float(max_distance):
        return None
    return best


def _load_jsonl(
    path: str | Path,
    *,
    limit: int | None = None,
    use_width_sidecar: bool = True,
) -> list[dict]:
    rows = []
    max_rows = None if limit is None or int(limit) <= 0 else int(limit)
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
                if max_rows is not None and len(rows) >= max_rows:
                    break
    if use_width_sidecar:
        rows = _merge_width_sidecar(rows, _load_width_sidecar(path, limit=limit))
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
    emit_every: int = 1,
    max_candidates: int = 8,
    live_max_candidates: int | None = None,
    include_local_box: bool = True,
    merge_context_frames: int = 6,
    merge_min_size: float = 175.0,
    merge_size_ratio: float = 1.30,
) -> list[dict]:
    runtime = runtime or TransparentFamilySelectorRuntime()
    shadow_frames = int(min_frames if shadow_min_frames is None else shadow_min_frames)
    live_pool = TransparentLiveFamilyPool(window=window, min_frames=min_frames)
    shadow = TransparentSelectorShadow(
        runtime,
        clip_id=clip_id,
        window=window,
        min_frames=shadow_frames,
        emit_every=emit_every,
        max_candidates=max_candidates,
        include_local_box=include_local_box,
        merge_context_frames=merge_context_frames,
        merge_min_size=merge_min_size,
        merge_size_ratio=merge_size_ratio,
    )
    out: list[dict] = []
    seeded = False

    for index, row in enumerate(rows):
        copied = dict(row)
        frame = int(row.get("i", index) or index)
        candidates = _normalize_candidates(row.get("cands", []))
        track = _point(row.get("track"))
        live_candidates = _limit_candidates(candidates, live_max_candidates)
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
    *,
    limit: int | None = None,
    use_width_sidecar: bool = True,
    **kwargs,
) -> Path | None:
    rows = _load_jsonl(in_path, limit=limit, use_width_sidecar=use_width_sidecar)
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
    parser.add_argument("--emit-every", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--max-candidates", type=int, default=8)
    parser.add_argument("--live-max-candidates", type=int, default=0)
    parser.add_argument("--merge-context-frames", type=int, default=6)
    parser.add_argument("--merge-min-size", type=float, default=175.0)
    parser.add_argument("--merge-size-ratio", type=float, default=1.30)
    parser.add_argument("--no-local-box", action="store_true")
    parser.add_argument("--no-width-sidecar", action="store_true")
    args = parser.parse_args(argv)

    source = Path(args.input)
    out_path = Path(args.out) if args.out else source.with_name(f"{source.stem}_selector_shadow.jsonl")
    result = write_backfilled_jsonl(
        source,
        out_path,
        limit=args.limit or None,
        use_width_sidecar=not args.no_width_sidecar,
        window=args.window,
        min_frames=args.min_frames,
        shadow_min_frames=args.shadow_min_frames or None,
        emit_every=args.emit_every,
        max_candidates=args.max_candidates,
        live_max_candidates=args.live_max_candidates or args.max_candidates,
        include_local_box=not args.no_local_box,
        merge_context_frames=args.merge_context_frames,
        merge_min_size=args.merge_min_size,
        merge_size_ratio=args.merge_size_ratio,
    )
    print(f"selector_shadow_backfill input={source} output={result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
