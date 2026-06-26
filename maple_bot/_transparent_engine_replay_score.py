# 투명 도형 퍼즐 새 엔진을 녹화 JSONL과 GT 프레임으로 재생 채점합니다.
from __future__ import annotations

import csv
import io
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _path_family_oracle as path_score
import _phase_catalog_score as phase_catalog
from core.vision.transparent_puzzle_engine import (
    EngineConfig,
    PuzzleCandidate,
    PuzzleEngineInput,
    TransparentPuzzleEngine,
)

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "03_output"

Point = Tuple[float, float]


def candidate_from_tuple(row: Sequence[float]) -> PuzzleCandidate:
    cx, cy, score, w, h = row[:5]
    return PuzzleCandidate(
        float(cx),
        float(cy),
        float(score),
        float(w),
        float(h),
    )


def _candidate_set_to_engine(candidates) -> List[PuzzleCandidate]:
    out = []
    for cand in candidates:
        cx, cy, w, h, score = cand[:5]
        out.append(candidate_from_tuple((cx, cy, score, w, h)))
    return out


def load_engine_inputs(name: str) -> List[PuzzleEngineInput]:
    frames = phase_catalog.load_frames(name)
    rows = phase_catalog.load_rows(name)
    wrows = phase_catalog.load_wrows(name)
    prep_end, white = phase_catalog.detect_prep(frames)
    csets = phase_catalog.candidate_sets(rows, wrows, white)

    inputs = []
    for frame_index, candidates in enumerate(csets):
        gray_frame = None
        inputs.append(
            PuzzleEngineInput(
                frame_index=frame_index,
                candidates=_candidate_set_to_engine(candidates),
                white_anchor=white.get(frame_index) if frame_index < prep_end else None,
                gray_frame=gray_frame,
            )
        )
    return inputs


def run_clip(name: str, config: EngineConfig | None = None) -> Dict[int, Point]:
    engine = TransparentPuzzleEngine(config or EngineConfig())
    path: Dict[int, Point] = {}
    for inp in load_engine_inputs(name):
        out = engine.update(inp)
        if out.x is not None and out.y is not None:
            path[inp.frame_index] = (float(out.x), float(out.y))
    return path


def score_clip(name: str, config: EngineConfig | None = None) -> dict:
    gt = phase_catalog.load_gt(name)
    if not gt:
        return {
            "name": name,
            "covered": 0,
            "coverage": 0.0,
            "mean": float("inf"),
            "max": float("inf"),
            "success": False,
        }
    score = path_score.score_path(run_clip(name, config=config), gt)
    score["name"] = name
    return score


def score_all(config: EngineConfig | None = None) -> List[dict]:
    rows = []
    for name in phase_catalog.names_from_gt():
        rows.append(score_clip(name, config=config))
    return rows


def summarize(rows: Sequence[dict]) -> dict:
    return {
        "success": sum(1 for row in rows if row["success"]),
        "total": len(rows),
        "mean": float(np.mean([row["mean"] for row in rows])) if rows else float("nan"),
    }


def csv_text(rows: Sequence[dict]) -> str:
    buf = io.StringIO()
    fields = ["name", "mean", "max", "covered", "coverage", "success"]
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row[field] for field in fields})
    return buf.getvalue()


def write_outputs(rows: Sequence[dict]) -> Path | None:
    OUT_DIR.mkdir(exist_ok=True)
    version = 1
    while True:
        path = OUT_DIR / f"2026-06-24_transparent_engine_replay_score_v{version}.csv"
        if not path.exists():
            break
        version += 1
    try:
        path.write_text(csv_text(rows), encoding="utf-8")
    except PermissionError:
        return None
    return path


def main() -> None:
    rows = score_all()
    summary = summarize(rows)
    print(f"transparent_engine: {summary['success']}/{summary['total']} mean={summary['mean']:.1f}px")
    for row in rows:
        print(f"{row['name']}: {row['mean']:.1f}px {'OK' if row['success'] else 'FAIL'}")
    out_path = write_outputs(rows)
    if out_path is None:
        print("saved: skipped by current filesystem permission")
    else:
        print(f"saved: {out_path}")
    print("\n=== CSV ===")
    print(csv_text(rows))


if __name__ == "__main__":
    main()
